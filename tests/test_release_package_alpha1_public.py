"""Synthetic public-byte admission; these tests perform no public downloads."""

from __future__ import annotations

import copy
import hashlib
import importlib
import importlib.util
import io
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO = "MarcoPorcellato/matryca-plumber"
TAG = "v2.1.0-alpha.1"
SOURCE = "a" * 40
TREE = "b" * 40
NAMES = (
    "matryca_plumber-2.1.0a1-py3-none-any.whl",
    "matryca_plumber-2.1.0a1.tar.gz",
    "binding.json",
    "content-ledger.json",
    "canonical-build.json",
    "SHA256SUMS",
)


def _public() -> Any:
    name = "scripts.release_qualification.alpha1_public"
    assert importlib.util.find_spec(name) is not None, "Public artifact admission is missing."
    return importlib.import_module(name)


def _inputs() -> tuple[Any, dict[str, Any]]:
    public = _public()
    context = public.PublicContext(SOURCE, TREE, "123", "456")
    release_assets = [
        {
            "id": index + 1,
            "name": name,
            "size": len(name.encode()),
            "digest": "sha256:" + hashlib.sha256(name.encode()).hexdigest(),
            "state": "uploaded",
            "url": f"https://api.github.com/repos/{REPO}/releases/assets/{index + 1}",
            "browser_download_url": f"https://github.com/{REPO}/releases/download/{TAG}/{name}",
        }
        for index, name in enumerate(NAMES)
    ]
    metadata = {
        "main": {"object": {"sha": SOURCE}},
        "tag": {"ref": "refs/tags/" + TAG, "object": {"type": "tag", "sha": "c" * 40}},
        "tag_object": {
            "sha": "c" * 40,
            "tag": TAG,
            "object": {"type": "commit", "sha": SOURCE},
            "verification": {"verified": True},
        },
        "publisher": {
            "id": 123,
            "run_attempt": 1,
            "event": "push",
            "head_sha": SOURCE,
            "head_branch": TAG,
            "path": ".github/workflows/release.yml",
            "status": "completed",
            "conclusion": "success",
            "repository": {"id": 1241185104, "full_name": REPO},
        },
        "verifier": {
            "id": 456,
            "run_attempt": 1,
            "event": "workflow_dispatch",
            "head_sha": SOURCE,
            "head_branch": "main",
            "path": ".github/workflows/og-public-artifact-qualification.yml",
            "status": "in_progress",
            "repository": {"id": 1241185104, "full_name": REPO},
        },
        "release": {
            "tag_name": TAG,
            "draft": False,
            "prerelease": True,
            "assets": release_assets,
        },
        "pypi": {
            "info": {"name": "matryca-plumber", "version": "2.1.0a1"},
            "urls": [
                {
                    "filename": name,
                    "size": len(name.encode()),
                    "digests": {"sha256": hashlib.sha256(name.encode()).hexdigest()},
                    "yanked": False,
                    "packagetype": kind,
                    "url": "https://files.pythonhosted.org/packages/ab/" + name,
                }
                for name, kind in zip(NAMES[:2], ("bdist_wheel", "sdist"), strict=True)
            ],
        },
    }
    return context, metadata


def test_public_metadata_accepts_only_the_actual_original_pair() -> None:
    context, metadata = _inputs()
    result = _public().verify_metadata(context, metadata)
    assert set(result) == set(NAMES)
    assert result[NAMES[0]]["sha256"] == hashlib.sha256(NAMES[0].encode()).hexdigest()


