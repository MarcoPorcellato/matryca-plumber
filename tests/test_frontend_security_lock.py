"""Regression checks for the frontend audit remediation in #584."""

import json
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
CHANGELOG = ROOT / "CHANGELOG.md"


def _json(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def test_frontend_manifest_and_lock_hold_the_first_fixed_audit_versions() -> None:
    manifest = _json(FRONTEND / "package.json")
    lock = _json(FRONTEND / "package-lock.json")

    assert manifest["overrides"] == {"browserslist": "4.28.7", "nanoid": "3.3.18"}

    packages = lock["packages"]
    assert isinstance(packages, dict)
    for package, version in (("browserslist", "4.28.7"), ("nanoid", "3.3.18")):
        resolved = packages[f"node_modules/{package}"]
        assert isinstance(resolved, dict)
        assert resolved["version"] == version


def test_frontend_security_remediation_is_tracked_by_issue_584() -> None:
    assert "Frontend dependency audit remediation" in CHANGELOG.read_text(encoding="utf-8")
    assert "Refs #584." in CHANGELOG.read_text(encoding="utf-8")
