"""Synthetic public-byte admission; these tests perform no public downloads."""

from __future__ import annotations

import copy
import hashlib
import importlib
import importlib.util
import io
import json
import shutil
import threading
from collections.abc import Iterator
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NoReturn

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO = "MarcoPorcellato/matryca-plumber"
TAG = "v2.1.0-alpha.3"
SOURCE = "a" * 40
TREE = "b" * 40
NAMES = (
    "matryca_plumber-2.1.0a3-py3-none-any.whl",
    "matryca_plumber-2.1.0a3.tar.gz",
    "binding.json",
    "content-ledger.json",
    "canonical-build.json",
    "SHA256SUMS",
)


@pytest.fixture
def commit_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[str, str, dict[str, bytes], list[str]]]:
    """Exercise the installed CLI's real projection against loopback bytes only."""
    gh = shutil.which("gh")
    assert gh is not None, "The installed provenance CLI is required for this boundary test."
    documents: dict[str, bytes] = {}
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(self.path)
            body = documents[self.path]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *args: Any) -> None:
            return

    for name in (
        "GH_DEBUG",
        "GH_HOST",
        "GITHUB_TOKEN",
        "GH_ENTERPRISE_TOKEN",
        "GITHUB_ENTERPRISE_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GH_TOKEN", "synthetic-loopback-token")
    monkeypatch.setenv("GH_CONFIG_DIR", str(tmp_path / "empty-cli-config"))
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05})
        thread.start()
        try:
            yield gh, f"http://127.0.0.1:{server.server_port}/commit", documents, requests
        finally:
            server.shutdown()
            thread.join(timeout=3)
            assert not thread.is_alive(), "Synthetic HTTP reader did not stop."