@pytest.mark.parametrize(
    "mutation",
    [
        "main",
        "source",
        "publisher-attempt",
        "publisher-event",
        "workflow",
        "publisher-status",
        "publisher-branch",
        "verifier-id",
        "verifier-attempt",
        "verifier-source",
        "verifier-workflow",
        "repository",
        "tag-object",
        "tag-signature",
        "tag-ref",
        "release-tag",
        "draft",
        "prerelease",
        "missing",
        "extra",
        "duplicate",
        "size-bool",
        "metadata-oversize",
        "digest",
        "asset-host",
        "asset-path",
        "pypi-extra",
        "pypi-missing",
        "pypi-yanked",
        "pypi-version",
        "pypi-size",
        "pypi-sha",
        "pypi-kind",
        "pypi-host",
        "pypi-duplicate",
    ],
)
def test_public_metadata_rejects_wrong_or_incomplete_identities(mutation: str) -> None:
    context, original = _inputs()
    public = _public()
    public.verify_metadata(context, original)
    value = copy.deepcopy(original)
    updates = {
        "main": ("main", "object", "sha", "0" * 40),
        "source": ("publisher", None, "head_sha", "0" * 40),
        "publisher-attempt": ("publisher", None, "run_attempt", 2),
        "publisher-event": ("publisher", None, "event", "workflow_dispatch"),
        "workflow": ("publisher", None, "path", ".github/workflows/other.yml"),
        "publisher-status": ("publisher", None, "conclusion", "failure"),
        "publisher-branch": ("publisher", None, "head_branch", "main"),
        "verifier-id": ("verifier", None, "id", 123),
        "verifier-attempt": ("verifier", None, "run_attempt", True),
        "verifier-source": ("verifier", None, "head_sha", "0" * 40),
        "verifier-workflow": ("verifier", None, "path", ".github/workflows/release.yml"),
        "repository": ("publisher", "repository", "id", 99),
        "tag-object": ("tag_object", "object", "sha", "0" * 40),
        "tag-signature": ("tag_object", "verification", "verified", False),
        "tag-ref": ("tag", None, "ref", "refs/heads/main"),
        "release-tag": ("release", None, "tag_name", "v2.1.0-alpha.2"),
        "draft": ("release", None, "draft", True),
        "prerelease": ("release", None, "prerelease", False),
    }
    if mutation in updates:
        root, nested, field, replacement = updates[mutation]
        target = value[root] if nested is None else value[root][nested]
        target[field] = replacement
    elif mutation in ("missing", "extra", "duplicate"):
        assets = value["release"]["assets"]
        if mutation == "missing":
            assets.pop()
        else:
            assets.append(copy.deepcopy(assets[0]))
            if mutation == "extra":
                assets[-1]["name"] = "unexpected.json"
    elif mutation in ("size-bool", "metadata-oversize", "digest", "asset-host", "asset-path"):
        asset = value["release"]["assets"][2]
        if mutation == "size-bool":
            asset["size"] = True
        elif mutation == "metadata-oversize":
            asset["size"] = 2_097_153
        elif mutation == "digest":
            asset["digest"] = "sha256:not-a-digest"
        elif mutation == "asset-host":
            asset["url"] = "https://attacker.invalid/file"
        else:
            asset["url"] = "https://api.github.com/repos/other/repo/releases/assets/3"
    else:
        urls = value["pypi"]["urls"]
        if mutation == "pypi-extra":
            urls.append({**urls[0], "filename": "extra.whl"})
        elif mutation == "pypi-missing":
            urls.pop()
        elif mutation == "pypi-duplicate":
            urls[1] = copy.deepcopy(urls[0])
        elif mutation == "pypi-yanked":
            urls[0]["yanked"] = True
        elif mutation == "pypi-version":
            value["pypi"]["info"]["version"] = "2.1.0a2"
        elif mutation == "pypi-size":
            urls[0]["size"] += 1
        elif mutation == "pypi-sha":
            urls[0]["digests"]["sha256"] = "0" * 64
        elif mutation == "pypi-kind":
            urls[0]["packagetype"] = "sdist"
        elif mutation == "pypi-host":
            urls[0]["url"] = "https://attacker.invalid/package"
    with pytest.raises(ValueError):
        public.verify_metadata(context, value)


