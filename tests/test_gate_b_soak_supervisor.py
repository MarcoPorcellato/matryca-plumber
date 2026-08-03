from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType


def _module() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / "run_gate_b_soak_supervisor.py"
    spec = importlib.util.spec_from_file_location("gate_b_soak_supervisor", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_terminal_pass_or_fail_stops_without_running_command(tmp_path: Path) -> None:
    module = _module()
    for status in ("PASS", "FAIL"):
        output = tmp_path / status
        output.mkdir()
        (output / module._RESULT_FILE).write_text(json.dumps({"status": status}), encoding="utf-8")
        called = False

        def command(*_args: object, **_kwargs: object) -> object:
            nonlocal called
            called = True
            raise AssertionError

        assert module.run_supervisor(output, ["collector"], command_runner=command) == 0
        assert called is False


def test_nonterminal_exit_requests_service_restart(tmp_path: Path) -> None:
    module = _module()
    result = module.run_supervisor(
        tmp_path,
        ["collector"],
        command_runner=lambda *_args, **_kwargs: subprocess.CompletedProcess([], 2),
    )
    assert result == module._RETRY_EXIT


def test_terminal_result_written_by_collector_stops_restart(tmp_path: Path) -> None:
    module = _module()
    output = tmp_path / "evidence"
    output.mkdir()

    def command(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        (output / module._RESULT_FILE).write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
        return subprocess.CompletedProcess([], 0)

    assert module.run_supervisor(output, ["collector"], command_runner=command) == 0


def test_invalid_terminal_result_fails_closed_without_restart(tmp_path: Path) -> None:
    module = _module()
    output = tmp_path / "evidence"
    output.mkdir()
    (output / module._RESULT_FILE).write_text("not-json", encoding="utf-8")
    assert module.run_supervisor(output, ["collector"]) == 0