@pytest.mark.parametrize(
    "mutation", [None, "sha", "tree", "signature", "reason", "missing", "oversized"]
)
def test_recovery_commit_projection_uses_real_cli_and_preserves_signature_gates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    commit_api: tuple[str, str, dict[str, bytes], list[str]],
    mutation: str | None,
) -> None:
    from tests.test_release_package_alpha3_recovery import _public_inputs

    public = _public()
    context, metadata = _public_inputs()
    gh, endpoint, documents, requests = commit_api
    full = copy.deepcopy(metadata["verifier_commit"])
    full["files"] = [{"filename": "synthetic.py", "patch": "x" * 100_000}]
    full["commit"]["verification"].update(signature="synthetic-signature", payload="signed-payload")
    if mutation == "sha":
        full["sha"] = "f" * 40
    elif mutation == "tree":
        full["commit"]["tree"]["sha"] = "f" * 40
    elif mutation == "signature":
        full["commit"]["verification"]["verified"] = False
    elif mutation == "reason":
        full["commit"]["verification"]["reason"] = "invalid"
    elif mutation == "missing":
        full.pop("sha")
    elif mutation == "oversized":
        full["commit"]["verification"]["payload"] = "x" * 100_000
    documents["/commit"] = json.dumps(full).encode()
    assert len(documents["/commit"]) > 65_536
    actual_command = public._command

    class CommitObserved(Exception):
        pass

    def command(argv: list[str], path: Path, timeout: int = 30) -> bytes:
        if path.stem == "verifier_commit":
            assert argv[:3] == [
                gh,
                "api",
                f"repos/{REPO}/commits/{context.recovery.verifier_commit}",
            ]
            actual_command([gh, "api", endpoint, *argv[3:]], path, timeout)
            raise CommitObserved
        raw = json.dumps(metadata[path.stem]).encode()
        path.write_bytes(raw)
        return raw

    monkeypatch.setattr(public, "_command", command)
    monkeypatch.setattr(
        public.bundle,
        "_git_value",
        lambda _root, arg: context.source_commit if arg == "HEAD" else context.source_tree,
    )
    monkeypatch.setattr(public, "installed_status", lambda _root: "")
    for name, value in {
        "GITHUB_REPOSITORY": REPO,
        "GITHUB_REPOSITORY_ID": "1241185104",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_RUN_ID": context.verifier_run,
        "GITHUB_SHA": context.workflow_commit,
    }.items():
        monkeypatch.setenv(name, value)
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "public-bundle"
    if mutation == "oversized":
        with pytest.raises(ValueError, match="capture limit"):
            public.admit_public(source, output, context.publisher_run, recovery=context.recovery)
    else:
        with pytest.raises(CommitObserved):
            public.admit_public(source, output, context.publisher_run, recovery=context.recovery)
        raw = (output / "public-provenance/verifier_commit.json").read_bytes()
        assert len(raw) < 65_536
        projected = json.loads(raw)
        assert set(projected) == {"sha", "commit"}
        assert projected["commit"] == full["commit"]
        metadata["verifier_commit"] = projected
        if mutation is None:
            assert len(public.verify_metadata(context, metadata)) == 6
        else:
            with pytest.raises(ValueError, match="Recovery verifier"):
                public.verify_metadata(context, metadata)
    assert requests == ["/commit"]
    assert not (output / "public-input.json").exists()


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
            "info": {"name": "matryca-plumber", "version": "2.1.0a3"},
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
    "publisher_suffix",
    ("", "@main", "@v2.1.0-alpha.3", "@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
)
@pytest.mark.parametrize(
    "verifier_suffix",
    ("", "@main", "@v2.1.0-alpha.3", "@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
)
def test_public_metadata_accepts_selected_source_workflow_selectors(
    publisher_suffix: str, verifier_suffix: str
) -> None:
    context, metadata = _inputs()
    metadata["publisher"]["path"] = ".github/workflows/release.yml" + publisher_suffix
    metadata["verifier"]["path"] = (
        ".github/workflows/og-public-artifact-qualification.yml" + verifier_suffix
    )
    result = _public().verify_metadata(context, metadata)
    assert set(result) == set(NAMES)
    assert result[NAMES[0]]["sha256"] == hashlib.sha256(NAMES[0].encode()).hexdigest()


@pytest.mark.parametrize("role", ("publisher", "verifier"))
@pytest.mark.parametrize(
    "suffix",
    (
        "@",
        "@other",
        "@v2.1.0-alpha.1",
        "@v2.1.0-alpha.2",
        "@v2.1.0-alpha.4",
        "@bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "@refs/heads/main",
        "@refs/tags/v2.1.0-alpha.3",
        "@main@main",
        "@main@v2.1.0-alpha.3",
        "@main/",
        "@main/..",
        "@main?x=1",
        "@main#fragment",
        "@%6dain",
        "@main\n",
        "@main\x00",
    ),
)
def test_public_metadata_rejects_unselected_workflow_suffixes(role: str, suffix: str) -> None:
    context, metadata = _inputs()
    public = _public()
    public.verify_metadata(context, metadata)
    metadata[role]["path"] += suffix
    with pytest.raises(ValueError, match="Publication or qualification run identity mismatch"):
        public.verify_metadata(context, metadata)


@pytest.mark.parametrize("role", ("publisher", "verifier"))
@pytest.mark.parametrize(
    "bad_path",
    (
        None,
        False,
        1,
        [],
        {},
        "",
        "__missing__",
        "/.github/workflows/release.yml@main",
        ".github/workflows/../workflows/release.yml@main",
        ".github/workflows/Release.yml@main",
        "https://github.com/MarcoPorcellato/matryca-plumber/.github/workflows/release.yml@main",
    ),
)
def test_public_metadata_rejects_malformed_workflow_paths(role: str, bad_path: object) -> None:
    context, metadata = _inputs()
    public = _public()
    public.verify_metadata(context, metadata)
    if bad_path == "__missing__":
        del metadata[role]["path"]
    else:
        metadata[role]["path"] = bad_path
    with pytest.raises(ValueError, match="Publication or qualification run identity mismatch"):
        public.verify_metadata(context, metadata)


@pytest.mark.parametrize("role", ("publisher", "verifier"))
def test_public_metadata_rejects_swapped_qualified_workflows(role: str) -> None:
    context, metadata = _inputs()
    public = _public()
    public.verify_metadata(context, metadata)
    other = "verifier" if role == "publisher" else "publisher"
    metadata[role]["path"] = metadata[other]["path"] + "@main"
    with pytest.raises(ValueError, match="Publication or qualification run identity mismatch"):
        public.verify_metadata(context, metadata)


@pytest.mark.parametrize("role", ("publisher", "verifier"))
@pytest.mark.parametrize(
    ("field", "bad_value"),
    (
        ("head_sha", "b" * 40),
        ("head_branch", "unselected-ref"),
        ("event", "pull_request"),
        ("run_attempt", 2),
        ("id", 789),
        ("repository", {"id": 7, "full_name": "other/repository"}),
    ),
)
def test_qualified_workflow_paths_preserve_run_identity_checks(
    role: str, field: str, bad_value: object
) -> None:
    context, metadata = _inputs()
    public = _public()
    metadata["publisher"]["path"] += "@main"
    metadata["verifier"]["path"] += "@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    public.verify_metadata(context, metadata)
    metadata[role][field] = bad_value
    with pytest.raises(ValueError, match="Publication or qualification run identity mismatch"):
        public.verify_metadata(context, metadata)


@pytest.mark.parametrize("anchor", ("main", "tag-source", "tag-signature"))
def test_qualified_workflow_paths_require_selected_source_aliases(anchor: str) -> None:
    context, metadata = _inputs()
    public = _public()
    metadata["publisher"]["path"] += "@main"
    metadata["verifier"]["path"] += "@v2.1.0-alpha.3"
    public.verify_metadata(context, metadata)
    if anchor == "main":
        metadata["main"]["object"]["sha"] = "b" * 40
    elif anchor == "tag-source":
        metadata["tag_object"]["object"]["sha"] = "b" * 40
    else:
        metadata["tag_object"]["verification"]["verified"] = False
    with pytest.raises(ValueError):
        public.verify_metadata(context, metadata)


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
        "release-tag": ("release", None, "tag_name", "v2.1.0-alpha.4"),
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
            value["pypi"]["info"]["version"] = "2.1.0a4"
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
    ("url", "size", "sha256", "kind"),
    [
        ("https://pypi.org/pypi/matryca-plumber/2.1.0a3/json", 0, "", "pypi-metadata"),
        (
            f"https://api.github.com/repos/{REPO}/releases/assets/1",
            9,
            hashlib.sha256(b"synthetic").hexdigest(),
            "github",
        ),
        (
            "https://files.pythonhosted.org/packages/synthetic.whl",
            9,
            hashlib.sha256(b"synthetic").hexdigest(),
            "pypi",
        ),
    ],
)
def test_acquisition_digest_reaches_real_process_guard_and_cli_parser(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    url: str,
    size: int,
    sha256: str,
    kind: str,
) -> None:
    from scripts import qualify_release_package as qualification

    public = _public()
    commands: list[list[str]] = []

    class ChildLaunchIntercepted(Exception):
        pass

    def intercept_launch(command: list[str], **_kwargs: Any) -> NoReturn:
        commands.append(command)
        raise ChildLaunchIntercepted

    # Keep _acquire, _run_bounded and start_process real; stop only at Popen.
    monkeypatch.setattr(public.sdist_build.process_module.subprocess, "Popen", intercept_launch)
    path = tmp_path / "download"
    with pytest.raises(ChildLaunchIntercepted):
        public._acquire(url, path, size, sha256, kind)
    assert len(commands) == 1
    command = commands[0]
    assert all(isinstance(argument, str) and argument for argument in command)
    assert command[:3] == [
        public.sys.executable,
        "-B",
        str(ROOT / "scripts/qualify_release_package.py"),
    ]
    args = qualification._parser().parse_args(command[3:])
    assert (args.url, args.output, args.size, args.sha256, args.kind) == (
        url,
        path,
        size,
        sha256,
        kind,
    )
    response = io.BytesIO(b"synthetic")
    response.status = 200  # type: ignore[attr-defined]
    monkeypatch.setattr(public, "_open", lambda *_args, **_kwargs: response)
    qualification._alpha_public_fetch(args)
    assert path.read_bytes() == b"synthetic"


