"""First-stable lock export must yield a closed native wheel-only profile."""

import pytest

_CLOSURE = (
    "anyio==4.14.2 \\\n    --hash=sha256:" + "a" * 64 + "\n"
    "pywin32==311 ; sys_platform == 'win32' \\\n    --hash=sha256:" + "b" * 64 + "\n"
)


def test_native_inputs_have_explicit_parser_and_no_windows_dependencies() -> None:
    from scripts.release_qualification.first_stable_profiles import resolve_profile

    profile = resolve_profile(_CLOSURE, "current", "macos-arm64", "3.13.18")
    assert profile.packages == (
        ("anyio", "4.14.2"),
        ("logseq-matryca-parser", "1.11.4"),
    )
    assert profile.requirements == (
        f"anyio==4.14.2 --hash=sha256:{'a' * 64}\n"
        "logseq-matryca-parser==1.11.4 "
        "--hash=sha256:7c62c5690cc7f11e35b365d5659eecec743e30da389c5306fef12c1883491f39\n"
    )


@pytest.mark.parametrize(
    "extra",
    [
        "--index-url=https://custom.invalid/simple",
        "-r another-file.txt",
        "thing==1.0",
        "thing>=1.0 --hash=sha256:" + "c" * 64,
        "thing @ https://custom.invalid/artifact --hash=sha256:" + "c" * 64,
        "thing==1.0 ; platform_release == '1' --hash=sha256:" + "c" * 64,
        "logseq-matryca-parser==1.9.0 --hash=sha256:" + "c" * 64,
        "anyio==4.14.2 --hash=sha256:" + "a" * 64,
    ],
)
def test_unlocked_or_ambiguous_exports_are_rejected(extra: str) -> None:
    from scripts.release_qualification.first_stable_profiles import resolve_profile

    with pytest.raises(ValueError):
        resolve_profile(_CLOSURE + extra + "\n", "minimum", "linux-x86_64", "3.12.16")
