"""Tests for read-only daemon checkpoint access."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.agent.maintenance_daemon import DaemonState, save_daemon_state
from src.daemon.checkpoint import read_daemon_checkpoint


def test_read_daemon_checkpoint_reads_bootstrap_fields(tmp_path: Path) -> None:
    (tmp_path / "pages").mkdir()
    save_daemon_state(
        tmp_path,
        DaemonState(
            bootstrap_complete=False,
            bootstrap_scanned=4,
            bootstrap_total=9,
            bootstrap_failed=True,
            bootstrap_failed_reason="disk full",
            status="idle",
        ),
    )
    view = read_daemon_checkpoint(tmp_path)
    assert view.bootstrap_complete is False
    assert view.bootstrap_scanned == 4
    assert view.bootstrap_total == 9
    assert view.bootstrap_failed is True
    assert view.bootstrap_failed_reason == "disk full"
    assert view.status == "idle"


def test_read_daemon_checkpoint_empty_when_missing(tmp_path: Path) -> None:
    (tmp_path / "pages").mkdir()
    view = read_daemon_checkpoint(tmp_path)
    assert view.bootstrap_complete is False
    assert view.bootstrap_total == 0


def test_read_daemon_checkpoint_logs_when_bak_restore_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.daemon.checkpoint import CHECKPOINT_BAK_FILENAME, CHECKPOINT_FILENAME

    (tmp_path / "pages").mkdir()
    primary = tmp_path / CHECKPOINT_FILENAME
    backup = tmp_path / CHECKPOINT_BAK_FILENAME
    primary.write_text("{not-json", encoding="utf-8")
    backup.write_text(
        '{"bootstrap_complete": true, "bootstrap_scanned": 2, "bootstrap_total": 5}',
        encoding="utf-8",
    )

    errors: list[str] = []

    def _fail_copy(*_args: object, **_kwargs: object) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr("src.graph.daemon_checkpoint.shutil.copy2", _fail_copy)
    monkeypatch.setattr(
        "src.graph.daemon_checkpoint.logger.exception",
        lambda msg, *args: errors.append(msg.format(*args) if args else msg),
    )

    view = read_daemon_checkpoint(tmp_path)
    assert view.bootstrap_complete is True
    assert view.bootstrap_scanned == 2
    assert view.bootstrap_total == 5
    assert any("restore primary" in err for err in errors)


def test_read_daemon_checkpoint_uses_backup_without_restore_in_read_only_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.daemon.checkpoint import CHECKPOINT_BAK_FILENAME, CHECKPOINT_FILENAME

    (tmp_path / "pages").mkdir()
    primary = tmp_path / CHECKPOINT_FILENAME
    backup = tmp_path / CHECKPOINT_BAK_FILENAME
    primary.write_text("{not-json", encoding="utf-8")
    backup.write_text('{"bootstrap_complete": true}', encoding="utf-8")
    before = primary.read_bytes()
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")

    assert read_daemon_checkpoint(tmp_path).bootstrap_complete is True
    assert primary.read_bytes() == before
