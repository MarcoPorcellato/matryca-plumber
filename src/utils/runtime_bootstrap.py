"""Ensure Matryca Plumber runtime directories and config exist before graph processing.

Provisioned on every Matryca Plumber startup (MCP lifespan, daemon, UI, CLI):

- **Logs** — parent dirs for ``MATRYCA_PLUMBER_LOG_PATH`` and ``MATRYCA_LOGURU_LOG_PATH``
  (default: repo ``logs/``).
- **L1** — ``<parent-of-vault>/matryca-l1/`` with ``README.md`` + ``session-rules.md`` when empty.
- **Graph** — ``.matryca_semantic_cache/``, ``templates/`` (or ``templates_subdir`` from wiki YAML).
- **Wiki config** — ``matryca-wiki.yml`` seeded from ``matryca-wiki.example.yml`` when missing.

Created lazily on first use (not at bootstrap): ``.matryca_daemon_state.json``,
``.matryca_xray_state.json``, daemon PID/lock files, catalog JSON bodies.
Repo ``.env`` is copied from ``.env.example`` on first startup when missing.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from loguru import logger

from ..agent.l1_memory import ensure_matryca_l1_dir
from ..config import MatrycaWikiConfig, load_matryca_wiki_config
from .config_paths import ensure_plumber_log_directories

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _REPO_ROOT / ".env"
_ENV_EXAMPLE = _REPO_ROOT / ".env.example"
_WIKI_EXAMPLE = _REPO_ROOT / "matryca-wiki.example.yml"
_SEMANTIC_CACHE_DIR = ".matryca_semantic_cache"


def ensure_repo_dotenv_from_example(*, repo_root: Path | None = None) -> bool:
    """Copy ``.env.example`` to ``.env`` when missing (idempotent).

    Returns:
        ``True`` when a new ``.env`` was created from the example template.
    """
    if repo_root is None and os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    root = repo_root or _REPO_ROOT
    env_path = root / ".env"
    example_path = root / ".env.example"
    if env_path.is_file():
        return False
    if not example_path.is_file():
        logger.warning(
            "Cannot provision .env: .env.example is missing at {}",
            example_path,
        )
        return False
    shutil.copy2(example_path, env_path)
    logger.info(
        "Created repository .env from .env.example — review LOGSEQ_GRAPH_PATH and "
        "LLM settings in Settings before running on a production vault",
    )
    return True


def ensure_graph_runtime_directories(
    graph_root: Path,
    *,
    templates_subdir: str = "templates",
) -> None:
    """Create graph-local Matryca working directories (cache, templates)."""
    root = graph_root.expanduser().resolve(strict=False)
    (root / _SEMANTIC_CACHE_DIR).mkdir(parents=True, exist_ok=True)
    subdir = (templates_subdir or "templates").strip().strip("/\\")
    if subdir:
        (root / subdir).mkdir(parents=True, exist_ok=True)


def _patch_memory_path_in_wiki_yaml(text: str, l1_dir: Path) -> str:
    escaped = str(l1_dir).replace("\\", "\\\\")
    if re.search(r"^memory_path:\s*", text, flags=re.MULTILINE):
        return re.sub(
            r"^memory_path:\s*.*$",
            f"memory_path: {escaped}",
            text,
            count=1,
            flags=re.MULTILINE,
        )
    return f"memory_path: {escaped}\n\n{text}"


def ensure_matryca_wiki_config_file(
    graph_root: Path,
    *,
    l1_dir: Path | None = None,
) -> Path | None:
    """Seed ``matryca-wiki.yml`` from the repo example when missing under the graph root."""
    root = graph_root.expanduser().resolve(strict=False)
    target = root / "matryca-wiki.yml"
    if target.is_file():
        return target
    if not _WIKI_EXAMPLE.is_file():
        return None
    text = _WIKI_EXAMPLE.read_text(encoding="utf-8")
    if l1_dir is not None:
        text = _patch_memory_path_in_wiki_yaml(text, l1_dir)
    target.write_text(text, encoding="utf-8")
    logger.bind(path=str(target)).info("Created matryca-wiki.yml from matryca-wiki.example.yml")
    return target


def prepare_matryca_runtime(
    *,
    graph_root: Path | None = None,
    wiki_config: MatrycaWikiConfig | None = None,
    eager_graph: bool = True,
) -> None:
    """Provision logs, L1 memory, graph cache dirs, and optional wiki config before work.

    Args:
        graph_root: Resolved Logseq vault root (``pages/`` parent), or ``None``.
        wiki_config: Optional wiki orchestration config.
        eager_graph: When ``True`` (daemon, CLI, UI), load the in-memory AST index and
            identity config immediately. When ``False`` (MCP stdio lifespan), defer
            heavy graph parsing until the first tool call that needs the graph — so
            MCP ``initialize`` / ``tools/list`` complete in seconds.
    """
    ensure_plumber_log_directories()
    if graph_root is None:
        return

    cfg = wiki_config or MatrycaWikiConfig()
    l1_dir = ensure_matryca_l1_dir(
        logseq_graph_path=str(graph_root),
        memory_path_from_yaml=cfg.memory_path,
    )
    ensure_graph_runtime_directories(graph_root, templates_subdir=cfg.templates_subdir)
    ensure_matryca_wiki_config_file(graph_root, l1_dir=l1_dir)
    from ..daemon import register_daemon_post_write_hooks

    register_daemon_post_write_hooks(graph_root)
    if not eager_graph:
        return

    from ..daemon.ast_cache import get_graph_ast_cache
    from ..daemon.config_layer import get_identity_store

    get_graph_ast_cache(graph_root).bootstrap()
    get_identity_store(graph_root).reload_if_stale(force=True)


def try_prepare_matryca_runtime_from_env() -> None:
    """Provision runtime dirs from the current process environment (idempotent)."""
    ensure_repo_dotenv_from_example()
    from ..agent.plumber_config import reload_plumber_dotenv

    reload_plumber_dotenv()
    wiki_config = load_matryca_wiki_config()
    graph_raw = os.environ.get("LOGSEQ_GRAPH_PATH", "").strip()
    if not graph_raw:
        prepare_matryca_runtime(graph_root=None, wiki_config=wiki_config)
        return
    from ..graph.graph_path_validate import validate_logseq_graph_path

    try:
        graph_root = validate_logseq_graph_path(graph_raw)
    except ValueError:
        prepare_matryca_runtime(graph_root=None, wiki_config=wiki_config)
        return
    prepare_matryca_runtime(graph_root=graph_root, wiki_config=wiki_config)


__all__ = [
    "ensure_graph_runtime_directories",
    "ensure_matryca_wiki_config_file",
    "ensure_repo_dotenv_from_example",
    "prepare_matryca_runtime",
    "try_prepare_matryca_runtime_from_env",
]
