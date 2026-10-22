"""Synthetic public-byte admission; these tests perform no public downloads."""

from __future__ import annotations

import base64
import copy
import hashlib
import importlib
import importlib.util
import io
import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO = "MarcoPorcellato/matryca-plumber"
TAG = "v2.1.0-alpha.2"
SOURCE = "a" * 40
TREE = "b" * 40
NAMES = (
    "matryca_plumber-2.1.0a2-py3-none-any.whl",
    "matryca_plumber-2.1.0a2.tar.gz",
    "binding.json",
    "content-ledger.json",
    "canonical-build.json",
    "SHA256SUMS",
)


def _public() -> Any:
    name = "scripts.release_qualification.alpha1_public"
    assert importlib.util.find_spec(name) is not None, "Public artifact admission is missing."
    return importlib.import_module(name)


def test_metadata_acquisition_preserves_the_real_nonempty_argv_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import qualify_release_package as cli
    from scripts.release_qualification import process

    class SpawnReached(RuntimeError):
        pass

    commands: list[list[str]] = []

    def intercept_spawn(command: list[str], **_kwargs: Any) -> Any:
        commands.append(command)
        raise SpawnReached

    # Replace only the OS spawn, not _acquire, _run_bounded or its real guard.
    # No child, network request or downloaded code can execute in this test.
    monkeypatch.setattr(subprocess, "Popen", intercept_spawn)
    with pytest.raises(SpawnReached):
        _public()._acquire(
            "https://pypi.org/pypi/matryca-plumber/2.1.0a2/json",
            tmp_path / "pypi.json",
            0,
            "",
            "pypi-metadata",
        )
    assert len(commands) == 1
    command = commands[0]
    assert all(isinstance(token, str) and token for token in command)
    parsed = cli._parser().parse_args(command[3:])
    assert parsed.command == "alpha-public-fetch"
    assert parsed.sha256 == "" and parsed.size == 0
    assert parsed.kind == "pypi-metadata"
    with pytest.raises(ValueError, match="nonempty shell-free argv"):
        process.start_process(["synthetic", ""])