def _attestation(name: str) -> bytes:
    certificate = {
        "issuer": "https://token.actions.githubusercontent.com",
        "subjectAlternativeName": (
            f"https://github.com/{REPO}/.github/workflows/release.yml@refs/tags/{TAG}"
        ),
        "buildSignerURI": (
            f"https://github.com/{REPO}/.github/workflows/release.yml@refs/tags/{TAG}"
        ),
        "buildSignerDigest": SOURCE,
        "sourceRepositoryURI": "https://github.com/" + REPO,
        "sourceRepositoryDigest": SOURCE,
        "sourceRepositoryRef": "refs/tags/" + TAG,
        "sourceRepositoryIdentifier": "1241185104",
        "sourceRepositoryOwnerIdentifier": "220745401",
        "sourceRepositoryVisibilityAtSigning": "public",
        "runnerEnvironment": "github-hosted",
        "buildTrigger": "push",
        "runInvocationURI": f"https://github.com/{REPO}/actions/runs/123/attempts/1",
    }
    return json.dumps(
        [
            {
                "verificationResult": {
                    "signature": {"certificate": certificate},
                    "verifiedTimestamps": [{"type": "Tlog", "timestamp": "2026-10-18T00:00:00Z"}],
                    "statement": {
                        "_type": "https://in-toto.io/Statement/v1",
                        "predicateType": "https://slsa.dev/provenance/v1",
                        "subject": [
                            {
                                "name": name,
                                "digest": {"sha256": hashlib.sha256(name.encode()).hexdigest()},
                            }
                        ],
                        "predicate": {"run_id": "123"},
                    },
                }
            }
        ]
    ).encode()


@pytest.mark.parametrize(
    "field",
    [
        None,
        "issuer",
        "subjectAlternativeName",
        "buildSignerURI",
        "buildSignerDigest",
        "sourceRepositoryURI",
        "sourceRepositoryDigest",
        "sourceRepositoryRef",
        "sourceRepositoryIdentifier",
        "sourceRepositoryOwnerIdentifier",
        "sourceRepositoryVisibilityAtSigning",
        "runnerEnvironment",
        "buildTrigger",
        "runInvocationURI",
        "subject",
        "timestamps",
        "predicate-type",
    ],
)
def test_attestation_uses_signed_certificate_invocation_not_predicate(field: str | None) -> None:
    context, _ = _inputs()
    public = _public()
    raw = _attestation(NAMES[0])
    sha = hashlib.sha256(NAMES[0].encode()).hexdigest()
    public.verify_attestation(context, NAMES[0], sha, raw)
    value = json.loads(raw)
    result = value[0]["verificationResult"]
    if field is None:
        result["statement"]["predicate"] = {"run_id": "999"}
        public.verify_attestation(context, NAMES[0], sha, json.dumps(value).encode())
        return
    if field == "subject":
        result["statement"]["subject"][0]["digest"]["sha256"] = "0" * 64
    elif field == "timestamps":
        result["verifiedTimestamps"] = []
    elif field == "predicate-type":
        result["statement"]["predicateType"] = "wrong"
    else:
        result["signature"]["certificate"][field] = "wrong"
    with pytest.raises(ValueError):
        public.verify_attestation(context, NAMES[0], sha, json.dumps(value).encode())


@pytest.mark.parametrize(
    "url",
    [
        "http://files.pythonhosted.org/packages/a.whl",
        "https://user:secret@files.pythonhosted.org/packages/a.whl",
        "https://files.pythonhosted.org:444/packages/a.whl",
        "https://files.pythonhosted.org.attacker.invalid/packages/a.whl",
        "https://files.pythonhosted.org/packages/a.whl#fragment",
    ],
)
def test_public_urls_reject_unsafe_origins(url: str) -> None:
    public = _public()
    public.validate_url("https://files.pythonhosted.org/packages/a.whl", "pypi")
    with pytest.raises(ValueError):
        public.validate_url(url, "pypi")


