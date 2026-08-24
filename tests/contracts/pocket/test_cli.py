from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/build_pocket_contract_bundle.py"
SOURCE = ROOT / "contracts/pocket/v1"


def _run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_builds_and_verifies_json_receipt_without_absolute_path_output(tmp_path: Path) -> None:
    output = tmp_path / "bundle"

    built = _run_cli("build", "--source-dir", str(SOURCE), "--output-dir", str(output))

    assert built.returncode == 0
    build_receipt = json.loads(built.stdout)
    assert set(build_receipt) == {"bundle_digest", "content_root", "file_count"}
    assert str(tmp_path) not in built.stdout
    assert built.stderr == ""

    verified = _run_cli("verify", "--bundle-dir", str(output))

    assert verified.returncode == 0
    assert json.loads(verified.stdout) == build_receipt
    assert str(tmp_path) not in verified.stdout
    assert verified.stderr == ""


def test_cli_rejects_nonempty_output_without_path_or_body_disclosure(tmp_path: Path) -> None:
    output = tmp_path / "occupied"
    output.mkdir()
    retained = output / "retained.txt"
    retained.write_text("synthetic retained value", encoding="utf-8")

    result = _run_cli("build", "--source-dir", str(SOURCE), "--output-dir", str(output))

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == "output_not_empty\n"
    assert str(tmp_path) not in result.stderr
    assert "synthetic retained value" not in result.stderr
    assert retained.read_text(encoding="utf-8") == "synthetic retained value"


def test_cli_rejects_tampered_bundle_without_path_or_body_disclosure(tmp_path: Path) -> None:
    output = tmp_path / "bundle"
    built = _run_cli("build", "--source-dir", str(SOURCE), "--output-dir", str(output))
    assert built.returncode == 0
    tampered = output / "schemas/document.schema.json"
    tampered.write_bytes(tampered.read_bytes() + b" ")

    result = _run_cli("verify", "--bundle-dir", str(output))

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == "bundle_digest_mismatch\n"
    assert str(tmp_path) not in result.stderr
    assert "schemas/document.schema.json" not in result.stderr


def test_cli_normalizes_deep_manifest_recursion_without_disclosure(tmp_path: Path) -> None:
    bundle = tmp_path / "deep-manifest-bundle"
    bundle.mkdir()
    private_marker = "private-manifest-body"
    manifest = bundle / "bundle-manifest.json"
    manifest.write_bytes(b"[" * 50_000 + json.dumps(private_marker).encode("utf-8") + b"]" * 50_000)
    assert manifest.stat().st_size < 1024 * 1024

    result = _run_cli("verify", "--bundle-dir", str(bundle))

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == "invalid_bundle_manifest\n"
    assert str(ROOT) not in result.stderr
    assert str(tmp_path) not in result.stderr
    assert private_marker not in result.stderr
