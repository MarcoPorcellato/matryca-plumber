from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPTS = Path(__file__).parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _module() -> ModuleType:
    path = _SCRIPTS / "qualify_gate_b_soak.py"
    spec = importlib.util.spec_from_file_location("gate_b_soak", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _graph(tmp_path: Path) -> Path:
    graph = tmp_path / "graph"
    for directory in ("pages", "journals", "logseq"):
        (graph / directory).mkdir(parents=True)
    (graph / "pages" / "Alpha.md").write_text("- Alpha\n", encoding="utf-8")
    return graph


def _payload(*, crud: str = "PASS") -> dict[str, object]:
    return {
        "flag_off": True,
        "flag_on": True,
        "restart_health": True,
        "fts": True,
        "recovery": True,
        "subtree": "PASS",
        "synthetic_crud": crud,
        "source_count": 1,
        "indexed_count": 1,
        "quarantined_count": 0,
        "rss_kib": 100,
    }


def test_manifest_detects_non_markdown_and_mode_changes(tmp_path: Path) -> None:
    module = _module()
    graph = _graph(tmp_path)
    before = module._graph_manifest_digest(graph)
    hidden = graph / ".hidden"
    hidden.write_bytes(b"one")
    assert module._graph_manifest_digest(graph) != before
    changed = module._graph_manifest_digest(graph)
    hidden.chmod(0o600)
    assert module._graph_manifest_digest(graph) != changed


def test_profile_binding_rejects_profile_or_cache_drift(tmp_path: Path) -> None:
    module = _module()
    output = tmp_path / "evidence"
    first = module._load_or_create_profile(output, "default-on", tmp_path / "cache-a")
    assert first["profile"] == "default-on"
    with pytest.raises(module.EvidenceError, match="gate_b_profile_mismatch"):
        module._load_or_create_profile(output, "read-only-external", tmp_path / "cache-a")
    with pytest.raises(module.EvidenceError, match="gate_b_profile_mismatch"):
        module._load_or_create_profile(output, "default-on", tmp_path / "cache-b")


def test_external_cache_rejects_every_protected_tree(tmp_path: Path) -> None:
    module = _module()
    roots = {name: tmp_path / name for name in ("source", "working", "output", "repo")}
    for root in roots.values():
        root.mkdir()
    for protected in roots.values():
        with pytest.raises(module.EvidenceError, match="gate_b_cache_unsafe"):
            module._resolve_external_cache_root(
                protected / "cache",
                source=roots["source"],
                working=roots["working"],
                output=roots["output"],
                repo=roots["repo"],
            )


@pytest.mark.parametrize(
    ("profile", "read_only", "crud"),
    (("default-on", False, "PASS"), ("read-only-external", True, "SKIPPED")),
)
def test_profile_probe_uses_unset_default_and_preserves_graph(
    tmp_path: Path,
    profile: str,
    read_only: bool,
    crud: str,
) -> None:
    module = _module()
    graph = _graph(tmp_path)
    observed: list[dict[str, str]] = []

    def command(_command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        environment = kwargs["env"]
        assert isinstance(environment, dict)
        observed.append(environment)
        return subprocess.CompletedProcess([], 0, json.dumps(_payload(crud=crud)), "")

    result = module._run_profile_probe(
        Path(sys.executable),
        graph,
        tmp_path / "cache",
        profile,
        30,
        0,
        command_runner=command,
    )

    assert result["synthetic_crud"] == crud
    assert "MATRYCA_SHADOW_DB_ENABLED" not in observed[0]
    assert (observed[0].get("MATRYCA_READ_ONLY") == "true") is read_only


def test_profile_probe_fails_closed_on_graph_mutation(tmp_path: Path) -> None:
    module = _module()
    graph = _graph(tmp_path)

    def command(_command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        (graph / ".unexpected").write_bytes(b"mutation")
        return subprocess.CompletedProcess([], 0, json.dumps(_payload()), "")

    with pytest.raises(module.EvidenceError, match="working_copy_changed"):
        module._run_profile_probe(
            Path(sys.executable),
            graph,
            tmp_path / "cache",
            "default-on",
            30,
            0,
            command_runner=command,
        )


def test_manifest_binding_is_stable_and_fail_closed(tmp_path: Path) -> None:
    module = _module()
    output = tmp_path / "evidence"
    cache = tmp_path / "cache"
    graph = _graph(tmp_path)
    module._load_or_create_profile(output, "read-only-external", cache)
    module._bind_manifest(output, "read-only-external", cache, graph)
    module._bind_manifest(output, "read-only-external", cache, graph)
    (graph / ".unexpected").write_bytes(b"mutation")
    with pytest.raises(module.EvidenceError, match="working_copy_changed"):
        module._bind_manifest(output, "read-only-external", cache, graph)


def test_invalid_probe_payload_is_rejected() -> None:
    module = _module()
    payload = _payload()
    payload["flag_on"] = False
    with pytest.raises(module.EvidenceError, match="probe_invalid"):
        module._validate_payload(payload)


def test_main_reports_privacy_safe_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _module()
    result = module.main(
        [
            "--profile",
            "default-on",
            "--output",
            str(tmp_path / "evidence"),
            "--candidate-python",
            str(tmp_path / "missing-python"),
            "--source-vault",
            str(tmp_path / "missing-source"),
            "--expected-source-realpath-file",
            str(tmp_path / "missing-source.txt"),
            "--working-root",
            str(tmp_path / "working"),
            "--cache-root",
            str(tmp_path / "cache"),
        ]
    )
    assert result == 2
    assert capsys.readouterr().err.strip() == "gate b soak: storage_error"