def _inputs() -> tuple[Any, dict[str, Any]]:
    public = _public()
    workflow = b"name: synthetic verifier\n"
    context = public.PublicContext(
        SOURCE,
        TREE,
        "123",
        "456",
        "d" * 40,
        "e" * 40,
        hashlib.sha256(workflow).hexdigest(),
    )
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
        "main": {"object": {"sha": "d" * 40}},
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
            "actor": {"id": 220745401, "login": "MarcoPorcellato"},
            "triggering_actor": {"id": 220745401, "login": "MarcoPorcellato"},
        },
        "verifier": {
            "id": 456,
            "run_attempt": 1,
            "event": "workflow_dispatch",
            "head_sha": "d" * 40,
            "head_branch": "main",
            "path": ".github/workflows/og-public-artifact-qualification.yml",
            "status": "in_progress",
            "repository": {"id": 1241185104, "full_name": REPO},
            "actor": {"id": 220745401, "login": "MarcoPorcellato"},
            "triggering_actor": {"id": 220745401, "login": "MarcoPorcellato"},
        },
        "verifier_commit": {
            "sha": "d" * 40,
            "tree": {"sha": "e" * 40},
            "parents": [{"sha": SOURCE}],
            "verification": {"verified": True, "reason": "valid"},
        },
        "verifier_workflow": {
            "type": "file",
            "path": ".github/workflows/og-public-artifact-qualification.yml",
            "encoding": "base64",
            "size": len(workflow),
            "content": base64.b64encode(workflow).decode(),
            "sha": hashlib.sha1(
                b"blob " + str(len(workflow)).encode() + b"\0" + workflow,
                usedforsecurity=False,
            ).hexdigest(),
        },
        "release": {
            "id": 17,
            "tag_name": TAG,
            "draft": False,
            "prerelease": True,
            "assets": release_assets,
        },
        "pypi": {
            "info": {"name": "matryca-plumber", "version": "2.1.0a2"},
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


def _separated_inputs() -> tuple[Any, dict[str, Any]]:
    _, metadata = _inputs()
    workflow = b"name: synthetic verifier\n"
    verifier = "d" * 40
    context = _public().PublicContext(
        SOURCE, TREE, "123", "456", verifier, "e" * 40, hashlib.sha256(workflow).hexdigest()
    )
    metadata["main"]["object"]["sha"] = verifier
    metadata["verifier"]["head_sha"] = verifier
    for role in ("publisher", "verifier"):
        metadata[role]["actor"] = {"id": 220745401, "login": "MarcoPorcellato"}
        metadata[role]["triggering_actor"] = {"id": 220745401, "login": "MarcoPorcellato"}
    metadata["verifier_commit"] = {
        "sha": verifier,
        "tree": {"sha": "e" * 40},
        "parents": [{"sha": SOURCE}],
        "verification": {"verified": True, "reason": "valid"},
    }
    metadata["verifier_workflow"] = {
        "type": "file",
        "path": ".github/workflows/og-public-artifact-qualification.yml",
        "encoding": "base64",
        "size": len(workflow),
        "content": base64.b64encode(workflow).decode(),
        "sha": hashlib.sha1(
            b"blob " + str(len(workflow)).encode() + b"\0" + workflow,
            usedforsecurity=False,
        ).hexdigest(),
    }
    return context, metadata


def test_public_metadata_binds_separate_verifier_without_relabeling_publisher() -> None:
    context, metadata = _separated_inputs()
    assets = _public().verify_metadata(context, metadata)
    assert set(assets) == set(NAMES)
    assert metadata["publisher"]["head_sha"] == SOURCE
    assert metadata["verifier"]["head_sha"] == "d" * 40


@pytest.mark.parametrize(
    "mutation",
    (
        "main-source",
        "verifier-source",
        "publisher-verifier",
        "publisher-main-alias",
        "verifier-tag-alias",
        "verifier-tree",
        "verifier-parent",
        "verifier-signature",
        "verifier-workflow",
        "verifier-workflow-size",
        "verifier-workflow-blob",
        "verifier-workflow-path",
        "verifier-actor",
        "publisher-actor",
        "missing-commit",
    ),
)
def test_public_metadata_rejects_conflated_or_unauthenticated_verifier(mutation: str) -> None:
    context, metadata = _separated_inputs()
    public = _public()
    public.verify_metadata(context, metadata)
    if mutation == "main-source":
        metadata["main"]["object"]["sha"] = SOURCE
    elif mutation == "verifier-source":
        metadata["verifier"]["head_sha"] = SOURCE
    elif mutation == "publisher-verifier":
        metadata["publisher"]["head_sha"] = "d" * 40
    elif mutation == "publisher-main-alias":
        metadata["publisher"]["path"] += "@main"
    elif mutation == "verifier-tag-alias":
        metadata["verifier"]["path"] += "@" + TAG
    elif mutation == "verifier-tree":
        metadata["verifier_commit"]["tree"]["sha"] = TREE
    elif mutation == "verifier-parent":
        metadata["verifier_commit"]["parents"] = [{"sha": "f" * 40}]
    elif mutation == "verifier-signature":
        metadata["verifier_commit"]["verification"]["verified"] = False
    elif mutation == "verifier-workflow":
        metadata["verifier_workflow"]["content"] = base64.b64encode(b"foreign").decode()
    elif mutation == "verifier-workflow-size":
        metadata["verifier_workflow"]["size"] = True
    elif mutation == "verifier-workflow-blob":
        metadata["verifier_workflow"]["sha"] = "0" * 40
    elif mutation == "verifier-workflow-path":
        metadata["verifier_workflow"]["path"] = ".github/workflows/release.yml"
    elif mutation in ("verifier-actor", "publisher-actor"):
        metadata[mutation.removesuffix("-actor")]["actor"]["id"] = 7
    else:
        del metadata["verifier_commit"]
    with pytest.raises(ValueError):
        public.verify_metadata(context, metadata)


@pytest.mark.parametrize(
    "bad_root",
    (None, "same", "nested", "symlink", "dirty", "parent", "scope", "mode", "actor"),
)
def test_public_roots_require_disjoint_clean_source_and_actual_tooling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad_root: str | None
) -> None:
    public = _public()
    source, verifier = tmp_path / "producer", tmp_path / "verifier"
    source.mkdir()
    verifier.mkdir()
    workflow = b"name: synthetic verifier\n"
    release = b"name: synthetic producer\n"
    for root in (source, verifier):
        (root / ".github/workflows").mkdir(parents=True)
        (root / ".github/workflows/og-public-artifact-qualification.yml").write_bytes(workflow)
        (root / ".github/workflows/release.yml").write_bytes(release)
    for module, filename in (
        (public, "alpha1_public.py"),
        (public.matrix, "alpha1_matrix.py"),
        (public.bundle, "bundle.py"),
        (public.installed, "installed.py"),
        (public.sdist_build, "sdist_build.py"),
    ):
        path = verifier / "scripts/release_qualification" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"# inert synthetic origin\n")
        monkeypatch.setattr(module, "__file__", str(path))
        monkeypatch.setattr(module.__spec__, "origin", str(path))
    monkeypatch.setattr(public, "PRODUCER_COMMIT", SOURCE, raising=False)
    monkeypatch.setattr(public, "PRODUCER_TREE", TREE, raising=False)
    monkeypatch.setattr(public, "PUBLISHER_RUN", "123", raising=False)
    monkeypatch.setattr(
        public,
        "PRODUCER_RELEASE_WORKFLOW_SHA256",
        hashlib.sha256(release).hexdigest(),
        raising=False,
    )
    for key, value in {
        "GITHUB_REPOSITORY": REPO,
        "GITHUB_REPOSITORY_ID": "1241185104",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_RUN_ID": "456",
        "GITHUB_SHA": "d" * 40,
        "GITHUB_ACTOR": "MarcoPorcellato",
        "GITHUB_ACTOR_ID": "220745401",
        "GITHUB_TRIGGERING_ACTOR": "MarcoPorcellato",
        "GITHUB_WORKSPACE": str(tmp_path),
    }.items():
        monkeypatch.setenv(key, value)

    def git_value(root: Path, *args: str) -> str:
        if args[0] == "rev-parse":
            return (
                (SOURCE if root == source else "d" * 40)
                if args[1] == "HEAD"
                else (TREE if root == source else "e" * 40)
            )
        if args[0] == "status":
            return " M synthetic" if bad_root == "dirty" else ""
        if args[0] == "show":
            return "f" * 40 if bad_root == "parent" else SOURCE
        if args[0] == "diff":
            return (
                "src/forbidden.py"
                if bad_root == "scope"
                else ("scripts/release_qualification/alpha1_public.py")
            )
        if args[0] == "ls-tree":
            mode = "100755" if bad_root == "mode" else "100644"
            return mode + " blob " + "0" * 40 + "\t" + args[-1]
        raise AssertionError(args)

    monkeypatch.setattr(public.installed, "_git_value", git_value)
    if bad_root == "actor":
        monkeypatch.setenv("GITHUB_ACTOR_ID", "7")
    if bad_root == "same":
        verifier = source
    elif bad_root == "nested":
        verifier = source / "verifier"
        verifier.mkdir()
    elif bad_root == "symlink":
        link = tmp_path / "producer-link"
        link.symlink_to(source, target_is_directory=True)
        source = link
    if bad_root is not None:
        with pytest.raises(ValueError):
            public.context_from_roots(source, verifier, "123")
    else:
        context = public.context_from_roots(source, verifier, "123")
        assert context.source_commit == SOURCE and context.verifier_commit == "d" * 40
        assert context.verifier_workflow_sha256 == hashlib.sha256(workflow).hexdigest()