@pytest.mark.parametrize("failure", [None, "size", "hash", "redirect-host", "redirect-loop"])
def test_download_enforces_byte_and_redirect_limits_without_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str | None,
) -> None:
    public = _public()
    payload = b"synthetic"
    response = io.BytesIO(payload)
    response.headers = {}  # type: ignore[attr-defined]
    response.status = 200  # type: ignore[attr-defined]
    monkeypatch.setattr(public, "_open", lambda *_args, **_kwargs: response)
    size = len(payload) - (1 if failure == "size" else 0)
    sha = "0" * 64 if failure == "hash" else hashlib.sha256(payload).hexdigest()
    if failure in ("redirect-host", "redirect-loop"):
        from urllib.error import HTTPError

        target = (
            "https://attacker.invalid/file"
            if failure == "redirect-host"
            else "https://release-assets.githubusercontent.com/file"
        )

        def redirect(*_args: Any, **_kwargs: Any) -> Any:
            from email.message import Message

            headers = Message()
            headers["Location"] = target
            raise HTTPError("https://api.github.com", 302, "redirect", headers, None)

        monkeypatch.setattr(public, "_open", redirect)
    path = tmp_path / "asset"
    if failure:
        with pytest.raises(ValueError):
            public.fetch_file(
                f"https://api.github.com/repos/{REPO}/releases/assets/1",
                path,
                size,
                sha,
                "github",
            )
    else:
        public.fetch_file(
            f"https://api.github.com/repos/{REPO}/releases/assets/1",
            path,
            size,
            sha,
            "github",
        )
        assert path.read_bytes() == payload


