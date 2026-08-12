"""Agent-native CLI for the Logseq graph (Printing Press paradigm).

Machine-oriented stdout; errors on stderr. Bypasses MCP JSON-RPC overhead.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

from ..agent.context_load import load_agent_context
from ..agent.graph_dispatch import (
    dispatch_lint,
    dispatch_mutate,
    dispatch_read,
    dispatch_refactor,
    dispatch_search,
)
from ..agent.graph_tool_helpers import (
    MutateGraphAction,
    ReadGraphTarget,
    RefactorBlocksAction,
    RunLinterName,
    SearchGraphMethod,
)
from ..agent.maintenance_daemon import (
    resolve_graph_root,
    run_plumber_audit,
    run_plumber_cluster,
    start_daemon_detached,
    start_daemon_foreground,
    stop_daemon,
)
from ..agent.tana_import import run_tana_import
from ..config import load_matryca_wiki_config
from ..graph.graph_path_validate import validate_logseq_graph_path
from ..graph.safety.write_policy import (
    GraphReadOnlyError,
    ensure_graph_write_allowed,
    is_graph_read_only,
)
from ..graph.service_manager import manage_matryca_service
from ..memory.config import memory_graph_enabled
from ..utils.runtime_bootstrap import try_prepare_matryca_runtime_from_env
from ..utils.secret_redaction import redact_secrets_in_text
from .ui_server import run_ui_server

READ_TARGETS: tuple[ReadGraphTarget, ...] = (
    "page",
    "memory",
    "block_ast",
    "subtree",
    "structural_hops",
    "dashboard",
    "xray_page",
    "bootstrap_status",
    "shadow_status",
)
SEARCH_METHODS: tuple[SearchGraphMethod, ...] = (
    "bm25",
    "semantic",
    "regex",
    "unlinked_mentions",
    "journal_tasks",
    "resolve_entity",
    "recall",
)
MUTATE_ACTIONS: tuple[MutateGraphAction, ...] = (
    "write_outline",
    "edit_property",
    "append_journal",
    "inject_query",
    "generate_moc",
)
REFACTOR_ACTIONS: tuple[RefactorBlocksAction, ...] = (
    "split_large",
    "reparent",
    "generate_flashcards",
)
LINTER_NAMES: tuple[RunLinterName, ...] = (
    "unify_tags",
    "block_refs",
    "full_wiki_scan",
)


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level CLI parser and domain subcommands."""
    parser = argparse.ArgumentParser(prog="matryca", description="Agent-native Logseq graph CLI")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON on stdout (machine-readable for agents)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    read_p = sub.add_parser(
        "read",
        help="Read graph data (pages, memory, block AST, hops, dashboard)",
    )
    read_p.add_argument(
        "target_type",
        choices=READ_TARGETS,
        help="Read plane discriminator",
    )
    read_p.add_argument(
        "query",
        nargs="?",
        default="",
        help="Target-specific query string (optional for memory/dashboard)",
    )

    search_p = sub.add_parser("search", help="Search the on-disk graph")
    search_p.add_argument(
        "method",
        choices=SEARCH_METHODS,
        help="Search method",
    )
    search_p.add_argument(
        "query",
        nargs="?",
        default="",
        help="Keywords, regex, or JSON options",
    )

    mutate_p = sub.add_parser("mutate", help="Create or patch graph content")
    mutate_p.add_argument(
        "action",
        choices=MUTATE_ACTIONS,
        help="Mutation action",
    )
    mutate_p.add_argument(
        "--target",
        required=True,
        help="Parent block UUID or Page Title|block-uuid (use '' for append_journal)",
    )
    mutate_p.add_argument(
        "--payload",
        required=True,
        help="JSON outline, property edit spec, journal markdown, or query payload",
    )

    refactor_p = sub.add_parser("refactor", help="Restructure blocks on disk")
    refactor_p.add_argument(
        "action",
        choices=REFACTOR_ACTIONS,
        help="Refactor action",
    )
    refactor_p.add_argument(
        "target_uuid",
        help="Page title, optional page for split_large, or Page Title|block-uuid",
    )
    refactor_p.add_argument(
        "--payload",
        default="",
        help="Optional JSON options or reparent groups array",
    )

    lint_p = sub.add_parser("lint", help="Run vault hygiene linters")
    lint_p.add_argument(
        "linter_name",
        choices=LINTER_NAMES,
        help="Linter to run",
    )

    context_p = sub.add_parser(
        "context",
        help="Semantic macro: load page or block subtree context for agents",
    )
    context_sub = context_p.add_subparsers(dest="context_action", required=True)
    context_load = context_sub.add_parser(
        "load",
        help="Bundle spatial page context or a focused block subtree",
    )
    context_load.add_argument(
        "query",
        help="Page title or `Page Title|block-uuid` for subtree focus",
    )

    service_p = sub.add_parser(
        "service",
        help="Manage background system daemon integration",
    )
    service_p.add_argument(
        "action",
        choices=["install", "uninstall"],
        help="Install or remove the per-user background service unit",
    )

    plumber_p = sub.add_parser(
        "plumber",
        help="Matryca Plumber maintenance daemon (local LLM graph indexing)",
    )
    plumber_sub = plumber_p.add_subparsers(dest="plumber_action", required=True)
    plumber_start = plumber_sub.add_parser("start", help="Start the maintenance daemon")
    plumber_start.add_argument(
        "--foreground",
        action="store_true",
        help="Run in the current terminal instead of detaching",
    )
    plumber_sub.add_parser("status", help="Open the Plumber web UI (alias for ui)")
    plumber_sub.add_parser("ui", help="Start the FastAPI web UI and open Swagger docs")
    plumber_sub.add_parser("stop", help="Gracefully stop the running daemon")
    plumber_sub.add_parser(
        "audit",
        help="Run bootstrap harvest and graph insights diagnostic dashboard",
    )
    plumber_sub.add_parser(
        "cluster",
        help="Compute or audit deterministic semantic cluster neighborhoods",
    )

    import_p = sub.add_parser("import", help="Import external data into the Logseq graph")
    import_sub = import_p.add_subparsers(dest="import_command", required=True)
    tana_import_p = import_sub.add_parser(
        "tana",
        help="Import a Tana workspace JSON export into the graph",
    )
    tana_import_p.add_argument(
        "--file",
        required=True,
        dest="export_file",
        help="Path to the Tana workspace JSON export",
    )
    tana_import_p.add_argument(
        "--apply",
        action="store_true",
        help="Write to disk (default is dry-run: report only, no files touched)",
    )

    return parser


