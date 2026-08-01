from __future__ import annotations

import asyncio
import hashlib
import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from mcp.server.fastmcp import FastMCP
from src.agent.daemon_state import DaemonState
from src.agent.graph_tool_helpers import MutateGraphAction, RefactorBlocksAction
from src.agent.maintenance_daemon import start_daemon_detached, start_daemon_foreground
from src.agent.mcp_server import AppContext, register_mcp_tools
from src.cli import MUTATE_ACTIONS, REFACTOR_ACTIONS, main
from src.cli.ui_server import app
from src.config import MatrycaWikiConfig
from src.graph.safety.write_policy import GraphReadOnlyError, RuntimeWritePolicy
from src.shadow.bootstrap import reset_shadow_bootstrap_checked_for_tests
from src.shadow.cache_location import resolve_shadow_cache_location
from src.shadow.runtime_state import reset_shadow_runtime_state_for_tests
from src.utils.runtime_bootstrap import prepare_matryca_runtime


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _manifest(root: Path) -> dict[str, dict[str, str | int]]:
    """Capture graph entries without following symlinks or recording unstable timestamps."""
    entries: dict[str, dict[str, str | int]] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        metadata = path.lstat()
        common: dict[str, str | int] = {"mode": stat.S_IMODE(metadata.st_mode)}
        if path.is_symlink():
            entries[relative] = {**common, "type": "symlink", "target": os.readlink(path)}
        elif path.is_dir():
            entries[relative] = {**common, "type": "directory"}
        elif path.is_file():
            payload = path.read_bytes()
            entries[relative] = {
                **common,
                "type": "file",
                "size": len(payload),
                "sha256": _sha256(payload),
            }
        else:
            entries[relative] = {**common, "type": "other"}
    return entries


def _manifest_digest(manifest: dict[str, dict[str, str | int]]) -> str:
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    return _sha256(payload)


def _fixture_graph(tmp_path: Path) -> tuple[Path, Path, Path]:
    graph = tmp_path / "graph"
    external = tmp_path / "external"
    outside = tmp_path / "outside"
    for directory in (
        graph / "pages",
        graph / "journals",
        graph / "logseq" / "bak",
        graph / ".git" / "hooks",
        external,
        outside,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    (graph / "pages" / "Alpha.md").write_text(
        "- Alpha\n  id:: aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa\n",
        encoding="utf-8",
    )
    (graph / "journals" / "2026_08_02.md").write_text("- TODO qualify\n", encoding="utf-8")
    (graph / ".hidden").write_bytes(b"hidden\n")
    (graph / ".matryca_daemon.lock").write_bytes(b"existing-lock\n")
    (graph / "pages" / ".Alpha.md.tmp").write_bytes(b"existing-temp\n")
    (graph / ".git" / "config").write_text("[core]\n\tbare = false\n", encoding="utf-8")
    hook = graph / ".git" / "hooks" / "post-commit"
    hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    hook.chmod(0o755)
    outside_target = outside / "escape.md"
    outside_target.write_text("outside\n", encoding="utf-8")
    try:
        (graph / "pages" / "Escape.md").symlink_to(Path("..") / ".." / "outside" / "escape.md")
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    return graph, external, outside_target


def _assert_cli_exit(argv: list[str], expected: int) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == expected


def _mcp_context() -> Any:
    return SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=AppContext(wiki_config=MatrycaWikiConfig())
        )
    )


async def _exercise_mcp_surfaces(graph: Path) -> None:
    server = FastMCP("read-only-qualification")
    register_mcp_tools(server)
    tools = server._tool_manager._tools  # noqa: SLF001
    context = _mcp_context()

    page = await tools["read_graph_data"].fn(context, "page", "Alpha")
    regex = await tools["search_graph"].fn(context, "regex", "Alpha")
    assert "Alpha" in page
    assert "Alpha" in regex

    for mutate_action in MUTATE_ACTIONS:
        result = await tools["mutate_graph"].fn(
            context,
            mutate_action,
            "Alpha|aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            '{"dry_run":false}',
        )
        assert result["ok"] is False
        assert result["code"] == "graph_read_only"
    for refactor_action in REFACTOR_ACTIONS:
        result = await tools["refactor_blocks"].fn(
            context,
            refactor_action,
            "Alpha",
            '{"dry_run":false}',
        )
        assert result["ok"] is False
        assert result["code"] == "graph_read_only"
    for tool_name, args in (
        ("store_fact", (context, "do not write")),
        ("ingest_document", (context, "sample.md", "- content")),
        ("import_tana", (context, str(graph / "export.json"), False)),
    ):
        result = await tools[tool_name].fn(*args)
        assert result["ok"] is False
        assert result["code"] == "graph_read_only"

    dry_run_calls: list[tuple[str, str]] = []

    async def _dry_mutate(action: MutateGraphAction, _target: str, _payload: str) -> dict[str, Any]:
        dry_run_calls.append(("mutate", action))
        return {"ok": True, "dry_run": True}

    async def _dry_refactor(
        action: RefactorBlocksAction, _target: str, _payload: str
    ) -> dict[str, Any]:
        dry_run_calls.append(("refactor", action))
        return {"ok": True, "dry_run": True}

    with (
        patch("src.agent.mcp_server.dispatch_mutate", side_effect=_dry_mutate),
        patch("src.agent.mcp_server.dispatch_refactor", side_effect=_dry_refactor),
    ):
        await tools["mutate_graph"].fn(context, "edit_property", "Alpha|id", "{}")
        await tools["refactor_blocks"].fn(context, "split_large", "Alpha", "{}")
    assert dry_run_calls == [("mutate", "edit_property"), ("refactor", "split_large")]