@pytest.mark.parametrize(
    "build_failure",
    [
        None,
        "source_commit",
        "source_tree",
        "binding_sha256",
        "build_lock_sha256",
        "packages",
        "python_implementation",
        "python_version",
        "python_executable_sha256",
        "uv_version",
        "uv_sha256",
        "node_version",
        "npm_version",
    ],
)
def test_mocked_public_admission_binds_originals_commands_and_retained_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    build_failure: str | None,
) -> None:
    from scripts.release_qualification.bundle import BundleBinding, canonical_manifest

    public = _public()
    _, metadata = _inputs()
    payloads = {name: name.encode() for name in NAMES}
    binding = BundleBinding(
        SOURCE,
        TREE,
        "2.1.0a1",
        NAMES[0],
        len(payloads[NAMES[0]]),
        hashlib.sha256(payloads[NAMES[0]]).hexdigest(),
        NAMES[1],
        len(payloads[NAMES[1]]),
        hashlib.sha256(payloads[NAMES[1]]).hexdigest(),
        "d" * 64,
        "e" * 64,
    )
    payloads["binding.json"] = binding.to_json().encode()
    payloads["content-ledger.json"] = b'{"synthetic":true}'
    matrix_context = public.matrix.MatrixContext(
        binding,
        "456",
        1,
        {},
        {},
        "3" * 64,
        "4" * 64,
        (("setuptools", "84.0.0"), ("wheel", "0.48.0")),
        (),
    )
    build = {
        "source_commit": SOURCE,
        "source_tree": TREE,
        "binding_sha256": public.matrix.digest(asdict(binding)),
        "build_lock_sha256": "3" * 64,
        "python_implementation": "CPython",
        "python_version": "3.12.13",
        "python_executable_sha256": "6" * 64,
        "uv_version": "0.12.19",
        "uv_sha256": "7" * 64,
        "target_os": "linux",
        "target_architecture": "x64",
        "node_version": "v22.15.0",
        "npm_version": "10.8.0",
        "packages": [
            {"name": "setuptools", "version": "84.0.0"},
            {"name": "wheel", "version": "0.48.0"},
        ],
    }
    if build_failure is not None:
        build[build_failure] = "unsupported"
    payloads["canonical-build.json"] = json.dumps(build).encode()
    payloads["SHA256SUMS"] = canonical_manifest(binding, policy="og-alpha1")
    for asset in metadata["release"]["assets"]:
        payload = payloads[asset["name"]]
        asset.update(size=len(payload), digest="sha256:" + hashlib.sha256(payload).hexdigest())
    for item in metadata["pypi"]["urls"]:
        payload = payloads[item["filename"]]
        item.update(size=len(payload), digests={"sha256": hashlib.sha256(payload).hexdigest()})
    # Real GitHub tag objects include these additional response fields.
    metadata["tag"]["object"]["url"] = "https://api.github.com/tag-object"
    metadata["tag_object"]["object"]["url"] = "https://api.github.com/commit-object"
    gh = tmp_path / "synthetic-gh"
    gh.write_bytes(b"not-executed")
    monkeypatch.setattr(public.shutil, "which", lambda _name: str(gh))
    monkeypatch.setattr(
        public.bundle, "_git_value", lambda _path, arg: SOURCE if arg == "HEAD" else TREE
    )
    monkeypatch.setattr(public, "installed_status", lambda _source: "")
    monkeypatch.setattr(public.bundle, "build_binding", lambda *_args, **_kwargs: binding)

    def source_context(root: Path, actual: Any, run_id: str, attempt: int) -> Any:
        assert root == tmp_path / "source" and actual == binding
        assert run_id == "456" and attempt == 1
        return matrix_context

    monkeypatch.setattr(public.matrix, "source_context", source_context)
    handoffs: list[Path] = []

    def synthetic_handoff(dist: Path, manifest: Path, expected: Any, *, policy: str) -> None:
        # This composition fixture is deliberately bytes, not a real wheel.
        # The unchanged archive verifier is a separately tested boundary.
        assert policy == "og-alpha1" and expected == binding
        assert {path.name for path in dist.iterdir()} == {*NAMES[:2], "SHA256SUMS"}
        assert manifest.read_bytes() == payloads["SHA256SUMS"]
        for name in NAMES[:2]:
            assert (dist / name).read_bytes() == payloads[name]
        handoffs.append(dist)

    monkeypatch.setattr(public.bundle, "verify_handoff", synthetic_handoff)
    calls: list[list[str]] = []
    acquisitions: list[str] = []

    def command(argv: list[str], path: Path, timeout: int = 30) -> bytes:
        calls.append(argv)
        if argv[1] == "api":
            route = argv[2]
            key = {
                f"repos/{REPO}/git/ref/heads/main": "main",
                f"repos/{REPO}/git/ref/tags/{TAG}": "tag",
                f"repos/{REPO}/git/tags/" + "c" * 40: "tag_object",
                f"repos/{REPO}/actions/runs/123": "publisher",
                f"repos/{REPO}/actions/runs/456": "verifier",
                f"repos/{REPO}/releases/tags/{TAG}": "release",
            }[route]
            raw = json.dumps(metadata[key]).encode()
        else:
            assert argv[1:3] == ["attestation", "verify"] and timeout == 120
            assert "--cert-identity" in argv and "--signer-workflow" not in argv
            assert argv[argv.index("--source-digest") + 1] == SOURCE
            assert argv[argv.index("--signer-digest") + 1] == SOURCE
            name = Path(argv[3]).name
            value = json.loads(_attestation(name))
            value[0]["verificationResult"]["statement"]["subject"][0]["digest"]["sha256"] = (
                hashlib.sha256(payloads[name]).hexdigest()
            )
            raw = json.dumps(value).encode()
        path.write_bytes(raw)
        return raw

    def acquire(url: str, path: Path, size: int, sha256: str, kind: str) -> None:
        acquisitions.append(url)
        if kind == "pypi-metadata":
            raw = json.dumps(metadata["pypi"]).encode()
        else:
            raw = payloads[path.name]
            assert size == len(raw) and hashlib.sha256(raw).hexdigest() == sha256
        path.write_bytes(raw)

    monkeypatch.setattr(public, "_command", command)
    monkeypatch.setattr(public, "_acquire", acquire)
    for key, value in {
        "GITHUB_REPOSITORY": REPO,
        "GITHUB_REPOSITORY_ID": "1241185104",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_RUN_ID": "456",
        "GITHUB_SHA": SOURCE,
    }.items():
        monkeypatch.setenv(key, value)
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "public-bundle"
    if build_failure is not None:
        with pytest.raises(ValueError, match="Canonical build|Canonical frontend"):
            public.admit_public(source, output, "123")
        assert not (output / "public-input.json").exists()
        assert handoffs == []
        return
    record = public.admit_public(source, output, "123")
    assert handoffs == [output / "dist"]
    assert len(acquisitions) == len(set(acquisitions)) == 9
    assert sum(argv[1:3] == ["attestation", "verify"] for argv in calls) == 6
    context = SimpleNamespace(binding=binding, run_id="456", run_attempt=1)
    public.verify_retained(output, context, record)
    (output / "dist" / NAMES[0]).write_bytes(b"tampered")
    with pytest.raises(ValueError):
        public.verify_retained(output, context, record)


