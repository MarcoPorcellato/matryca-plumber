"""Admit only the original, independently attested public alpha artifacts.

Publication R and public qualification Q are distinct trusted workflow runs.
Local synthetic tests inject responses; this module never imports downloaded code.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from scripts.release_qualification import alpha1_matrix as matrix
from scripts.release_qualification import bundle, installed, sdist_build

REPO = "MarcoPorcellato/matryca-plumber"
REPOSITORY_ID = 1241185104
TAG = "v2.1.0-alpha.2"
VERSION = "2.1.0a2"
PUBLISHER = ".github/workflows/release.yml"
VERIFIER = ".github/workflows/og-public-artifact-qualification.yml"
ORIGINALS = (
    "matryca_plumber-2.1.0a2-py3-none-any.whl",
    "matryca_plumber-2.1.0a2.tar.gz",
)
ASSETS = (*ORIGINALS, "binding.json", "content-ledger.json", "canonical-build.json", "SHA256SUMS")
METADATA_LIMIT = 2_097_152
DISTRIBUTION_LIMIT = 33_554_432
PRODUCER_COMMIT = "82df37cdd4751e7cf0da9bf6372785567251c0ea"
PRODUCER_TREE = "e5e43299b06f780905cc16920e3ebaca701f2d8e"
PUBLISHER_RUN = "39734945749"
PUBLISHED_TAG_OBJECT = "e91b77d194198a5954021c635e0ee75b457407dd"
PUBLISHED_RELEASE_ID = 420383407
PRODUCER_RELEASE_WORKFLOW_SHA256 = (
    "d668bf4ddb11c4749469e22857c8a483cf8c523c9e6093a6bf4389c35dd9acf4"
)
PUBLISHED_SUBJECTS = {
    "binding.json": (
        664930623,
        628,
        "f714ce41eeb57c0afafed6b573151bc15b4f8ea85495c74c8187e918d5308821",
    ),
    "canonical-build.json": (
        664930648,
        770,
        "5448633187566bc8a65ef634ad412c9c2846826c031674c2ab1ca81226422478",
    ),
    "content-ledger.json": (
        664930626,
        154408,
        "da7853682430b0597c90c270bbb434066670d4cd682ecc595c903bed0e2e756b",
    ),
    ORIGINALS[0]: (
        664930628,
        754128,
        "77e224f5f16fa06e98855cb79df00763e092b63c09a6b3adb2f7f659e298918e",
    ),
    ORIGINALS[1]: (
        664930625,
        1041123,
        "ddeecbd974bd625b025b5c5f2f6064b4b684c9309a0399d70744f6b30970a501",
    ),
    "SHA256SUMS": (
        664930629,
        204,
        "eff521b26c6289fff66678d580b26eb0d39e594a1929882ad2a3051d6bfbfe63",
    ),
}
VERIFIER_PATHS = frozenset(
    {
        "scripts/release_qualification/alpha1_public.py",
        "scripts/release_qualification/alpha1_matrix.py",
        "scripts/qualify_release_package.py",
        VERIFIER,
        "tests/test_release_package_alpha1_public.py",
        "tests/test_release_package_alpha1_matrix.py",
        "docs/RELEASE_PROCESS.md",
        "docs/quality/V2_1_0A2_RELEASE_QUALIFICATION_PLAN_2026-10-19.md",
        "CHANGELOG.md",
        "docs/knowledge/inventory.json",
        "docs/knowledge/inventory.md",
    }
)
PUBLIC_FIELDS = {
    "schema_version",
    "status",
    "source_commit",
    "source_tree",
    "publisher_run",
    "verifier_run",
    "publisher_attempt",
    "verifier_attempt",
    "verifier_commit",
    "verifier_tree",
    "verifier_workflow_sha256",
    "github_cli_sha256",
    "provenance_sha256",
    "assets",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


@dataclass(frozen=True, slots=True)
class PublicContext:
    """Independently selected source and the two actual workflow identities."""

    source_commit: str
    source_tree: str
    publisher_run: str
    verifier_run: str
    verifier_commit: str
    verifier_tree: str
    verifier_workflow_sha256: str

    def __post_init__(self) -> None:
        _require(
            all(
                isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value)
                for value in (
                    self.source_commit,
                    self.source_tree,
                    self.verifier_commit,
                    self.verifier_tree,
                )
            )
            and all(
                isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value)
                for value in (self.publisher_run, self.verifier_run)
            )
            and self.publisher_run != self.verifier_run
            and self.source_commit != self.verifier_commit
            and self.source_tree != self.verifier_tree
            and isinstance(self.verifier_workflow_sha256, str)
            and re.fullmatch(r"[0-9a-f]{64}", self.verifier_workflow_sha256) is not None,
            "Invalid or conflated public source/run selection.",
        )


def _checked_root(path: Path) -> Path:
    absolute = path.absolute()
    _require(
        absolute.is_dir()
        and absolute == absolute.resolve()
        and not any(item.is_symlink() for item in (absolute, *absolute.parents))
        and (not hasattr(os, "getuid") or absolute.stat().st_uid == os.getuid()),
        "Public checkout root is not regular, canonical and task-owned.",
    )
    return absolute


def context_from_roots(source: Path, verifier: Path, publication_run: str) -> PublicContext:
    """Select S from a literal pin and C from the actual event and tooling origins."""
    source, verifier = _checked_root(source), _checked_root(verifier)
    workspace = _checked_root(Path(os.environ.get("GITHUB_WORKSPACE", "")))
    _require(
        source != verifier
        and not source.is_relative_to(verifier)
        and not verifier.is_relative_to(source)
        and source == workspace / "producer"
        and verifier == workspace / "verifier",
        "Public source and verifier roots must be disjoint explicit checkouts.",
    )
    for module, filename in (
        (sys.modules[__name__], "alpha1_public.py"),
        (matrix, "alpha1_matrix.py"),
        (bundle, "bundle.py"),
        (installed, "installed.py"),
        (sdist_build, "sdist_build.py"),
    ):
        expected = verifier / "scripts/release_qualification" / filename
        _require(
            module.__file__ is not None
            and module.__spec__ is not None
            and module.__spec__.origin is not None
            and Path(module.__file__).resolve() == expected
            and Path(module.__spec__.origin).resolve() == expected,
            "Qualification tooling does not originate in the verifier checkout.",
        )
    git = installed._git_value
    context = PublicContext(
        git(source, "rev-parse", "HEAD"),
        git(source, "rev-parse", "HEAD^{tree}"),
        publication_run,
        os.environ.get("GITHUB_RUN_ID", ""),
        git(verifier, "rev-parse", "HEAD"),
        git(verifier, "rev-parse", "HEAD^{tree}"),
        hashlib.sha256((verifier / VERIFIER).read_bytes()).hexdigest(),
    )
    _require(
        context.source_commit == PRODUCER_COMMIT
        and context.source_tree == PRODUCER_TREE
        and context.publisher_run == PUBLISHER_RUN
        and git(verifier, "show", "-s", "--format=%P", "HEAD") == PRODUCER_COMMIT
        and not installed_status(source)
        and not installed_status(verifier)
        and hashlib.sha256((source / PUBLISHER).read_bytes()).hexdigest()
        == PRODUCER_RELEASE_WORKFLOW_SHA256,
        "Public producer, verifier parent, clean state or publisher workflow changed.",
    )
    changed = git(
        verifier,
        "diff",
        "--name-only",
        "--no-renames",
        "--no-ext-diff",
        "--no-textconv",
        PRODUCER_COMMIT,
        "HEAD",
        "--",
    ).splitlines()
    _require(
        bool(changed) and len(changed) == len(set(changed)) and set(changed) <= VERIFIER_PATHS,
        "Verifier delta exceeds its approved qualification-only scope.",
    )
    for relative in changed:
        for root in (source, verifier):
            item = git(root, "ls-tree", "HEAD", "--", relative)
            _require(
                re.fullmatch(r"100644 blob [0-9a-f]{40}\t" + re.escape(relative), item) is not None,
                "Verifier delta changed a file type or introduced an unselected path.",
            )
    _require(
        os.environ.get("GITHUB_REPOSITORY") == REPO
        and os.environ.get("GITHUB_REPOSITORY_ID") == str(REPOSITORY_ID)
        and os.environ.get("GITHUB_REF") == "refs/heads/main"
        and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        and os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
        and os.environ.get("GITHUB_SHA") == context.verifier_commit
        and os.environ.get("GITHUB_ACTOR_ID") == "220745401"
        and os.environ.get("GITHUB_ACTOR") == "MarcoPorcellato"
        and os.environ.get("GITHUB_TRIGGERING_ACTOR") == "MarcoPorcellato",
        "Public qualification is not the selected maintainer verifier attempt.",
    )
    return context


def verify_frozen_publication(metadata: dict[str, Any], assets: dict[str, dict[str, Any]]) -> None:
    """Reject publication drift instead of accepting two newly matching inventories."""
    _require(
        metadata["release"].get("id") == PUBLISHED_RELEASE_ID
        and metadata["tag_object"].get("sha") == PUBLISHED_TAG_OBJECT
        and {name: (item["id"], item["size"], item["sha256"]) for name, item in assets.items()}
        == PUBLISHED_SUBJECTS,
        "Public inventory differs from the preserved publication.",
    )


def validate_url(url: str, kind: str, *, initial: bool = False) -> None:
    """Allow HTTPS only; never forward authentication or accept foreign redirects."""
    parts = urlsplit(url)
    _require(
        parts.scheme == "https"
        and parts.username is None
        and parts.password is None
        and parts.port in (None, 443)
        and not parts.fragment
        and not parts.query
        and not any(ord(character) < 33 for character in url),
        "Unsafe public URL.",
    )
    if kind == "github":
        api = (
            parts.hostname == "api.github.com"
            and re.fullmatch(rf"/repos/{REPO}/releases/assets/[1-9][0-9]*", parts.path) is not None
        )
        browser = parts.hostname == "github.com" and parts.path.startswith(
            f"/{REPO}/releases/download/{TAG}/"
        )
        redirect = not initial and parts.hostname in (
            "release-assets.githubusercontent.com",
            "objects.githubusercontent.com",
        )
        # Release-asset redirects carry signed query parameters; see fetch_file.
        _require(api or browser or redirect, "Foreign GitHub asset origin.")
    elif kind == "pypi":
        _require(
            parts.hostname == "files.pythonhosted.org" and parts.path.startswith("/packages/"),
            "Foreign PyPI distribution origin.",
        )
    elif kind == "pypi-metadata":
        _require(
            url == f"https://pypi.org/pypi/matryca-plumber/{VERSION}/json", "Foreign PyPI metadata."
        )
    else:
        raise ValueError("Unknown public acquisition kind.")


def _redirect_url(url: str, kind: str) -> None:
    # GitHub's signed asset-service URL has a query. Only those exact hosts may
    # carry it, and neither userinfo, fragments nor a different port is accepted.
    parts = urlsplit(url)
    if kind == "github" and parts.hostname in (
        "release-assets.githubusercontent.com",
        "objects.githubusercontent.com",
    ):
        validate_url(parts._replace(query="").geturl(), kind)
        _require(not any(ord(character) < 33 for character in url), "Invalid redirect characters.")
    else:
        validate_url(url, kind)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


def _open(request: Request) -> Any:
    # No ambient proxies, cookies, Authorization or token headers on public bytes.
    return build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=30)


def fetch_file(url: str, path: Path, size: int, sha256: str, kind: str) -> None:
    """Stream one bounded acquisition; the caller owns its 120-second process deadline."""
    metadata = kind == "pypi-metadata"
    limit = METADATA_LIMIT if metadata or path.name not in ORIGINALS else DISTRIBUTION_LIMIT
    _require(
        (metadata and size == 0 and sha256 == "")
        or (
            type(size) is int
            and 0 < size <= limit
            and re.fullmatch(r"[0-9a-f]{64}", sha256) is not None
        ),
        "Invalid acquisition expectations.",
    )
    validate_url(url, kind, initial=True)
    _require(
        path.parent.is_dir()
        and not path.parent.is_symlink()
        and not path.exists()
        and not path.is_symlink(),
        "Acquisition destination is not fresh and task-owned.",
    )
    response = None
    for hop in range(4):
        try:
            response = _open(
                Request(
                    url,
                    headers={
                        "Accept": "application/json" if metadata else "application/octet-stream"
                    },
                    method="GET",
                )
            )
            break
        except HTTPError as error:
            try:
                _require(
                    error.code in (301, 302, 303, 307, 308) and hop < 3,
                    "Public redirect limit or HTTP failure.",
                )
                location = error.headers.get("Location")
                _require(
                    isinstance(location, str) and bool(location),
                    "Missing public redirect location.",
                )
                url = urljoin(url, location)
                _redirect_url(url, kind)
            finally:
                error.close()
    if response is None:
        raise ValueError("No public response.")
    total = 0
    digest = hashlib.sha256()
    with response, path.open("xb") as output:
        _require(response.status == 200, "Public response did not succeed.")
        while chunk := response.read(65_536):
            total += len(chunk)
            _require(total <= (limit if metadata else size), "Public output exceeds its bound.")
            output.write(chunk)
            digest.update(chunk)
    _require(
        total > 0 and (metadata or (total == size and digest.hexdigest() == sha256)),
        "Public size or SHA-256 mismatch.",
    )


def verify_metadata(context: PublicContext, metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Authenticate source/tag/R/Q and exact six-plus-two public inventories."""
    _require(
        set(metadata)
        == {
            "main",
            "tag",
            "tag_object",
            "publisher",
            "verifier",
            "release",
            "pypi",
            "verifier_commit",
            "verifier_workflow",
        },
        "Incomplete public metadata.",
    )
    _require(
        metadata["main"].get("object", {}).get("sha") == context.verifier_commit,
        "Public main advanced.",
    )
    commit = metadata["verifier_commit"]
    parents = commit.get("parents")
    _require(
        commit.get("sha") == context.verifier_commit
        and commit.get("tree", {}).get("sha") == context.verifier_tree
        and isinstance(parents, list)
        and len(parents) == 1
        and isinstance(parents[0], dict)
        and parents[0].get("sha") == context.source_commit
        and commit.get("verification", {}).get("verified") is True
        and commit.get("verification", {}).get("reason") == "valid",
        "Signed verifier commit/tree/parent identity mismatch.",
    )
    workflow = metadata["verifier_workflow"]
    content = workflow.get("content")
    _require(
        workflow.get("type") == "file"
        and workflow.get("path") == VERIFIER
        and workflow.get("encoding") == "base64"
        and type(workflow.get("size")) is int
        and 0 < workflow["size"] <= METADATA_LIMIT
        and isinstance(content, str)
        and len(content) <= METADATA_LIMIT,
        "Verifier workflow metadata is malformed.",
    )
    try:
        raw_workflow = base64.b64decode(content.replace("\n", ""), validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("Verifier workflow encoding is malformed.") from error
    _require(
        len(raw_workflow) == workflow["size"]
        and hashlib.sha256(raw_workflow).hexdigest() == context.verifier_workflow_sha256
        and hashlib.sha1(
            b"blob " + str(len(raw_workflow)).encode() + b"\0" + raw_workflow,
            usedforsecurity=False,
        ).hexdigest()
        == workflow.get("sha"),
        "Verifier workflow does not match its independently selected bytes.",
    )
    tag, tag_object = metadata["tag"], metadata["tag_object"]
    _require(
        tag.get("ref") == "refs/tags/" + TAG
        and tag.get("object", {}).get("type") == "tag"
        and tag.get("object", {}).get("sha") == tag_object.get("sha")
        and re.fullmatch(r"[0-9a-f]{40}", str(tag_object.get("sha"))) is not None
        and tag_object.get("tag") == TAG
        and tag_object.get("object", {}).get("type") == "commit"
        and tag_object.get("object", {}).get("sha") == context.source_commit
        and tag_object.get("verification", {}).get("verified") is True,
        "Signed annotated tag does not bind the selected source.",
    )
    for key, run_id, event, branch, workflow_path_expected, head in (
        ("publisher", context.publisher_run, "push", TAG, PUBLISHER, context.source_commit),
        (
            "verifier",
            context.verifier_run,
            "workflow_dispatch",
            "main",
            VERIFIER,
            context.verifier_commit,
        ),
    ):
        run = metadata[key]
        workflow_path = run.get("path")
        # Do not equate a path suffix with the triggering branch. Only aliases
        # already bound to the selected source above are admitted.
        _require(
            type(run.get("id")) is int
            and str(run["id"]) == run_id
            and type(run.get("run_attempt")) is int
            and run["run_attempt"] == 1
            and run.get("event") == event
            and run.get("head_branch") == branch
            and run.get("head_sha") == head
            and isinstance(workflow_path, str)
            and workflow_path
            in (
                workflow_path_expected,
                f"{workflow_path_expected}@{branch}",
                f"{workflow_path_expected}@{head}",
            )
            and run.get("repository", {}).get("id") == REPOSITORY_ID
            and run.get("repository", {}).get("full_name") == REPO
            and all(
                type(run.get(actor, {}).get("id")) is int
                and run[actor]["id"] == 220745401
                and run[actor].get("login") == "MarcoPorcellato"
                for actor in ("actor", "triggering_actor")
            ),
            "Publication or qualification run identity mismatch.",
        )
    _require(
        metadata["publisher"].get("status") == "completed"
        and metadata["publisher"].get("conclusion") == "success",
        "Publication is not terminally successful.",
    )
    release = metadata["release"]
    _require(
        release.get("tag_name") == TAG
        and release.get("draft") is False
        and release.get("prerelease") is True
        and isinstance(release.get("assets"), list)
        and len(release["assets"]) == 6,
        "Release identity or asset cardinality mismatch.",
    )
    assets: dict[str, dict[str, Any]] = {}
    asset_ids: set[int] = set()
    for asset in release["assets"]:
        name = asset.get("name")
        _require(
            name in ASSETS and name not in assets, "Missing, extra or duplicate release asset."
        )
        identifier, size, digest = asset.get("id"), asset.get("size"), asset.get("digest")
        _require(
            type(identifier) is int
            and identifier > 0
            and identifier not in asset_ids
            and type(size) is int
            and 0 < size <= (DISTRIBUTION_LIMIT if name in ORIGINALS else METADATA_LIMIT)
            and isinstance(digest, str)
            and re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is not None
            and asset.get("state") == "uploaded"
            and asset.get("url")
            == f"https://api.github.com/repos/{REPO}/releases/assets/{identifier}"
            and asset.get("browser_download_url")
            == f"https://github.com/{REPO}/releases/download/{TAG}/{name}",
            "Release asset size, digest or identity mismatch.",
        )
        asset_ids.add(identifier)
        assets[name] = {"id": identifier, "size": size, "sha256": digest[7:], "url": asset["url"]}
    _require(set(assets) == set(ASSETS), "Incomplete release assets.")
    _require(
        sum(assets[name]["size"] for name in ORIGINALS) <= 67_108_864,
        "Original pair exceeds aggregate bound.",
    )
    pypi = metadata["pypi"]
    _require(
        pypi.get("info", {}).get("name") == "matryca-plumber"
        and pypi.get("info", {}).get("version") == VERSION
        and isinstance(pypi.get("urls"), list)
        and len(pypi["urls"]) == 2,
        "PyPI version or inventory mismatch.",
    )
    seen: set[str] = set()
    for item in pypi["urls"]:
        name = item.get("filename")
        _require(
            name in ORIGINALS and name not in seen, "Extra, duplicate or missing PyPI original."
        )
        seen.add(name)
        expected = assets[name]
        _require(
            item.get("yanked") is False
            and type(item.get("size")) is int
            and item["size"] == expected["size"]
            and item.get("digests", {}).get("sha256") == expected["sha256"]
            and item.get("packagetype") == ("bdist_wheel" if name == ORIGINALS[0] else "sdist")
            and isinstance(item.get("url"), str),
            "PyPI original differs from its GitHub counterpart.",
        )
        validate_url(item["url"], "pypi", initial=True)
        _require(urlsplit(item["url"]).path.endswith("/" + name), "PyPI URL filename mismatch.")
        expected["pypi_url"] = item["url"]
    return assets


def verify_attestation(context: PublicContext, name: str, sha256: str, raw: bytes) -> None:
    """Check the cryptographically verified CLI result, not an editable predicate."""
    result = matrix.document(b'{"entries":' + raw + b"}").get("entries")
    if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], dict):
        raise ValueError("Ambiguous verified attestation result.")
    verified = result[0].get("verificationResult", {})
    certificate = verified.get("signature", {}).get("certificate", {})
    workflow_identity = f"https://github.com/{REPO}/{PUBLISHER}@refs/tags/{TAG}"
    expected = {
        "issuer": "https://token.actions.githubusercontent.com",
        "subjectAlternativeName": workflow_identity,
        "buildSignerURI": workflow_identity,
        "buildSignerDigest": context.source_commit,
        "sourceRepositoryURI": "https://github.com/" + REPO,
        "sourceRepositoryDigest": context.source_commit,
        "sourceRepositoryRef": "refs/tags/" + TAG,
        "sourceRepositoryIdentifier": str(REPOSITORY_ID),
        "sourceRepositoryOwnerIdentifier": "220745401",
        "sourceRepositoryVisibilityAtSigning": "public",
        "runnerEnvironment": "github-hosted",
        "buildTrigger": "push",
        "runInvocationURI": (
            f"https://github.com/{REPO}/actions/runs/{context.publisher_run}/attempts/1"
        ),
    }
    _require(
        all(certificate.get(key) == value for key, value in expected.items()),
        "Signed certificate identity/source/invocation mismatch.",
    )
    statement = verified.get("statement", {})
    _require(
        isinstance(verified.get("verifiedTimestamps"), list)
        and bool(verified["verifiedTimestamps"])
        and statement.get("_type") == "https://in-toto.io/Statement/v1"
        and statement.get("predicateType") == "https://slsa.dev/provenance/v1"
        and isinstance(statement.get("subject"), list)
        and sum(
            subject.get("digest", {}).get("sha256") == sha256 and subject.get("name") == name
            for subject in statement["subject"]
        )
        == 1,
        "Verified attestation subject or timestamp is missing.",
    )


