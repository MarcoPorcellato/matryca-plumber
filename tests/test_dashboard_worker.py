"""Private child ordering, native parity and source/import controls."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from src.agent import dashboard_worker as worker
from src.agent.dashboard_process import DashboardJobControl, run_dashboard_process
from src.agent.dashboard_protocol import (
    DashboardIntent,
    DashboardLimits,
    DashboardOutcome,
    DashboardRequest,
)
from src.config import MatrycaWikiConfig

REQUEST = "c" * 32
POSIX = pytest.mark.skipif(sys.platform not in {"linux", "darwin"}, reason="POSIX lane")


def _root(tmp_path: Path) -> Path:
    root = tmp_path.resolve()
    (root / "pages").mkdir()
    return root


def _run(
    root: Path, *, config: MatrycaWikiConfig | None = None, include_identity: bool = False
) -> DashboardOutcome:
    intent = DashboardIntent(
        request_id=REQUEST,
        raw_graph_path=str(root),
        wiki_config=config or MatrycaWikiConfig(),
        include_identity=include_identity,
    )
    limits = DashboardLimits(execution_s=30.0, cleanup_s=5.0)
    return run_dashboard_process(intent, limits=limits, control=DashboardJobControl(limits))


def test_dashboard_private_parser_shutdown_precedes_success_frame(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    calls: list[str] = []
    output = io.BytesIO()

    class Sink:
        def write(self, data: bytes) -> int:
            assert calls[-1] == "shutdown"
            return output.write(data)

        def flush(self) -> None:
            pass

    class Parser:
        def shutdown(self) -> None:
            calls.append("shutdown")

    def compute(*_args: object, on_phase: object) -> str:
        calls.append("compute")
        return "- synthetic"

    def identity(body: str) -> str:
        assert os.environ["LOGSEQ_GRAPH_PATH"] == str(root)
        calls.append("identity")
        return body + "\nIdentity"

    request = (
        DashboardRequest(
            request_id=REQUEST,
            graph_root=str(root),
            wiki_config=MatrycaWikiConfig(),
            include_identity=True,
        )
        .model_dump_json()
        .encode()
    )
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", "/synthetic/unrelated")
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")
    monkeypatch.setenv("MATRYCA_DEBUG", "false")
    monkeypatch.setattr(worker, "logger", SimpleNamespace(remove=lambda: None))
    monkeypatch.setattr(
        worker,
        "sys",
        SimpleNamespace(
            stdin=SimpleNamespace(buffer=io.BytesIO(request)),
            stdout=SimpleNamespace(buffer=Sink()),
            stderr=SimpleNamespace(buffer=io.BytesIO()),
        ),
    )
    monkeypatch.setattr(worker, "get_bounded_page_parse_worker", lambda: Parser())
    monkeypatch.setattr(worker, "build_dashboard_markdown", compute)
    monkeypatch.setattr("src.daemon.config_layer.append_identity_to_mcp_payload", identity)
    assert worker.main() == 0
    assert calls == ["compute", "identity", "shutdown"]
    assert json.loads(output.getvalue())["markdown"] == "- synthetic\nIdentity"


@pytest.mark.parametrize("shutdown_error", [False, True])
def test_dashboard_worker_never_emits_success_after_compute_or_shutdown_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shutdown_error: bool
) -> None:
    root = _root(tmp_path)
    output = io.BytesIO()

    class Parser:
        def shutdown(self) -> None:
            if shutdown_error:
                raise KeyboardInterrupt("synthetic shutdown")

    def compute(*_args: object, **_kwargs: object) -> str:
        if not shutdown_error:
            raise KeyboardInterrupt("synthetic computation")
        return "- synthetic"

    request = (
        DashboardRequest(request_id=REQUEST, graph_root=str(root), wiki_config=MatrycaWikiConfig())
        .model_dump_json()
        .encode()
    )
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(root))
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")
    monkeypatch.setenv("MATRYCA_DEBUG", "false")
    monkeypatch.setattr(worker, "logger", SimpleNamespace(remove=lambda: None))
    monkeypatch.setattr(
        worker,
        "sys",
        SimpleNamespace(
            stdin=SimpleNamespace(buffer=io.BytesIO(request)),
            stdout=SimpleNamespace(buffer=output),
            stderr=SimpleNamespace(buffer=io.BytesIO()),
        ),
    )
    monkeypatch.setattr(worker, "get_bounded_page_parse_worker", lambda: Parser())
    monkeypatch.setattr(worker, "build_dashboard_markdown", compute)
    monkeypatch.setattr("src.daemon.config_layer.append_identity_to_mcp_payload", lambda body: body)
    assert worker.main() == 0
    assert json.loads(output.getvalue())["code"] == "dashboard_worker_failed"
    assert "synthetic computation" not in output.getvalue().decode()


@POSIX
def test_dashboard_success_matches_existing_stats_and_outline(tmp_path: Path) -> None:
    root = _root(tmp_path)
    (root / "pages" / "Città.md").write_text(
        "alias:: City\n- One\n  id:: f47ac10b-58cc-4372-a567-0e02b2c3d479\n"
        "  - ((f47ac10b-58cc-4372-a567-0e02b2c3d479))\n"
        "- ((11111111-1111-4111-8111-111111111111))\n",
        encoding="utf-8",
    )
    (root / "journals").mkdir()
    (root / "journals" / "2026_10_26.md").write_text("- Daily\n", encoding="utf-8")
    before = {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }
    outcome = _run(root, config=MatrycaWikiConfig(namespaces=["Projects"]))
    assert outcome.cleanup_verified, outcome
    assert outcome.code is None, outcome
    assert outcome.last_phase == "complete"
    assert outcome.markdown is not None
    assert "**Pages (`pages/**/*.md`):** 1" in outcome.markdown
    assert "**`id::` declarations (v4, counted):** 1" in outcome.markdown
    assert "**Broken `((uuid))` refs:** 1" in outcome.markdown
    assert "[[Projects]]" in outcome.markdown
    after = {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }
    assert after == before


@POSIX
def test_dashboard_identity_is_appended_once_after_body_cap_from_request_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    (root / "pages" / "matryca-config.md").write_text(
        "- Telos\n  - Only synthetic identity\n", encoding="utf-8"
    )
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(tmp_path / "not-the-request-root"))
    outcome = _run(root, config=MatrycaWikiConfig(namespaces=["x" * 26000]), include_identity=True)
    assert outcome.cleanup_verified, outcome
    assert outcome.code is None, outcome
    assert outcome.markdown is not None
    assert "[TRUNCATED:" in outcome.markdown
    assert outcome.markdown.count("Only synthetic identity") == 1
    assert outcome.markdown.index("[TRUNCATED:") < outcome.markdown.index("Only synthetic identity")
    assert len(outcome.markdown) > 25000


@POSIX
def test_dashboard_direct_read_keeps_legacy_no_identity_behavior(tmp_path: Path) -> None:
    root = _root(tmp_path)
    (root / "pages" / "matryca-config.md").write_text(
        "- Telos\n  - Synthetic MCP-only context\n", encoding="utf-8"
    )
    outcome = _run(root)
    assert outcome.cleanup_verified and outcome.code is None, outcome
    assert outcome.markdown is not None
    assert "Synthetic MCP-only context" not in outcome.markdown


@POSIX
def test_dashboard_worker_does_not_execute_site_customization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    marker = tmp_path / "unexpected-customization"
    (root / "sitecustomize.py").write_text(
        f"open({str(marker)!r}, 'w').write('executed')\n", encoding="utf-8"
    )
    (root / "usercustomize.py").write_text(
        f"open({str(marker)!r}, 'w').write('executed')\n", encoding="utf-8"
    )
    (root / "danger.pth").write_text(
        f"import pathlib; pathlib.Path({str(marker)!r}).write_text('executed')\n", encoding="utf-8"
    )
    (root / "pages" / "Test.md").write_text("- content\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(root))
    outcome = _run(root)
    assert outcome.cleanup_verified, outcome
    assert outcome.code is None, outcome
    assert not marker.exists()


@POSIX
def test_dashboard_startup_import_origins_match_admitted_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.agent import dashboard_process as runtime

    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda _name: SimpleNamespace(
            origin=str(tmp_path / "wrong-checkout" / "src" / "__init__.py")
        ),
    )
    with pytest.raises(ValueError, match="origin rejected"):
        runtime._build_launch()


@POSIX
def test_dashboard_isolated_bootstrap_supports_installed_package_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    from src.agent import dashboard_process as runtime

    source = Path(runtime.__file__).resolve().parents[2]
    stage = tmp_path / "site-packages"
    stage.mkdir()
    for package in ("src", "matryca_plumber"):
        shutil.copytree(
            source / package, stage / package, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
        )
    original_argv, env, _cwd = runtime._build_launch()
    roots = json.loads(original_argv[-1])
    roots[0] = str(stage.resolve())
    argv = original_argv[:-1] + [json.dumps(roots)]
    monkeypatch.setattr(runtime, "_build_launch", lambda: (argv, env, stage))
    graph = tmp_path / "graph"
    graph.mkdir()
    root = _root(graph)
    (root / "pages" / "Layout.md").write_text("- synthetic\n", encoding="utf-8")
    outcome = _run(root)
    assert outcome.cleanup_verified, outcome
    assert outcome.code is None, outcome
    assert outcome.markdown is not None and "**Pages (`pages/**/*.md`):** 1" in outcome.markdown


@POSIX
def test_dashboard_actual_worker_has_isolated_flags_and_starts_no_network_or_watcher(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.agent import dashboard_process as runtime

    root = _root(tmp_path)
    (root / "pages" / "Read.md").write_text("- synthetic\n", encoding="utf-8")
    (root / "pages" / "matryca-config.md").write_text(
        "- Telos\n  - Synthetic identity\n", encoding="utf-8"
    )
    argv, env, cwd = runtime._build_launch()
    # This is a synthetic tripwire, not a production isolation mechanism.
    tripwire = "\n".join(
        [
            "import sys,json",
            "assert sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode",
            "def reject_network(event,args):",
            "    if event in {'socket.__new__','socket.connect',"
            "'socket.bind','socket.getaddrinfo'}:",
            "        raise RuntimeError('synthetic network tripwire')",
            "sys.addaudithook(reject_network)",
            "sys.path[:0]=json.loads(sys.argv[1])",
            "import watchdog.observers.api",
            "def reject_watch(*args,**kwargs):",
            "    raise RuntimeError('synthetic watcher tripwire')",
            "watchdog.observers.api.BaseObserver.start=reject_watch",
            "",
        ]
    )
    guarded = argv.copy()
    guarded[-2] = tripwire + argv[-2]
    monkeypatch.setattr(runtime, "_build_launch", lambda: (guarded, env, cwd))
    outcome = _run(root, include_identity=True)
    assert outcome.cleanup_verified, outcome
    assert outcome.code is None, outcome


@POSIX
@pytest.mark.slow
def test_dashboard_synthetic_1115_pages_complete_without_partial_counts(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    if request.config.getoption("markexpr", default="") != "slow":
        pytest.skip(
            "Deferred scale qualification: explicitly select -m slow; "
            "the historical 120-second attempt remains failed"
        )
    root = _root(tmp_path)
    for index in range(1115):
        (root / "pages" / f"Page{index}.md").write_text("- synthetic\n", encoding="utf-8")
    limits = DashboardLimits()
    intent = DashboardIntent(
        request_id=REQUEST, raw_graph_path=str(root), wiki_config=MatrycaWikiConfig()
    )
    outcome = run_dashboard_process(intent, limits=limits, control=DashboardJobControl(limits))
    assert outcome.cleanup_verified, outcome
    assert outcome.code is None, outcome
    assert outcome.markdown is not None
    assert "**Pages (`pages/**/*.md`):** 1115" in outcome.markdown
    assert outcome.last_phase == "complete"