def _redact_text_if_sensitive(text: str) -> str:
    return redact_secrets_in_text(text)


def _sanitize_for_output(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _sanitize_for_output(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_output(item) for item in value]
    if isinstance(value, str):
        return _redact_text_if_sensitive(value)
    return value


def _wrap_cli_json(command: str, result: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, dict):
        payload: dict[str, Any] = {"ok": result.get("ok", True), "command": command, **result}
    else:
        payload = {"ok": True, "command": command, "text": result}
    sanitized = _sanitize_for_output(payload)
    if not isinstance(sanitized, dict):
        return {"ok": True, "command": command, "text": str(sanitized)}
    return sanitized


def _emit_result(result: str | dict[str, Any], *, as_json: bool = False, command: str = "") -> None:
    if as_json:
        safe_result = _wrap_cli_json(command, result)
        # stdout is the CLI output channel; payload sanitized
        safe_str = json.dumps(safe_result, ensure_ascii=False, indent=2)
        sys.stdout.write(safe_str)  # codeql[py/clear-text-logging-sensitive-data]
        sys.stdout.write("\n")
        return
    if isinstance(result, dict):
        safe_result = _sanitize_for_output(result)
        # stdout is the CLI output channel; payload sanitized
        safe_str = json.dumps(safe_result, ensure_ascii=False, indent=2)
        sys.stdout.write(safe_str)  # codeql[py/clear-text-logging-sensitive-data]
        sys.stdout.write("\n")
    else:
        # stdout is the CLI output channel; payload sanitized
        safe_str = _redact_text_if_sensitive(result)
        sys.stdout.write(safe_str)  # codeql[py/clear-text-logging-sensitive-data]
        if not result.endswith("\n"):
            sys.stdout.write("\n")


def _emit_error(message: str) -> None:
    sys.stderr.write(message)
    if not message.endswith("\n"):
        sys.stderr.write("\n")


def _mutation_is_dry_run(action: str, payload: str) -> bool:
    if action == "write_outline":
        return False
    raw = payload.strip()
    if not raw:
        return True
    if not raw.startswith("{"):
        return False
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if not isinstance(data, dict):
        return False
    return bool(data.get("dry_run", True))


def _reject_read_only_mutation(action: str, *, payload: str, dry_run: bool | None = None) -> None:
    if dry_run is None:
        dry_run = _mutation_is_dry_run(action, payload)
    if dry_run:
        return
    if not is_graph_read_only():
        return
    raw_graph = os.environ.get("LOGSEQ_GRAPH_PATH", "").strip()
    if not raw_graph:
        return
    graph_root = validate_logseq_graph_path(raw_graph)
    ensure_graph_write_allowed(graph_root, operation=action)


def _reject_read_only_cli_mutation(args: argparse.Namespace) -> None:
    """Reject an applying CLI mutation before runtime bootstrap can write locally."""

    if args.command in {"mutate", "refactor"}:
        _reject_read_only_mutation(args.action, payload=args.payload)
    elif args.command == "import" and args.import_command == "tana" and args.apply:
        _reject_read_only_mutation("import_tana", payload="", dry_run=False)


async def run_cli(args: argparse.Namespace) -> int:
    """Dispatch parsed CLI arguments to graph handlers."""
    wiki_config = load_matryca_wiki_config()
    command = args.command
    as_json = bool(getattr(args, "json", False))

    if command == "read":
        read_out = await dispatch_read(
            wiki_config,
            args.target_type,
            args.query,
        )
        if as_json:
            _emit_result(
                {"target_type": args.target_type, "query": args.query, "content": read_out},
                as_json=True,
                command=command,
            )
        else:
            _emit_result(read_out)
        return 0

    if command == "search":
        search_out: str | dict[str, Any] = await dispatch_search(args.method, args.query)
        _emit_result(search_out, as_json=as_json, command=command)
        return 0

    if command == "mutate":
        try:
            _reject_read_only_mutation(args.action, payload=args.payload)
        except GraphReadOnlyError as exc:
            _emit_error(f"{exc.code}: {exc}")
            return 1
        mutate_out: dict[str, Any] = await dispatch_mutate(
            args.action,
            args.target,
            args.payload,
        )
        _emit_result(mutate_out, as_json=as_json, command=command)
        if mutate_out.get("ok") is False:
            return 1
        return 0

    if command == "refactor":
        try:
            _reject_read_only_mutation(args.action, payload=args.payload)
        except GraphReadOnlyError as exc:
            _emit_error(f"{exc.code}: {exc}")
            return 1
        refactor_out: dict[str, Any] = await dispatch_refactor(
            args.action,
            args.target_uuid,
            args.payload,
        )
        _emit_result(refactor_out, as_json=as_json, command=command)
        if refactor_out.get("ok") is False:
            return 1
        return 0

    if command == "lint":
        lint_out: str | dict[str, Any] = await dispatch_lint(wiki_config, args.linter_name)
        if as_json and isinstance(lint_out, str):
            _emit_result(
                {"linter_name": args.linter_name, "report_markdown": lint_out},
                as_json=True,
                command=command,
            )
        else:
            _emit_result(lint_out, as_json=as_json, command=command)
        return 0

    if command == "context":
        if args.context_action == "load":
            context_out = await load_agent_context(args.query)
            _emit_result(context_out, as_json=as_json, command="context load")
            if context_out.get("ok") is False:
                return 1
            return 0
        _emit_error(f"unknown context action: {args.context_action}")
        return 2

    if command == "service":
        service_out: dict[str, Any] = manage_matryca_service(args.action)
        _emit_result(service_out, as_json=as_json, command=command)
        if service_out.get("ok") is False:
            return 1
        return 0

    if command == "plumber":
        graph_root = resolve_graph_root()
        plumber_action = args.plumber_action
        if plumber_action == "start":
            if args.foreground:
                start_daemon_foreground(graph_root)
                return 0
            start_out = start_daemon_detached(graph_root)
            _emit_result(start_out, as_json=as_json, command=command)
            return 0 if start_out.get("ok") is not False else 1
        if plumber_action == "stop":
            stop_out = stop_daemon(graph_root)
            _emit_result(stop_out, as_json=as_json, command=command)
            return 0 if stop_out.get("ok") is not False else 1
        if plumber_action == "audit":
            audit_out = run_plumber_audit(graph_root)
            _emit_result(audit_out, as_json=as_json, command=command)
            return 0 if audit_out.get("ok") is not False else 1
        if plumber_action == "cluster":
            cluster_out = run_plumber_cluster(graph_root)
            _emit_result(cluster_out, as_json=as_json, command=command)
            return 0 if cluster_out.get("ok") is not False else 1
        _emit_error(f"unknown plumber action: {plumber_action}")
        return 2

    if command == "import":
        if args.import_command == "tana":
            if not args.apply:
                _emit_error(
                    "DRY-RUN MODE: No files written to disk. Use --apply to commit.\n",
                )
            else:
                try:
                    _reject_read_only_mutation("import_tana", payload="", dry_run=False)
                except GraphReadOnlyError as exc:
                    _emit_error(f"{exc.code}: {exc}")
                    return 1
            import_result = run_tana_import(args.export_file, apply=args.apply)
            _emit_result(import_result.to_dict(), as_json=True, command="import tana")
            return 0 if import_result.ok else 1
        _emit_error(f"unknown import command: {args.import_command}")
        return 2

    _emit_error(f"unknown command: {command}")
    return 2


def _cli_eager_graph(args: argparse.Namespace) -> bool:
    """Return whether this CLI invocation should warm the in-memory AST index.

    ``search bm25`` and gated ``search recall`` use read-only lexical Shadow
    paths and must not pay for ``GraphAstCache.bootstrap`` (A-CLI-01 / #297).
    Keeping recall lazy also lets its disabled gate respond before graph setup.
    Other graph commands keep eager load so first-read latency stays predictable.
    """
    return not (args.command == "search" and getattr(args, "method", None) in {"bm25", "recall"})


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint: load ``.env``, parse args, run async dispatch."""
    parser = build_parser()
    args = parser.parse_args(argv)
    ui_only = args.command == "plumber" and args.plumber_action in {"status", "ui"}
    skip_eager_bootstrap = args.command == "plumber" and args.plumber_action == "start"
    disabled_recall = (
        args.command == "search" and args.method == "recall" and not memory_graph_enabled()
    )
    try:
        _reject_read_only_cli_mutation(args)
    except GraphReadOnlyError as exc:
        _emit_error(f"{exc.code}: {exc}")
        raise SystemExit(1) from exc
    if not ui_only and not skip_eager_bootstrap and not disabled_recall:
        try_prepare_matryca_runtime_from_env(eager_graph=_cli_eager_graph(args))
    if ui_only:
        try:
            run_ui_server()
        except KeyboardInterrupt:
            raise SystemExit(130) from None
        raise SystemExit(0)
    try:
        exit_code = asyncio.run(run_cli(args))
    except (ValueError, TypeError, json.JSONDecodeError, OSError) as exc:
        _emit_error(str(exc))
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