def _write(path: Path, raw: bytes) -> None:
    _require(not path.exists() and not path.is_symlink(), "Refusing to replace public evidence.")
    with path.open("xb") as output:
        output.write(raw)


def _command(command: list[str], output: Path, timeout: int = 30) -> bytes:
    result = sdist_build._run_bounded(command, timeout=timeout, capture=True)
    _write(output, result.stdout)
    _require(result.returncode == 0, "Bounded public provenance command failed.")
    return result.stdout


def _acquire(url: str, path: Path, size: int, sha256: str, kind: str) -> None:
    # Reuse the reviewed process-tree owner for the *entire* streaming deadline.
    result = sdist_build._run_bounded(
        [
            sys.executable,
            "-B",
            str(Path(__file__).resolve().parents[1] / "qualify_release_package.py"),
            "alpha-public-fetch",
            "--url",
            url,
            "--output",
            str(path),
            "--size",
            str(size),
            f"--sha256={sha256}",
            "--kind",
            kind,
        ],
        timeout=120,
        capture=True,
    )
    _require(result.returncode == 0, "One-shot public acquisition failed.")


def _inventory(root: Path) -> dict[str, str]:
    result = {}
    for path in root.iterdir():
        _require(
            not path.is_symlink() and path.is_file() and path.stat().st_size <= DISTRIBUTION_LIMIT,
            "Invalid retained public provenance.",
        )
        result[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def admit_public(
    source: Path, output: Path, publication_run: str, *, verifier: Path
) -> dict[str, Any]:
    """One hosted admission, after complete publication; no build or fallback route."""
    context = context_from_roots(source, verifier, publication_run)
    source, verifier = source.resolve(), verifier.resolve()
    _require(
        not output.exists()
        and not output.is_symlink()
        and not output.resolve().is_relative_to(source)
        and not output.resolve().is_relative_to(verifier),
        "Public bundle root must be fresh and outside source.",
    )
    output.mkdir(parents=True)
    provenance = output / "public-provenance"
    provenance.mkdir()
    gh = shutil.which("gh")
    _require(gh is not None, "GitHub CLI is unavailable.")
    assert gh is not None
    gh_digest = hashlib.sha256(Path(gh).read_bytes()).hexdigest()

    def gh_read(arguments: list[str], name: str, timeout: int = 30) -> bytes:
        _require(
            hashlib.sha256(Path(gh).read_bytes()).hexdigest() == gh_digest,
            "GitHub CLI changed during qualification.",
        )
        return _command([gh, *arguments], provenance / name, timeout)

    metadata: dict[str, Any] = {}
    for key, endpoint in (
        ("main", "git/ref/heads/main"),
        ("tag", "git/ref/tags/" + TAG),
        ("publisher", "actions/runs/" + context.publisher_run),
        ("verifier", "actions/runs/" + context.verifier_run),
        ("release", "releases/tags/" + TAG),
        ("verifier_commit", "git/commits/" + context.verifier_commit),
        ("verifier_workflow", f"contents/{VERIFIER}?ref={context.verifier_commit}"),
    ):
        metadata[key] = matrix.document(gh_read(["api", f"repos/{REPO}/{endpoint}"], key + ".json"))
    tag_sha = metadata["tag"].get("object", {}).get("sha")
    _require(
        isinstance(tag_sha, str) and re.fullmatch(r"[0-9a-f]{40}", tag_sha) is not None,
        "Invalid tag object.",
    )
    metadata["tag_object"] = matrix.document(
        gh_read(["api", f"repos/{REPO}/git/tags/{tag_sha}"], "tag_object.json")
    )
    pypi_path = provenance / "pypi.json"
    _acquire(
        f"https://pypi.org/pypi/matryca-plumber/{VERSION}/json", pypi_path, 0, "", "pypi-metadata"
    )
    metadata["pypi"] = matrix.read_document(pypi_path)
    assets = verify_metadata(context, metadata)
    verify_frozen_publication(metadata, assets)
    dist = output / "dist"
    dist.mkdir()
    for name in ASSETS:
        expected = assets[name]
        target = dist / name if name in (*ORIGINALS, "SHA256SUMS") else output / name
        _acquire(expected["url"], target, expected["size"], expected["sha256"], "github")
        raw = gh_read(
            [
                "attestation",
                "verify",
                str(target),
                "--repo",
                REPO,
                "--cert-identity",
                f"https://github.com/{REPO}/{PUBLISHER}@refs/tags/{TAG}",
                "--source-digest",
                context.source_commit,
                "--signer-digest",
                context.source_commit,
                "--deny-self-hosted-runners",
                "--format",
                "json",
                "--limit",
                "1",
            ],
            name + ".verification.json",
            120,
        )
        verify_attestation(context, name, expected["sha256"], raw)
    for name in ORIGINALS:
        expected = assets[name]
        _acquire(
            expected["pypi_url"], provenance / name, expected["size"], expected["sha256"], "pypi"
        )
    binding = bundle.BundleBinding.from_json(
        (output / "binding.json").read_text(), policy=matrix.POLICY
    )
    _require(
        binding.source_commit == context.source_commit
        and binding.source_tree == context.source_tree,
        "Publisher binding is stale.",
    )
    expected_context = matrix.source_context(source, binding, context.verifier_run, 1)
    matrix.verify_canonical_build(
        expected_context, matrix.read_document(output / "canonical-build.json")
    )
    bundle.verify_handoff(dist, dist / "SHA256SUMS", binding, policy=matrix.POLICY)
    observed = bundle.build_binding(
        source, dist, output / "content-ledger.json", context.source_commit, policy=matrix.POLICY
    )
    _require(
        observed == binding,
        "Public ledger or original artifact inventory differs from selected source.",
    )
    record = {
        "schema_version": 2,
        "status": "pass",
        "source_commit": context.source_commit,
        "source_tree": context.source_tree,
        "publisher_run": context.publisher_run,
        "verifier_run": context.verifier_run,
        "verifier_commit": context.verifier_commit,
        "verifier_tree": context.verifier_tree,
        "verifier_workflow_sha256": context.verifier_workflow_sha256,
        "publisher_attempt": 1,
        "verifier_attempt": 1,
        "github_cli_sha256": gh_digest,
        "provenance_sha256": _inventory(provenance),
        "assets": assets,
    }
    _write(output / "public-input.json", matrix.canonical(record))
    return record


def installed_status(source: Path) -> str:
    """Keep the source clean while admitting only external public inputs."""
    return installed._git_value(source, "status", "--porcelain", "--untracked-files=all")


def verify_retained(
    root: Path, context: matrix.MatrixContext, expected: dict[str, Any], *, verifier: PublicContext
) -> None:
    """Recheck the admission job's authenticated output and retained original inputs."""
    record = matrix.read_document(root / "public-input.json")
    _require(
        set(record) == PUBLIC_FIELDS
        and record == expected
        and record.get("status") == "pass"
        and type(record.get("schema_version")) is int
        and record["schema_version"] == 2,
        "Public admission output differs from independently carried expectation.",
    )
    public = verifier
    _require(
        isinstance(public, PublicContext)
        and public.source_commit == context.binding.source_commit == PRODUCER_COMMIT
        and public.source_tree == context.binding.source_tree == PRODUCER_TREE
        and public.publisher_run == record.get("publisher_run") == PUBLISHER_RUN
        and public.verifier_run == context.run_id
        and public.verifier_commit == record.get("verifier_commit")
        and public.verifier_tree == record.get("verifier_tree")
        and public.verifier_workflow_sha256 == record.get("verifier_workflow_sha256")
        and re.fullmatch(r"[0-9a-f]{64}", str(record.get("github_cli_sha256"))) is not None
        and type(record.get("publisher_attempt")) is int
        and record["publisher_attempt"] == 1
        and type(record.get("verifier_attempt")) is int
        and record["verifier_attempt"] == 1
        and context.run_attempt == 1
        and record.get("verifier_run") == context.run_id
        and record.get("source_commit") == context.binding.source_commit
        and record.get("source_tree") == context.binding.source_tree,
        "Retained R/Q identity mismatch.",
    )
    provenance = root / "public-provenance"
    _require(
        not provenance.is_symlink() and provenance.is_dir(), "Missing retained public provenance."
    )
    _require(
        _inventory(provenance) == record["provenance_sha256"], "Retained public provenance changed."
    )
    metadata = {
        key: matrix.read_document(provenance / (key + ".json"))
        for key in (
            "main",
            "tag",
            "tag_object",
            "publisher",
            "verifier",
            "release",
            "pypi",
            "verifier_commit",
            "verifier_workflow",
        )
    }
    assets = verify_metadata(public, metadata)
    verify_frozen_publication(metadata, assets)
    _require(assets == record["assets"], "Retained public asset expectation changed.")
    for name in ASSETS:
        path = root / "dist" / name if name in (*ORIGINALS, "SHA256SUMS") else root / name
        _require(
            not path.is_symlink()
            and path.is_file()
            and path.stat().st_size == assets[name]["size"],
            "Public asset size changed.",
        )
        _require(
            hashlib.sha256(path.read_bytes()).hexdigest() == assets[name]["sha256"],
            "Public asset hash changed.",
        )
        verify_attestation(
            public,
            name,
            assets[name]["sha256"],
            (provenance / (name + ".verification.json")).read_bytes(),
        )
    for name in ORIGINALS:
        _require(
            hashlib.sha256((provenance / name).read_bytes()).hexdigest() == assets[name]["sha256"],
            "PyPI original differs from GitHub original.",
        )
