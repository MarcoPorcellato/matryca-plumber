"""Public S3 inputs stay pinned to retained RC and baseline artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest


def test_source_must_match_exact_clean_commit_and_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.release_qualification import first_stable_s3_inputs as inputs

    source = tmp_path / "source"
    source.mkdir()
    observed = {
        "HEAD": "a" * 40,
        "HEAD^{tree}": "b" * 40,
        "status --porcelain --untracked-files=all": "",
    }
    monkeypatch.setattr(inputs, "_git_value", lambda _root, *args: observed[" ".join(args)])
    monkeypatch.setattr(
        inputs,
        "_installed_status",
        lambda _root: observed["status --porcelain --untracked-files=all"],
    )

    inputs.require_source(source, "a" * 40, "b" * 40)

    observed["HEAD"] = "c" * 40
    with pytest.raises(ValueError, match="source"):
        inputs.require_source(source, "a" * 40, "b" * 40)
    observed["HEAD"] = "a" * 40
    observed["HEAD^{tree}"] = "c" * 40
    with pytest.raises(ValueError, match="source"):
        inputs.require_source(source, "a" * 40, "b" * 40)
    observed["HEAD^{tree}"] = "b" * 40
    observed["status --porcelain --untracked-files=all"] = "?? unexpected.txt"
    with pytest.raises(ValueError, match="clean"):
        inputs.require_source(source, "a" * 40, "b" * 40)


def test_source_rejects_symlink_checkout(tmp_path: Path) -> None:
    from scripts.release_qualification.first_stable_s3_inputs import require_source

    source = tmp_path / "source"
    source.mkdir()
    link = tmp_path / "source-link"
    link.symlink_to(source, target_is_directory=True)

    with pytest.raises(ValueError, match="source"):
        require_source(link, "a" * 40, "b" * 40)


def test_baseline_identities_are_closed_and_pinned() -> None:
    from scripts.release_qualification.first_stable_s3_inputs import (
        _RC_BINDING,
        BASELINES,
        RC_COMMIT,
        RC_PUBLISHER_RUN,
        RC_TAG_OBJECT,
        RC_TREE,
        TAG,
    )

    assert TAG == "v2.1.0-rc.1"
    assert RC_TAG_OBJECT == "959ad1ce70d956aa6085bc5d1e0acc9853621e8b"
    assert RC_PUBLISHER_RUN == 45996481639
    assert RC_COMMIT == "4080f69ffc7d69edda27886530ce2932a6ee3fed"
    assert RC_TREE == "d9d2ed439e8be446ff4ec1604807f788935060c4"
    assert _RC_BINDING.version == "2.1.0rc1"
    assert _RC_BINDING.wheel_name == "matryca_plumber-2.1.0rc1-py3-none-any.whl"
    assert _RC_BINDING.wheel_size == 768_440
    assert _RC_BINDING.wheel_sha256 == (
        "e7fc25eca467bdc67da5b35540d2779618c8c022b2b56578934cde399d1b8a88"
    )
    assert _RC_BINDING.sdist_name == "matryca_plumber-2.1.0rc1.tar.gz"
    assert _RC_BINDING.sdist_size == 1_115_739
    assert _RC_BINDING.sdist_sha256 == (
        "2b728f46f1eb9ebaff6716053aa92675c6fa47dc90e4d6de22a6a5ace0de7867"
    )
    assert set(BASELINES) == {"2.0.0", "2.1.0a4"}
    assert BASELINES["2.0.0"].commit == "987446b8337f7abd308a9efe4abb834ce1acdc1b"
    assert BASELINES["2.0.0"].tree == "d164f054f84e7d6eb33a60efbaa6181403edf312"
    assert BASELINES["2.0.0"].wheel_name == "matryca_plumber-2.0.0-py3-none-any.whl"
    assert BASELINES["2.0.0"].wheel_sha256 == (
        "d3247aa1f4c2ea802c0bd94b180df61fef8d3f1faf62e0f3b920e483f74c4653"
    )
    assert BASELINES["2.0.0"].wheel_size == 593_914
    assert BASELINES["2.0.0"].pypi_url == (
        "https://files.pythonhosted.org/packages/e7/84/"
        "0a399141c2965c5c6961a0f83b94297c26620188d18d948de62608a6a4ff/"
        "matryca_plumber-2.0.0-py3-none-any.whl"
    )
    assert BASELINES["2.1.0a4"].commit == "1d884ddcbdb37ecdd0d4ad3ccb3e9a6d406e1bdd"
    assert BASELINES["2.1.0a4"].tree == "22bced0e8eef57595acdfed12933e53905f22a95"
    assert BASELINES["2.1.0a4"].wheel_name == "matryca_plumber-2.1.0a4-py3-none-any.whl"
    assert BASELINES["2.1.0a4"].wheel_sha256 == (
        "6d611de748d267bf377dd8f3266259ede71268fd39f30ac7136238cc99cdad56"
    )
    assert BASELINES["2.1.0a4"].wheel_size == 768_418
    assert BASELINES["2.1.0a4"].pypi_url == (
        "https://files.pythonhosted.org/packages/fd/11/"
        "9d2b2511981ebcc9fc6c2eecfd1a81377803efcefb26bcf93846c80012b8/"
        "matryca_plumber-2.1.0a4-py3-none-any.whl"
    )


def test_acquisition_rejects_unknown_baseline_before_creating_root(tmp_path: Path) -> None:
    from scripts.release_qualification.first_stable_s3_inputs import acquire_public

    root = tmp_path / "public-inputs"
    with pytest.raises(ValueError, match="baseline"):
        acquire_public(root, "2.1.0a5")
    assert not root.exists()


def test_acquisition_refuses_to_reuse_existing_root(tmp_path: Path) -> None:
    from scripts.release_qualification.first_stable_s3_inputs import acquire_public

    root = tmp_path / "public-inputs"
    root.mkdir()
    sentinel = root / "keep.txt"
    sentinel.write_text("preserve", encoding="ascii")

    with pytest.raises(ValueError, match="fresh"):
        acquire_public(root, None)

    assert sentinel.read_text(encoding="ascii") == "preserve"


def test_acquisition_materializes_exact_rc_handoff_and_only_selected_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.release_qualification import bundle
    from scripts.release_qualification import first_stable_s3_inputs as inputs

    wheel = b"synthetic wheel bytes"
    sdist = b"synthetic sdist bytes"
    binding = bundle.BundleBinding(
        inputs.RC_COMMIT,
        inputs.RC_TREE,
        "2.1.0rc1",
        "matryca_plumber-2.1.0rc1-py3-none-any.whl",
        len(wheel),
        hashlib.sha256(wheel).hexdigest(),
        "matryca_plumber-2.1.0rc1.tar.gz",
        len(sdist),
        hashlib.sha256(sdist).hexdigest(),
        "c" * 64,
        "d" * 64,
    )
    binding_bytes = binding.to_json().encode("ascii")
    manifest = bundle.canonical_manifest(binding, policy="og-alpha3")
    baseline = inputs.Baseline(
        commit="e" * 40,
        tree="f" * 40,
        wheel_name="matryca_plumber-2.0.0-py3-none-any.whl",
        wheel_sha256="1" * 64,
        wheel_size=0,
        pypi_url="https://files.example/baseline.whl",
    )
    baseline_bytes = b"synthetic baseline wheel"
    baseline = inputs.Baseline(
        commit=baseline.commit,
        tree=baseline.tree,
        wheel_name=baseline.wheel_name,
        wheel_sha256=hashlib.sha256(baseline_bytes).hexdigest(),
        wheel_size=len(baseline_bytes),
        pypi_url=baseline.pypi_url,
    )
    payloads = {
        "binding.json": binding_bytes,
        "SHA256SUMS": manifest,
        binding.wheel_name: wheel,
        binding.sdist_name: sdist,
        baseline.wheel_name: baseline_bytes,
    }
    monkeypatch.setattr(inputs, "_RC_BINDING", binding)
    monkeypatch.setattr(inputs, "_RC_BINDING_SHA256", hashlib.sha256(binding_bytes).hexdigest())
    monkeypatch.setattr(inputs, "_RC_BINDING_SIZE", len(binding_bytes))
    monkeypatch.setattr(inputs, "_RC_MANIFEST_SHA256", hashlib.sha256(manifest).hexdigest())
    monkeypatch.setattr(inputs, "BASELINES", {"2.0.0": baseline})
    monkeypatch.setattr(
        inputs,
        "_RC_URLS",
        {
            "binding.json": "https://github.example/binding.json",
            "SHA256SUMS": "https://github.example/SHA256SUMS",
            binding.wheel_name: "https://github.example/rc-wheel.whl",
            binding.sdist_name: "https://github.example/rc-sdist.tar.gz",
        },
    )
    monkeypatch.setattr(
        inputs,
        "_PYPI_URLS",
        {
            binding.wheel_name: "https://files.example/rc-wheel.whl",
            binding.sdist_name: "https://files.example/rc-sdist.tar.gz",
        },
    )
    calls: list[tuple[str, str, int, str, str, str]] = []

    def acquire(
        url: str, path: Path, size: int, sha256: str, kind: str, *, release_tag: str
    ) -> None:
        calls.append((url, path.name, size, sha256, kind, release_tag))
        path.write_bytes(payloads[path.name])

    handoffs: list[tuple[Path, Path, bundle.BundleBinding, str]] = []

    def verify_handoff(
        dist: Path, manifest_path: Path, expected: bundle.BundleBinding, *, policy: str
    ) -> None:
        handoffs.append((dist, manifest_path, expected, policy))
        assert (dist / expected.wheel_name).read_bytes() == wheel
        assert (dist / expected.sdist_name).read_bytes() == sdist
        assert manifest_path.read_bytes() == manifest

    monkeypatch.setattr(inputs, "_acquire_public", acquire)
    monkeypatch.setattr(inputs, "verify_handoff", verify_handoff)
    root = tmp_path / "public-inputs"

    result = inputs.acquire_public(root, "2.0.0")

    assert result == binding
    assert (root / "binding.json").read_bytes() == binding_bytes
    assert set(path.name for path in (root / "dist").iterdir()) == {
        binding.wheel_name,
        binding.sdist_name,
        "SHA256SUMS",
    }
    assert (root / baseline.wheel_name).read_bytes() == baseline_bytes
    assert (root / "pypi" / baseline.wheel_name).read_bytes() == baseline_bytes
    assert (root / "pypi" / binding.wheel_name).read_bytes() == wheel
    assert (root / "pypi" / binding.sdist_name).read_bytes() == sdist
    assert len([call for call in calls if call[4] == "pypi"]) == 3
    assert {call[0] for call in calls if call[4] == "pypi"} == {
        *inputs._PYPI_URLS.values(),
        baseline.pypi_url,
    }
    assert sum(call[4] == "github" for call in calls) == 4
    assert calls[-1] == (
        baseline.pypi_url,
        baseline.wheel_name,
        len(baseline_bytes),
        baseline.wheel_sha256,
        "pypi",
        "v2.0.0",
    )
    assert len(handoffs) == 1
    assert handoffs[0] == (root / "dist", root / "dist/SHA256SUMS", binding, "og-alpha3")


def test_acquisition_stops_on_pypi_and_github_byte_disagreement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.release_qualification import bundle
    from scripts.release_qualification import first_stable_s3_inputs as inputs

    wheel = b"github wheel"
    sdist = b"same sdist"
    binding = bundle.BundleBinding(
        inputs.RC_COMMIT,
        inputs.RC_TREE,
        "2.1.0rc1",
        "matryca_plumber-2.1.0rc1-py3-none-any.whl",
        len(wheel),
        hashlib.sha256(wheel).hexdigest(),
        "matryca_plumber-2.1.0rc1.tar.gz",
        len(sdist),
        hashlib.sha256(sdist).hexdigest(),
        "c" * 64,
        "d" * 64,
    )
    binding_bytes = binding.to_json().encode("ascii")
    manifest = bundle.canonical_manifest(binding, policy="og-alpha3")
    payloads = {
        "binding.json": binding_bytes,
        "SHA256SUMS": manifest,
        binding.wheel_name: wheel,
        binding.sdist_name: sdist,
    }
    monkeypatch.setattr(inputs, "_RC_BINDING", binding)
    monkeypatch.setattr(inputs, "_RC_BINDING_SHA256", hashlib.sha256(binding_bytes).hexdigest())
    monkeypatch.setattr(inputs, "_RC_BINDING_SIZE", len(binding_bytes))
    monkeypatch.setattr(inputs, "_RC_MANIFEST_SHA256", hashlib.sha256(manifest).hexdigest())
    monkeypatch.setattr(
        inputs,
        "_RC_URLS",
        {
            "binding.json": "https://github.example/binding.json",
            "SHA256SUMS": "https://github.example/SHA256SUMS",
            binding.wheel_name: "https://github.example/rc-wheel.whl",
            binding.sdist_name: "https://github.example/rc-sdist.tar.gz",
        },
    )
    monkeypatch.setattr(
        inputs,
        "_PYPI_URLS",
        {
            binding.wheel_name: "https://files.example/rc-wheel.whl",
            binding.sdist_name: "https://files.example/rc-sdist.tar.gz",
        },
    )

    def acquire(
        url: str, path: Path, size: int, sha256: str, kind: str, *, release_tag: str
    ) -> None:
        raw = payloads[path.name]
        if kind == "pypi" and path.name == binding.wheel_name:
            raw += b" changed"
        path.write_bytes(raw)

    monkeypatch.setattr(inputs, "_acquire_public", acquire)
    root = tmp_path / "public-inputs"

    with pytest.raises(ValueError, match="fixed pin"):
        inputs.acquire_public(root, None)
    assert not (root / "dist" / binding.wheel_name).is_symlink()
