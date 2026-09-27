from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs" / "quality" / "V2_0_1_RC4_RELEASE_QUALIFICATION_PLAN_2026-09-06.md"
README = ROOT / "README.md"


def test_rc4_qualification_plan_binds_the_required_delta_and_gate_boundaries() -> None:
    text = PLAN.read_text(encoding="utf-8")

    for required in (
        "#582",
        "Parser 1.9",
        "process timeout lifecycle",
        "topology session",
        "static contract/TCK resources",
        "test-only/unbound",
        "upstream_blocked",
        "Tier 3",
        "259,200 valid seconds per required profile",
        "default-on",
        "read-only + external Shadow",
        "74884c38edb9cae445fa465969aa2c9cee5ecd1c",
        "No current-source candidate, public RC4 artifact, Gate B result",
    ):
        assert required in text


def test_rc4_qualification_plan_separates_rc_from_stable_and_forbids_execution() -> None:
    text = PLAN.read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    assert text.index("Stage A — pre-publication GO/NO-GO") < text.index(
        "Stage B — post-publication qualification"
    )
    assert "Gate B is **not** a prerequisite for publishing the experimental RC4" in normalized
    assert "Terminal Gate B PASS for both exact-artifact profiles" in normalized
    assert "future stable `v2.0.1`" in text
    assert "authorizes no heavy Gate B/CCP invocation" in normalized


def test_rc4_qualification_plan_is_discoverable_from_the_public_readme() -> None:
    assert PLAN.name in README.read_text(encoding="utf-8")
