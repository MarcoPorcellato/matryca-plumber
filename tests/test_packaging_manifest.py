from pathlib import Path


def test_manifest_excludes_compiled_python_artifacts() -> None:
    manifest = Path(__file__).parents[1] / "MANIFEST.in"

    assert "global-exclude *.py[cod]" in manifest.read_text(encoding="utf-8")