@pytest.mark.parametrize("command", [[], [""], ["synthetic", ""]])
def test_public_acquisition_keeps_empty_argv_rejection(
    monkeypatch: pytest.MonkeyPatch, command: list[str]
) -> None:
    public = _public()

    def unexpected_launch(*_args: Any, **_kwargs: Any) -> NoReturn:
        pytest.fail("Invalid argv must be rejected before a process is created.")

    monkeypatch.setattr(public.sdist_build.process_module.subprocess, "Popen", unexpected_launch)
    with pytest.raises(ValueError, match="nonempty shell-free argv"):
        public.sdist_build.process_module.start_process(command, windows=False)


@pytest.mark.parametrize(("size", "sha256"), [(1, ""), (0, "a" * 64)])
def test_metadata_acquisition_preserves_empty_digest_and_zero_size_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, size: int, sha256: str
) -> None:
    public = _public()

    def unexpected_open(*_args: Any, **_kwargs: Any) -> NoReturn:
        pytest.fail("Invalid metadata expectations must fail before network access.")

    monkeypatch.setattr(public, "_open", unexpected_open)
    path = tmp_path / "pypi.json"
    with pytest.raises(ValueError, match="Invalid acquisition expectations"):
        public.fetch_file(
            "https://pypi.org/pypi/matryca-plumber/2.1.0a3/json",
            path,
            size,
            sha256,
            "pypi-metadata",
        )
    assert not path.exists()


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
        "2.1.0a3",
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
    payloads["SHA256SUMS"] = canonical_manifest(binding, policy="og-alpha3")
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

    def synthetic_binding(
        root: Path, dist: Path, ledger: Path, expected_commit: str, *, policy: str
    ) -> Any:
        # The real inventory verifier accepts only the two original archives.
        assert root == tmp_path / "source" and expected_commit == SOURCE
        assert policy == "og-alpha3"
        assert {path.name for path in dist.iterdir()} == set(NAMES[:2])
        assert ledger.read_bytes() == payloads["content-ledger.json"]
        return binding

    monkeypatch.setattr(public.bundle, "build_binding", synthetic_binding)

    def source_context(root: Path, actual: Any, run_id: str, attempt: int) -> Any:
        assert root == tmp_path / "source" and actual == binding
        assert run_id == "456" and attempt == 1
        return matrix_context

    monkeypatch.setattr(public.matrix, "source_context", source_context)
    handoffs: list[Path] = []

    def synthetic_handoff(dist: Path, manifest: Path, expected: Any, *, policy: str) -> None:
        # This composition fixture is deliberately bytes, not a real wheel.
        # The unchanged archive verifier is a separately tested boundary.
        assert policy == "og-alpha3" and expected == binding
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
    assert not (output / "SHA256SUMS").exists()
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
    assert set(value["on"]["workflow_dispatch"]["inputs"]) == {
        "source_sha",
        "publication_run",
        "alpha3_recovery",
        "verifier_sha",
        "verifier_tree",
    }
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
            step for step in steps if step.get("if") == "${{ github.ref_name == 'v2.1.0-alpha.3' }}"
        ]
    acquisitions = [
        (index, step)
        for index, step in enumerate(steps)
        if "uv_acquisition.py acquire " in step.get("run", "")
    ]
    assert len(acquisitions) == 1, "Fresh authenticated acquisition is missing."
    acquire_index, acquire = acquisitions[0]
    assert not any("RUNNER_TOOL_CACHE" in step.get("env", {}) for step in steps)
    assert not any("setup-uv@" in step.get("uses", "") for step in steps)
    assert acquire["env"]["MATRYCA_UV_ROOT"] == "${{ runner.temp }}/matryca-uv"
    assert acquire["env"]["UV_ARCHIVE_SHA256"] == checksum
    assert int(acquire["timeout-minutes"]) <= 2
    verify = next(
        (i for i, step in enumerate(steps) if step.get("name") == "Verify selected uv acquisition"),
        -1,
    )
    provision = next(
        (i for i, step in enumerate(steps) if "uv python install 3.12" in step.get("run", "")), -1
    )
    assert 0 <= acquire_index < verify < provision
    script = steps[verify]["run"]
    assert "uv_acquisition.py verify " in script and "--version" in script
    assert 'test "$selected" = "$located"' in script
    assert "uv-path=" in script and "uv-version=" in script
    assert acquire["env"]["UV_PYTHON"] == "3.12"
    assert acquire["env"]["UV_PYTHON_INSTALL_DIR"] == "${{ runner.temp }}/matryca-uv/python"
    assert acquire["env"]["UV_PYTHON_BIN_DIR"] == "${{ runner.temp }}/matryca-uv/python-bin"
    assert int(steps[provision]["timeout-minutes"]) <= 5
    assert steps[provision]["env"]["UV_PYTHON_DOWNLOADS"] == "manual"
