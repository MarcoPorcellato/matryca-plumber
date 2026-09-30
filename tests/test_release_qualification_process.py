from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from scripts.release_qualification import focused, installed, process, sdist_build


@pytest.mark.skipif(os.name == "nt", reason="POSIX runner lifecycle integration")
def test_all_qualification_runners_use_the_shared_process_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    starts: list[tuple[str, ...]] = []
    start_process = process.start_process

    def record_start(command: list[str], **kwargs: object) -> process.OwnedProcess:
        starts.append(tuple(command))
        return start_process(command, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(process, "start_process", record_start)

    focused_result = focused._run_command(
        [sys.executable, "-c", "print('focused')"],
        tmp_path,
        "Focused command failed.",
        timeout=3.0,
    )
    sdist_result = sdist_build._run_bounded(
        [sys.executable, "-I", "-c", "print('sdist')"],
        cwd=tmp_path,
        timeout=3.0,
        capture=True,
    )
    installed_result = installed._run_bounded(
        [sys.executable, "-c", "print('installed')"], cwd=tmp_path, timeout=3
    )

    assert focused_result.stdout == "focused\n"
    assert sdist_result.stdout == b"sdist\n"
    assert installed_result[1] == b"installed\n"
    assert len(starts) == 3


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group cleanup")
def test_group_signal_failure_still_kills_and_reaps_direct_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owned = process.start_process(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=None,
        stderr=None,
        windows=False,
    )

    def fail_group_signal(_process_group_id: int, _signal_number: int) -> None:
        raise ValueError("injected process-group signal failure")

    monkeypatch.setattr(process, "_signal_process_group", fail_group_signal)
    try:
        with pytest.raises(ValueError, match="Could not stop an owned qualification process group"):
            owned.terminate(grace_seconds=0.1, immediate=True)

        assert owned.process.poll() is not None
        assert owned.process.returncode is not None
    finally:
        if owned.process.poll() is None:
            owned.process.kill()
            owned.process.wait(timeout=3)