@pytest.mark.integration
def test_read_only_immutability_qualification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph, external, outside_target = _fixture_graph(tmp_path)
    cache = external / "cache"
    log_path = external / "plumber.jsonl"
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(graph))
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    monkeypatch.setenv("MATRYCA_CACHE_PATH", str(cache))
    monkeypatch.setenv("MATRYCA_PLUMBER_LOG_PATH", str(log_path))
    monkeypatch.setenv("MATRYCA_GIT_AUDIT_ENABLED", "false")
    reset_shadow_runtime_state_for_tests()
    reset_shadow_bootstrap_checked_for_tests()
    baseline = _manifest(graph)
    outside_before = outside_target.read_bytes()

    _assert_cli_exit(["--json", "read", "page", "Alpha"], 0)
    _assert_cli_exit(["--json", "search", "regex", "Alpha"], 0)

    for mutate_action in MUTATE_ACTIONS:
        _assert_cli_exit(
            [
                "--json",
                "mutate",
                mutate_action,
                "--target",
                "Alpha|aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "--payload",
                '{"dry_run":false}',
            ],
            1,
        )
    for refactor_action in REFACTOR_ACTIONS:
        _assert_cli_exit(
            [
                "--json",
                "refactor",
                refactor_action,
                "Alpha",
                "--payload",
                '{"dry_run":false}',
            ],
            1,
        )

    cli_dry_runs: list[str] = []

    async def _dry_dispatch(*args: Any, **_kwargs: Any) -> dict[str, Any]:
        cli_dry_runs.append(str(args[0]))
        return {"ok": True, "dry_run": True}

    with (
        patch("src.cli.dispatch_mutate", side_effect=_dry_dispatch),
        patch("src.cli.dispatch_refactor", side_effect=_dry_dispatch),
    ):
        _assert_cli_exit(
            [
                "--json",
                "mutate",
                "edit_property",
                "--target",
                "Alpha|aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "--payload",
                "{}",
            ],
            0,
        )
        _assert_cli_exit(
            ["--json", "refactor", "split_large", "Alpha", "--payload", "{}"],
            0,
        )
    assert cli_dry_runs == ["edit_property", "split_large"]

    asyncio.run(_exercise_mcp_surfaces(graph))

    prepare_matryca_runtime(graph_root=graph, wiki_config=MatrycaWikiConfig(), eager_graph=False)
    assert cache.exists()
    assert not cache.is_relative_to(graph)

    default_location = resolve_shadow_cache_location(
        graph,
        env={"MATRYCA_READ_ONLY": "true"},
        platform_name="darwin",
        home=external / "default-home",
    )
    assert (
        default_location.cache_root
        == external / "default-home" / "Library" / "Caches" / "matryca-plumber"
    )
    assert not default_location.database_path.is_relative_to(graph)

    cache_inside_alias = external / "cache-inside-alias"
    cache_inside_alias.symlink_to(graph / "logseq", target_is_directory=True)
    with pytest.raises(GraphReadOnlyError):
        RuntimeWritePolicy.from_env(
            graph,
            env={"MATRYCA_READ_ONLY": "true", "MATRYCA_CACHE_PATH": str(cache_inside_alias)},
        )

    with (
        patch("src.agent.maintenance_daemon.MaintenanceDaemon.run_forever", return_value=None),
        patch("src.agent.maintenance_daemon.apply_plumber_priority", return_value=None),
        patch("src.agent.maintenance_daemon.apply_cpu_sandbox", return_value=None),
    ):
        start_daemon_foreground(graph)
    detached = start_daemon_detached(graph)
    assert detached["ok"] is False
    assert detached["code"] == "read_only_foreground_required"

    with (
        patch("src.cli.ui_server.load_daemon_state", return_value=DaemonState()),
        patch("src.cli.ui_server.read_pid_file", return_value=None),
        patch("src.cli.ui_server._session_token_totals_for_api", return_value=(0, 0)),
        TestClient(app) as client,
    ):
        token = client.get("/api/auth/session").json()["token"]
        response = client.get("/api/state", headers={"X-Matryca-Token": token})
        assert response.status_code == 200
        assert response.json()["daemon_profile"] == "read_only_shadow_observer"

    writable_graph = tmp_path / "writable-graph"
    (writable_graph / "pages").mkdir(parents=True)
    monkeypatch.delenv("MATRYCA_READ_ONLY")
    assert RuntimeWritePolicy.from_env(writable_graph).ensure_write_allowed(
        writable_graph / "pages" / "Allowed.md"
    ) == (writable_graph / "pages" / "Allowed.md").resolve(strict=False)
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")

    final = _manifest(graph)
    assert final == baseline
    assert outside_target.read_bytes() == outside_before

    evidence = {
        "schema_version": 1,
        "status": "PASS",
        "manifest_sha256": _manifest_digest(final),
        "checks": [
            "cli_reads",
            "cli_mutators_rejected",
            "cli_dry_runs_allowed",
            "mcp_reads",
            "mcp_mutators_rejected",
            "mcp_dry_runs_allowed",
            "ui_startup",
            "daemon_startup",
            "shadow_external_cache",
            "shadow_default_cache",
            "symlink_escape_rejected",
            "unset_mode_writable",
            "graph_manifest_unchanged",
        ],
    }
    evidence_path = os.environ.get("MATRYCA_READ_ONLY_QUALIFICATION_EVIDENCE", "").strip()
    if evidence_path:
        Path(evidence_path).write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