def test_public_workflow_has_no_rebuild_or_diagnostic_substitution() -> None:
    path = ROOT / ".github/workflows/og-public-artifact-qualification.yml"
    assert path.is_file(), "Public-input workflow is missing."
    value = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
    assert set(value["on"]) == {"workflow_dispatch"}
    assert set(value["on"]["workflow_dispatch"]["inputs"]) == {"source_sha", "publication_run"}
    jobs = value["jobs"]
    assert set(jobs) == {
        "admission",
        "source-controls",
        "windows-refusal",
        "linux312",
        "linux313",
        "macos312",
        "macos313",
        "aggregate",
    }
    text = path.read_text()
    assert "alpha-public-admit" in text and "alpha-public-aggregate" in text
    assert "alpha-build" not in text and "build_release_artifacts" not in text
    assert "npm ci" not in text and "Build OG alpha" not in text
    assert "EXPECTED_PUBLIC_JSON" in text
    assert "publication_run" in text and "digest-mismatch: error" in text
    assert "refs/heads/main" in text and "GITHUB_RUN_ATTEMPT" in text
    assert jobs["admission"]["name"] == "Admit public OG alpha"
    assert all(int(job["timeout-minutes"]) <= 35 for job in jobs.values())
    assert "actions: read" in text and "attestations: read" in text


def test_publisher_stages_six_attested_assets_but_only_two_distributions() -> None:
    value = yaml.load((ROOT / ".github/workflows/release.yml").read_text(), Loader=yaml.BaseLoader)
    build = value["jobs"]["build-release"]
    alpha = [step for step in build["steps"] if "alpha" in step.get("name", "").lower()]
    assert alpha, "Alpha publisher bridge is missing."
    text = "\n".join(step.get("run", "") for step in alpha)
    assert "alpha-build" in text and "--build-python" in text
    assert "release-qualification-build" in text and "--locked" in text
    attest = next(
        step for step in build["steps"] if step.get("name") == "Attest alpha originals and evidence"
    )
    subjects = attest["with"]["subject-path"]
    for name in (
        "binding.json",
        "content-ledger.json",
        "canonical-build.json",
        "SHA256SUMS",
        "*.whl",
        "*.tar.gz",
    ):
        assert name in subjects
    upload = next(
        step for step in build["steps"] if step.get("name") == "Preserve alpha publication bundle"
    )
    assert int(upload["with"]["retention-days"]) >= 14
    publish = value["jobs"]["publish-release"]
    stage = next(
        step
        for step in publish["steps"]
        if step.get("name") == "Stage alpha distribution-only PyPI directory"
    )
    assert "pypi-dist" in stage["run"] and "sha256sum" in stage["run"]
    pypi = next(
        step for step in publish["steps"] if step.get("name") == "Publish alpha originals to PyPI"
    )
    assert pypi["with"] == {"packages-dir": "pypi-dist/"}
    assert TAG in text or any(TAG in str(step.get("if", "")) for step in alpha)


