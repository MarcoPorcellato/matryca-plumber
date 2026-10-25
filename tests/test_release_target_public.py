"""A new release target must flow through metadata, URLs and attestations."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import pytest
from scripts.release_qualification import alpha1_public as public
from scripts.release_qualification.release_target import ReleaseTarget

from tests.test_release_package_alpha1_public import _inputs


def future_inputs() -> tuple[Any, dict[str, Any]]:
    original, metadata = _inputs()
    target = ReleaseTarget(
        "v2.1.0-alpha.4",
        "2.1.0a4",
        original.source_commit,
        original.source_tree,
        "c" * 40,
        original.publisher_run,
    )
    context = public.PublicContext(
        original.source_commit,
        original.source_tree,
        original.publisher_run,
        original.verifier_run,
        target=target,
    )
    metadata = json.loads(
        json.dumps(metadata)
        .replace("v2.1.0-alpha.3", "v2.1.0-alpha.4")
        .replace("2.1.0a3", "2.1.0a4")
    )
    return context, metadata


def test_public_metadata_authenticates_a_successor_without_changing_original_inputs() -> None:
    context, metadata = future_inputs()
    assets = public.verify_metadata(context, metadata)
    assert set(assets) == {
        "matryca_plumber-2.1.0a4-py3-none-any.whl",
        "matryca_plumber-2.1.0a4.tar.gz",
        "binding.json",
        "content-ledger.json",
        "canonical-build.json",
        "SHA256SUMS",
    }


def test_signed_but_unselected_tag_object_is_rejected() -> None:
    context, metadata = future_inputs()
    metadata["tag"]["object"]["sha"] = "f" * 40
    metadata["tag_object"]["sha"] = "f" * 40
    with pytest.raises(ValueError):
        public.verify_metadata(context, metadata)


def test_public_target_cannot_be_conflated_with_the_selected_source() -> None:
    context, _ = future_inputs()
    with pytest.raises(ValueError):
        replace(context, target=replace(context.target, source_tree="f" * 40))


def test_acquisition_url_uses_only_the_selected_tag() -> None:
    url = "https://github.com/MarcoPorcellato/matryca-plumber/releases/download/v2.1.0-alpha.4/binding.json"
    public.validate_url(url, "github", initial=True, release_tag="v2.1.0-alpha.4")
    with pytest.raises(ValueError):
        public.validate_url(url, "github", initial=True, release_tag="v2.1.0-alpha.3")


def test_hardened_stable_release_is_not_mislabeled_as_prerelease() -> None:
    context, metadata = future_inputs()
    metadata = json.loads(
        json.dumps(metadata).replace("v2.1.0-alpha.4", "v2.1.0").replace("2.1.0a4", "2.1.0")
    )
    metadata["release"]["prerelease"] = False
    context = replace(context, target=replace(context.target, tag="v2.1.0", version="2.1.0"))
    assert "matryca_plumber-2.1.0-py3-none-any.whl" in public.verify_metadata(context, metadata)


@pytest.mark.parametrize("wrong_tag", [False, True])
def test_verified_attestation_stays_bound_to_the_selected_release(wrong_tag: bool) -> None:
    context, _ = future_inputs()
    identity = "https://github.com/MarcoPorcellato/matryca-plumber/.github/workflows/release.yml@refs/tags/v2.1.0-alpha.4"
    certificate = {
        "issuer": "https://token.actions.githubusercontent.com",
        "subjectAlternativeName": identity,
        "buildSignerURI": identity,
        "buildSignerDigest": context.source_commit,
        "sourceRepositoryURI": "https://github.com/MarcoPorcellato/matryca-plumber",
        "sourceRepositoryDigest": context.source_commit,
        "sourceRepositoryRef": "refs/tags/v2.1.0-alpha.4",
        "sourceRepositoryIdentifier": "1241185104",
        "sourceRepositoryOwnerIdentifier": "220745401",
        "sourceRepositoryVisibilityAtSigning": "public",
        "runnerEnvironment": "github-hosted",
        "buildTrigger": "push",
        "runInvocationURI": "https://github.com/MarcoPorcellato/matryca-plumber/actions/runs/123/attempts/1",
    }
    if wrong_tag:
        certificate["sourceRepositoryRef"] = "refs/tags/v2.1.0-alpha.3"
    raw = json.dumps(
        [
            {
                "verificationResult": {
                    "signature": {"certificate": certificate},
                    "verifiedTimestamps": ["synthetic verified timestamp"],
                    "statement": {
                        "_type": "https://in-toto.io/Statement/v1",
                        "predicateType": "https://slsa.dev/provenance/v1",
                        "subject": [{"name": "binding.json", "digest": {"sha256": "1" * 64}}],
                    },
                }
            }
        ]
    ).encode()
    if wrong_tag:
        with pytest.raises(ValueError):
            public.verify_attestation(context, "binding.json", "1" * 64, raw)
    else:
        public.verify_attestation(context, "binding.json", "1" * 64, raw)