@pytest.mark.parametrize("foreign", (False, True))
def test_public_source_child_checks_origins_before_loading_product_or_pytest(
    tmp_path: Path, foreign: bool
) -> None:
    import sys

    from scripts.release_qualification import alpha1_matrix as alpha
    from scripts.release_qualification import sdist_build

    source = tmp_path / "producer"
    source.mkdir()
    marker = tmp_path / "foreign-import"
    package = source / "src"
    if foreign:
        outside = tmp_path / "foreign-src"
        outside.mkdir()
        (outside / "__init__.py").write_text(
            "from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n"
        )
        package.symlink_to(outside, target_is_directory=True)
    else:
        package.mkdir()
        (package / "__init__.py").write_text("")
        (package / "agent").mkdir()
        (package / "agent/__init__.py").write_text("")
        (package / "agent/og_parser_topology_adapter.py").write_text("")
    (source / "matryca_plumber").mkdir()
    (source / "matryca_plumber/__init__.py").write_text("")
    (source / "pytest.py").write_text(
        "def main(args):\n print('SOURCE_COLLECTION', flush=True)\n return 0\n"
    )
    result = sdist_build._run_bounded(
        [sys.executable, "-I", "-B", "-c", alpha.PUBLIC_SOURCE_BOOTSTRAP, str(source)],
        cwd=tmp_path,
        timeout=15,
        capture=True,
    )
    assert not marker.exists()
    if foreign:
        assert result.returncode != 0 and b"SOURCE_COLLECTION" not in result.stdout
    else:
        assert result.returncode == 0 and b"SOURCE_COLLECTION" in result.stdout