@pytest.mark.parametrize(
    ("workflow", "job_name", "checksum"),
    [
        ("og-public-artifact-qualification.yml", name, checksum)
        for name, checksum in (
            ("admission", "23bf5552d220e0842b65c862097b2ebaeba0064b74eda5e565e77fd25969d8c8"),
            ("source-controls", "23bf5552d220e0842b65c862097b2ebaeba0064b74eda5e565e77fd25969d8c8"),
            ("windows-refusal", "6dbb02d79e419522f1c500f0adb1cddcff0cda7d59b0d66ea7f5e3b4a1b2f5f0"),
            ("linux312", "23bf5552d220e0842b65c862097b2ebaeba0064b74eda5e565e77fd25969d8c8"),
            ("linux313", "23bf5552d220e0842b65c862097b2ebaeba0064b74eda5e565e77fd25969d8c8"),
            ("macos312", "a9a8df1eedeb192f2e47e40e2faabfb387db4b850209118786d42f89dde3e0ba"),
            ("macos313", "a9a8df1eedeb192f2e47e40e2faabfb387db4b850209118786d42f89dde3e0ba"),
            ("aggregate", "23bf5552d220e0842b65c862097b2ebaeba0064b74eda5e565e77fd25969d8c8"),
        )
    ]
    + [
        ("release.yml", name, "23bf5552d220e0842b65c862097b2ebaeba0064b74eda5e565e77fd25969d8c8")
        for name in ("verify", "build-release")
    ],
)
def test_qualified_workflows_authenticate_uv_before_use(
    workflow: str,
    job_name: str,
    checksum: str,
) -> None:
    value = yaml.load((ROOT / ".github/workflows" / workflow).read_text(), Loader=yaml.BaseLoader)
    steps = value["jobs"][job_name]["steps"]
    if workflow == "release.yml":
        steps = [
            step for step in steps if step.get("if") == "${{ github.ref_name == 'v2.1.0-alpha.1' }}"
        ]
    setups = [
        (index, step)
        for index, step in enumerate(steps)
        if step.get("uses", "").startswith("astral-sh/setup-uv@")
    ]
    assert len(setups) == 1, "Exact-alpha uv bootstrap is missing."
    setup_index, setup = setups[0]
    assert setup["with"].get("checksum") == checksum, "Independent archive pin is missing."
    assert setup["with"]["version"] == "0.12.19"
    assert setup["with"]["download-from-astral-mirror"] == "false"
    assert setup["with"]["enable-cache"] == "false"
    root = "${{ runner.temp }}/alpha-uv-tool-cache"
    assert setup["env"]["RUNNER_TOOL_CACHE"] == root
    prepare = next(
        (
            i
            for i, step in enumerate(steps)
            if step.get("name") == "Prepare fresh uv acquisition root"
        ),
        -1,
    )
    verify = next(
        (i for i, step in enumerate(steps) if step.get("name") == "Verify selected uv acquisition"),
        -1,
    )
    provision = next(
        (i for i, step in enumerate(steps) if "uv python install 3.12" in step.get("run", "")), -1
    )
    assert 0 <= prepare < setup_index < verify < provision, "Acquisition must precede provisioning."
    assert steps[prepare]["env"]["RUNNER_TOOL_CACHE"] == root
    assert 'test ! -e "$cache"' in steps[prepare]["run"]
    assert 'test ! -L "$cache"' in steps[prepare]["run"]
    assert steps[verify]["env"]["RUNNER_TOOL_CACHE"] == root
    assert steps[verify]["env"]["UV_ARCHIVE_SHA256"] == checksum
    assert steps[verify]["env"]["UV_SELECTED_PATH"] == "${{ steps.setup-uv.outputs.uv-path }}"
    script = steps[verify]["run"]
    assert 'test ! -L "$selected"' in script
    assert '"$cache"/*)' in script and "executable_sha256" in script
    assert "--version" in script and "0.12.19" in script
    assert int(steps[provision]["timeout-minutes"]) <= 5
    assert steps[provision]["env"]["UV_PYTHON_DOWNLOADS"] == "manual"
