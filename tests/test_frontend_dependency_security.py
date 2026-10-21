"""Static regression coverage for the admitted frontend source-map security pin."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

_NODE = "node_modules/source-map-js"
_EXPECTED = {
    "version": "1.2.2",
    "resolved": "https://registry.npmjs.org/source-map-js/-/source-map-js-1.2.2.tgz",
    "integrity": (
        "sha512-KGj/8Y43x35aZVDtt+J4mK1hoLGHULMYfSkODJNQjNDC3oW1PqPoxMwo0pLUsWM/"
        "UEGzON/NxeHywEfNXNP3Vw=="
    ),
}


def _assert_patched_source_map(lock: dict[str, Any]) -> None:
    packages = lock["packages"]
    copies = {name for name in packages if name == _NODE or name.endswith("/" + _NODE)}
    if copies != {_NODE}:
        raise ValueError("Expected exactly one source-map-js package record")
    for field, expected in _EXPECTED.items():
        if packages[_NODE].get(field) != expected:
            raise ValueError(f"source-map-js {field} differs from the patched pin")


def _admitted_fixture() -> dict[str, Any]:
    return {
        "lockfileVersion": 3,
        "packages": {
            "node_modules/source-map-js": {
                "version": "1.2.2",
                "resolved": "https://registry.npmjs.org/source-map-js/-/source-map-js-1.2.2.tgz",
                "integrity": (
                    "sha512-KGj/8Y43x35aZVDtt+J4mK1hoLGHULMYfSkODJNQjNDC3oW1PqPoxMwo0pLUsWM/"
                    "UEGzON/NxeHywEfNXNP3Vw=="
                ),
            }
        },
    }


def test_frontend_lock_uses_the_authenticated_patched_source_map() -> None:
    root = Path(__file__).resolve().parents[1]
    lock = json.loads((root / "frontend/package-lock.json").read_text(encoding="utf-8"))
    _assert_patched_source_map(lock)


def test_source_map_pin_rejects_the_affected_version() -> None:
    lock = _admitted_fixture()
    _assert_patched_source_map(lock)
    lock["packages"][_NODE]["version"] = "1.2.1"
    with pytest.raises(ValueError, match="source-map-js version"):
        _assert_patched_source_map(lock)


def test_source_map_pin_rejects_wrong_integrity() -> None:
    lock = _admitted_fixture()
    _assert_patched_source_map(lock)
    lock["packages"][_NODE]["integrity"] = "sha512-not-the-authenticated-artifact"
    with pytest.raises(ValueError, match="source-map-js integrity"):
        _assert_patched_source_map(lock)


def test_source_map_pin_rejects_a_second_affected_nested_copy() -> None:
    lock = _admitted_fixture()
    _assert_patched_source_map(lock)
    stale = deepcopy(lock["packages"][_NODE])
    stale.update(
        {
            "version": "1.2.1",
            "resolved": "https://registry.npmjs.org/source-map-js/-/source-map-js-1.2.1.tgz",
            "integrity": (
                "sha512-UXWMKhLOwVKb728IUtQPXxfYU+usdybtUrK/8uGE8CQMvrhOpwvzDBwj0QhSL7"
                "MQc7vIsISBG8VQ8+IDQxpfQA=="
            ),
        }
    )
    lock["packages"]["node_modules/other/node_modules/source-map-js"] = stale
    with pytest.raises(ValueError, match="exactly one source-map-js"):
        _assert_patched_source_map(lock)


def test_source_map_pin_rejects_an_unexpected_artifact_url() -> None:
    lock = _admitted_fixture()
    _assert_patched_source_map(lock)
    lock["packages"][_NODE]["resolved"] = "https://example.invalid/source-map-js-1.2.2.tgz"
    with pytest.raises(ValueError, match="source-map-js resolved"):
        _assert_patched_source_map(lock)


# Registry metadata consistency only; archive/provenance verification is separate.
_VITE_TOOLCHAIN: dict[str, dict[str, str]] = {
    "vite": {
        "version": "8.3.3",
        "resolved": "https://registry.npmjs.org/vite/-/vite-8.3.3.tgz",
        "integrity": (
            "sha512-cTAldKPImjg6c+gk48U19POPn3GCBzZwpdsN8ZMEEcbpes+6/wvfqUd0C2y3qYY4w"
            "sj8PwgFwrZ/1jBPVttMSg=="
        ),
    },
    "rolldown": {
        "version": "1.2.11",
        "resolved": "https://registry.npmjs.org/rolldown/-/rolldown-1.2.11.tgz",
        "integrity": (
            "sha512-qpSwIyz0jHQq5qXBTNxFmE6664rJ7O+4TvPFOiOaBSrz8IOHc1koKKSqTM2H6u1UG"
            "1+TveuC6vaDHKXFOvb1Kw=="
        ),
    },
    "@oxc-project/types": {
        "version": "0.151.0",
        "resolved": "https://registry.npmjs.org/@oxc-project/types/-/types-0.151.0.tgz",
        "integrity": (
            "sha512-J1yXrIlNDZVzE3ada310xeAw7nH8yCAyLPuUIsjKatFPmfn5bS1oW+cM+QsGOtVWd"
            "5nhSpbwZWx/rue+r5Z+PA=="
        ),
    },
}
_ROLLDOWN_BINDINGS = {
    "@rolldown/binding-android-arm-eabi": (
        "sha512-A5kXfGKvKWWZE0TtPrfsvT+q4Y5d1QG8gGUzpYjGydM+fARM9MuX90PrXYXe0XbsD"
        "VgyxxNzHo6giCj90bsFNw=="
    ),
    "@rolldown/binding-android-arm64": (
        "sha512-z6cTycz+iJ4PVkuL4HHW4DfTfoeU/2nqYYuSOrTmH7yHK5Y0LCOnA03V4ZNxavyVa"
        "U1oOqUgIg2klN/s+USGOA=="
    ),
    "@rolldown/binding-darwin-arm64": (
        "sha512-jShvqNtP6vDC6/A5JOAzbVV+DkgHqhl/ScVCJEbt+TUY6QYz7YnXcrg3sLtFBniro"
        "0f/Ld50ZwCWA6f7KYD1nQ=="
    ),
    "@rolldown/binding-darwin-x64": (
        "sha512-f2i2xiNWq1Z1l2++q2fuhZRdLAT3aqxD6vRNm1RAxpUoBcdqNB3C0s1Bt+K+PbEx2"
        "F5F4gQp6hqKkphCY/xF9w=="
    ),
    "@rolldown/binding-freebsd-x64": (
        "sha512-4Ir5FSOKIAMr4r0kExpt1s3bMgzJU3rA45AYOHtQpls0oNeqcYBKrWMlckrYH4KCf"
        "GLfkfn1tN1dmZPMVsdXow=="
    ),
    "@rolldown/binding-linux-arm-gnueabihf": (
        "sha512-/gnRDM+39BROzAN/k1OZjDPnDMcZxB/0EUxKjONO5yVkNEvlsoMDrxGNKgZi/ttFr"
        "iS2gwlDNzB65pvNbFOXIQ=="
    ),
    "@rolldown/binding-linux-arm64-gnu": (
        "sha512-PFaK8HwvAHbaKbBcDNQihjMKYvFnA5hiENx/l5tphTDz1E0WFp32l0A7aq7lyUwGs"
        "Rw/xSrNIy/gIK4thrSCrw=="
    ),
    "@rolldown/binding-linux-arm64-musl": (
        "sha512-AskzJUIKRLPxkruR1wLKewGbOw+EYfU/9lOrBFj4AFrEA8hPpKFnODWNu2WLaNs0Q"
        "NkEb9QIJufmVZZIL/bJlg=="
    ),
    "@rolldown/binding-linux-ppc64-gnu": (
        "sha512-qlUGAheh2yh8afH7QBgx0PrRHN85hKnNd78x8MeMhXivuevgd8vgf6/CstOzmNKY/"
        "lLTHvNTrPy98cLnAugzJw=="
    ),
    "@rolldown/binding-linux-s390x-gnu": (
        "sha512-secpEad+0vCbSfn8upFySkDskv+bGPk3THSDS9Y89yc4rb4kzqHp8Dmyd9BkQW4Sn"
        "hNXBZCl/6CrO//hZahNJQ=="
    ),
    "@rolldown/binding-linux-x64-gnu": (
        "sha512-mOVBT3dPpkWm8XBWPmU4bf+U6dYDLeMo/9ojUmis4N0L5uu10qra5vOyngZ7/PSdo"
        "E4G9KvRt4bloRxNjLas7A=="
    ),
    "@rolldown/binding-linux-x64-musl": (
        "sha512-Is78i9A8Ui4SqcxUwFJ9uMmjDn58IbVTjFWYdQestFEgeuEmHMLGNriXnVJKkwG2Y"
        "iZjw8cP0zCTyDMdDGtOOg=="
    ),
    "@rolldown/binding-openharmony-arm64": (
        "sha512-dUCXneZ87INUMyQ0D+C0HrEBNUPNXHaPmU5GTjyKTJEiussw9Kaj5Ln8UztPe4epV"
        "/ffvgNBEadksdYhmW6xJA=="
    ),
    "@rolldown/binding-win32-arm64-msvc": (
        "sha512-jByxb6qfd+bH1xUd0qnfFnb17i9sWBPY2tOavJ0l3tdr3OTu+Kvtm8cd/JV5nFt65"
        "7b1VqGltxg9olOEfofXWw=="
    ),
    "@rolldown/binding-win32-x64-msvc": (
        "sha512-/PzKqzAJ03i19oy2ItPvyvaVjOjBCNnfaJs8yvUdGBKmiESgnrJSQ2awd81QzFbbn"
        "Amu7YO9ZnJrDCb9VSJPRA=="
    ),
}


def _assert_patched_vite_toolchain(manifest: dict[str, Any], lock: dict[str, Any]) -> None:
    if manifest["devDependencies"].get("vite") != "8.3.3":
        raise ValueError("Vite manifest differs from the fixed profile")
    packages = lock["packages"]
    if packages[""]["devDependencies"].get("vite") != "8.3.3":
        raise ValueError("Vite lock root differs from the fixed profile")
    vite_node = "node_modules/vite"
    copies = {name for name in packages if name == vite_node or name.endswith("/" + vite_node)}
    if copies != {vite_node}:
        raise ValueError("Expected exactly one Vite package record")
    for name, fields in _VITE_TOOLCHAIN.items():
        node = packages.get("node_modules/" + name, {})
        for field, expected in fields.items():
            if node.get(field) != expected:
                raise ValueError(f"Vite toolchain {name} {field} differs")
    if packages[vite_node]["dependencies"].get("rolldown") != "~1.2.11":
        raise ValueError("Vite Rolldown dependency differs")
    rolldown = packages["node_modules/rolldown"]
    if rolldown["dependencies"].get("@oxc-project/types") != "=0.151.0":
        raise ValueError("Rolldown types dependency differs")
    expected_bindings = dict.fromkeys(_ROLLDOWN_BINDINGS, "1.2.11")
    if rolldown.get("optionalDependencies") != expected_bindings:
        raise ValueError("Rolldown native dependency edges differ")
    for name, integrity in _ROLLDOWN_BINDINGS.items():
        node = packages.get("node_modules/" + name, {})
        expected_node = {
            "version": "1.2.11",
            "resolved": (f"https://registry.npmjs.org/{name}/-/{name.split('/')[1]}-1.2.11.tgz"),
            "integrity": integrity,
        }
        for field, value in expected_node.items():
            if node.get(field) != value:
                raise ValueError(f"Rolldown native binding {name} {field} differs")


def _vite_fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    manifest: dict[str, Any] = {"devDependencies": {"vite": "8.3.3"}}
    packages: dict[str, Any] = {
        "": {"devDependencies": {"vite": "8.3.3"}},
        **{"node_modules/" + name: deepcopy(fields) for name, fields in _VITE_TOOLCHAIN.items()},
    }
    packages["node_modules/vite"]["dependencies"] = {"rolldown": "~1.2.11"}
    packages["node_modules/rolldown"]["dependencies"] = {"@oxc-project/types": "=0.151.0"}
    packages["node_modules/rolldown"]["optionalDependencies"] = dict.fromkeys(
        _ROLLDOWN_BINDINGS, "1.2.11"
    )
    for name, integrity in _ROLLDOWN_BINDINGS.items():
        packages["node_modules/" + name] = {
            "version": "1.2.11",
            "resolved": (f"https://registry.npmjs.org/{name}/-/{name.split('/')[1]}-1.2.11.tgz"),
            "integrity": integrity,
        }
    return manifest, {"lockfileVersion": 3, "packages": packages}


def test_frontend_vite_toolchain_matches_official_fixed_profile() -> None:
    root = Path(__file__).resolve().parents[1] / "frontend"
    manifest = json.loads((root / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
    _assert_patched_vite_toolchain(manifest, lock)


@pytest.mark.parametrize("version", ["8.3.0", "8.3.2"])
def test_vite_profile_rejects_affected_version(version: str) -> None:
    manifest, lock = _vite_fixture()
    _assert_patched_vite_toolchain(manifest, lock)
    lock["packages"]["node_modules/vite"]["version"] = version
    with pytest.raises(ValueError, match="Vite toolchain vite version"):
        _assert_patched_vite_toolchain(manifest, lock)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("integrity", "sha512-not-the-selected-registry-integrity"),
        ("resolved", "https://example.invalid/vite-8.3.3.tgz"),
    ],
)
def test_vite_profile_rejects_wrong_integrity_or_registry(field: str, replacement: str) -> None:
    manifest, lock = _vite_fixture()
    _assert_patched_vite_toolchain(manifest, lock)
    lock["packages"]["node_modules/vite"][field] = replacement
    with pytest.raises(ValueError, match=f"Vite toolchain vite {field}"):
        _assert_patched_vite_toolchain(manifest, lock)


def test_vite_profile_rejects_second_nested_copy() -> None:
    manifest, lock = _vite_fixture()
    _assert_patched_vite_toolchain(manifest, lock)
    stale = deepcopy(lock["packages"]["node_modules/vite"])
    stale["version"] = "8.3.2"
    lock["packages"]["node_modules/other/node_modules/vite"] = stale
    with pytest.raises(ValueError, match="exactly one Vite"):
        _assert_patched_vite_toolchain(manifest, lock)


@pytest.mark.parametrize(
    ("name", "version"),
    [("rolldown", "1.2.9"), ("@oxc-project/types", "0.150.0")],
)
def test_vite_profile_rejects_old_bundler_or_types(name: str, version: str) -> None:
    manifest, lock = _vite_fixture()
    _assert_patched_vite_toolchain(manifest, lock)
    lock["packages"]["node_modules/" + name]["version"] = version
    with pytest.raises(ValueError, match="Vite toolchain"):
        _assert_patched_vite_toolchain(manifest, lock)


@pytest.mark.parametrize("name", list(_ROLLDOWN_BINDINGS))
@pytest.mark.parametrize("missing", [True, False])
def test_vite_profile_rejects_missing_or_mismatched_native_binding(
    name: str, missing: bool
) -> None:
    manifest, lock = _vite_fixture()
    _assert_patched_vite_toolchain(manifest, lock)
    if missing:
        del lock["packages"]["node_modules/" + name]
    else:
        lock["packages"]["node_modules/" + name]["version"] = "1.2.9"
    with pytest.raises(ValueError, match="Rolldown native binding"):
        _assert_patched_vite_toolchain(manifest, lock)


@pytest.mark.parametrize("side", ["manifest", "lock"])
def test_vite_profile_rejects_manifest_lock_disagreement(side: str) -> None:
    manifest, lock = _vite_fixture()
    _assert_patched_vite_toolchain(manifest, lock)
    if side == "manifest":
        manifest["devDependencies"]["vite"] = "^8.3.0"
    else:
        lock["packages"][""]["devDependencies"]["vite"] = "^8.3.0"
    with pytest.raises(ValueError, match="Vite (manifest|lock root)"):
        _assert_patched_vite_toolchain(manifest, lock)