@pytest.mark.parametrize(
    "publisher_suffix",
    ("", "@v2.1.0-alpha.2", "@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
)
@pytest.mark.parametrize(
    "verifier_suffix",
    ("", "@main", "@dddddddddddddddddddddddddddddddddddddddd"),
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
        "@v2.1.0-alpha.3",
        "@bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "@refs/heads/main",
        "@refs/tags/v2.1.0-alpha.2",
        "@main@main",
        "@main@v2.1.0-alpha.2",
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
    metadata["publisher"]["path"] += "@" + TAG
    metadata["verifier"]["path"] += "@dddddddddddddddddddddddddddddddddddddddd"
    public.verify_metadata(context, metadata)
    metadata[role][field] = bad_value
    with pytest.raises(ValueError, match="Publication or qualification run identity mismatch"):
        public.verify_metadata(context, metadata)


@pytest.mark.parametrize("anchor", ("main", "tag-source", "tag-signature"))
def test_qualified_workflow_paths_require_selected_source_aliases(anchor: str) -> None:
    context, metadata = _inputs()
    public = _public()
    metadata["publisher"]["path"] += "@" + TAG
    metadata["verifier"]["path"] += "@main"
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
        "release-tag": ("release", None, "tag_name", "v2.1.0-alpha.3"),
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
            value["pypi"]["info"]["version"] = "2.1.0a3"
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


@pytest.mark.parametrize("field", ("buildSignerDigest", "sourceRepositoryDigest"))
def test_verifier_revision_cannot_replace_producer_attestation_source(field: str) -> None:
    context, _ = _inputs()
    value = json.loads(_attestation(NAMES[0]))
    value[0]["verificationResult"]["signature"]["certificate"][field] = "d" * 40
    with pytest.raises(ValueError, match="certificate"):
        _public().verify_attestation(
            context,
            NAMES[0],
            hashlib.sha256(NAMES[0].encode()).hexdigest(),
            json.dumps(value).encode(),
        )


@pytest.mark.parametrize("mutation", ("id", "size", "digest", "release", "tag"))
def test_frozen_publication_rejects_two_matching_but_replaced_inventories(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    public = _public()
    context, metadata = _inputs()
    assets = public.verify_metadata(context, metadata)
    monkeypatch.setattr(public, "PUBLISHED_RELEASE_ID", 17)
    monkeypatch.setattr(public, "PUBLISHED_TAG_OBJECT", "c" * 40)
    monkeypatch.setattr(
        public,
        "PUBLISHED_SUBJECTS",
        {name: (item["id"], item["size"], item["sha256"]) for name, item in assets.items()},
    )
    public.verify_frozen_publication(metadata, assets)
    asset, pypi = metadata["release"]["assets"][0], metadata["pypi"]["urls"][0]
    if mutation == "id":
        asset["id"] = 100
        asset["url"] = f"https://api.github.com/repos/{REPO}/releases/assets/100"
    elif mutation == "size":
        asset["size"] += 1
        pypi["size"] += 1
    elif mutation == "digest":
        asset["digest"] = "sha256:" + "0" * 64
        pypi["digests"]["sha256"] = "0" * 64
    elif mutation == "release":
        metadata["release"]["id"] = 18
    else:
        metadata["tag"]["object"]["sha"] = "f" * 40
        metadata["tag_object"]["sha"] = "f" * 40
    replacement = public.verify_metadata(context, metadata)
    with pytest.raises(ValueError, match="preserved publication"):
        public.verify_frozen_publication(metadata, replacement)


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
    public_context, metadata = _inputs()
    payloads = {name: name.encode() for name in NAMES}
    binding = BundleBinding(
        SOURCE,
        TREE,
        "2.1.0a2",
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
    payloads["SHA256SUMS"] = canonical_manifest(binding, policy="og-alpha2")
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
    monkeypatch.setattr(public, "PRODUCER_COMMIT", SOURCE)
    monkeypatch.setattr(public, "PRODUCER_TREE", TREE)
    monkeypatch.setattr(public, "PUBLISHER_RUN", "123")
    monkeypatch.setattr(public, "PUBLISHED_TAG_OBJECT", "c" * 40)
    monkeypatch.setattr(public, "PUBLISHED_RELEASE_ID", 17)
    monkeypatch.setattr(
        public,
        "PUBLISHED_SUBJECTS",
        {
            asset["name"]: (asset["id"], asset["size"], asset["digest"][7:])
            for asset in metadata["release"]["assets"]
        },
    )

    def selected_roots(source_root: Path, verifier_root: Path, run: str) -> Any:
        assert source_root == tmp_path / "source"
        assert verifier_root == tmp_path / "verifier" and run == "123"
        return public_context

    monkeypatch.setattr(public, "context_from_roots", selected_roots)
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
        assert policy == "og-alpha2" and expected == binding
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
                f"repos/{REPO}/git/commits/" + "d" * 40: "verifier_commit",
                f"repos/{REPO}/contents/{public.VERIFIER}?ref=" + "d" * 40: "verifier_workflow",
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
        "GITHUB_SHA": "d" * 40,
    }.items():
        monkeypatch.setenv(key, value)
    source = tmp_path / "source"
    source.mkdir()
    verifier_root = tmp_path / "verifier"
    verifier_root.mkdir()
    output = tmp_path / "public-bundle"
    if build_failure is not None:
        with pytest.raises(ValueError, match="Canonical build|Canonical frontend"):
            public.admit_public(source, output, "123", verifier=verifier_root)
        assert not (output / "public-input.json").exists()
        assert handoffs == []
        return
    record = public.admit_public(source, output, "123", verifier=verifier_root)
    assert handoffs == [output / "dist"]
    assert len(acquisitions) == len(set(acquisitions)) == 9
    assert sum(argv[1:3] == ["attestation", "verify"] for argv in calls) == 6
    context = SimpleNamespace(binding=binding, run_id="456", run_attempt=1)
    public.verify_retained(output, context, record, verifier=public_context)
    assert record["schema_version"] == 2 and record["verifier_commit"] == "d" * 40
    for field, replacement in (
        ("schema_version", 1),
        ("schema_version", True),
        ("verifier_commit", SOURCE),
        ("verifier_tree", TREE),
        ("verifier_workflow_sha256", "0" * 64),
        ("verifier_attempt", True),
        ("source_commit", "d" * 40),
        ("publisher_run", "456"),
        ("future-field", None),
    ):
        changed = {**record, field: replacement}
        (output / "public-input.json").write_bytes(public.matrix.canonical(changed))
        with pytest.raises(ValueError):
            public.verify_retained(output, context, changed, verifier=public_context)
    for field in ("verifier_commit", "verifier_tree", "verifier_workflow_sha256"):
        changed = {key: value for key, value in record.items() if key != field}
        (output / "public-input.json").write_bytes(public.matrix.canonical(changed))
        with pytest.raises(ValueError):
            public.verify_retained(output, context, changed, verifier=public_context)
    (output / "public-input.json").write_bytes(public.matrix.canonical(record))
    (output / "dist" / NAMES[0]).write_bytes(b"tampered")
    with pytest.raises(ValueError):
        public.verify_retained(output, context, record, verifier=public_context)


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
    assert value["defaults"]["run"]["working-directory"] == "verifier"
    for name, job in jobs.items():
        checkouts = [
            step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout@")
        ]
        assert len(checkouts) == 2
        assert checkouts[0]["with"]["ref"] == "${{ github.sha }}"
        assert checkouts[0]["with"]["path"] == "verifier"
        assert checkouts[1]["with"]["ref"] == "82df37cdd4751e7cf0da9bf6372785567251c0ea"
        assert checkouts[1]["with"]["path"] == "producer"
        assert all(step["with"]["persist-credentials"] == "false" for step in checkouts)
        if name == "windows-refusal":
            git_overrides = {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "core.autocrlf",
                "GIT_CONFIG_VALUE_0": "false",
            }
            assert all(step.get("env") == git_overrides for step in checkouts)
        if name in ("source-controls", "linux312", "linux313", "macos312", "macos313"):
            assert (
                job["env"]["EXPECTED_PUBLIC_JSON"] == "${{ needs.admission.outputs.public-json }}"
            )
        invocations = [
            line
            for step in job["steps"]
            for line in step.get("run", "").splitlines()
            if "scripts/qualify_release_package.py alpha-" in line
        ]
        assert len(invocations) == 1
        assert '--source-root "$GITHUB_WORKSPACE/producer"' in invocations[0]
        assert '--verifier-root "$GITHUB_WORKSPACE/verifier"' in invocations[0]


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
            step for step in steps if step.get("if") == "${{ github.ref_name == 'v2.1.0-alpha.2' }}"
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
