"""Keep incomplete Stage A qualification unavailable for manual dispatch."""

from pathlib import Path


def test_stage_a_workflow_is_not_deployable_while_windows_is_no_go() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "release-package-qualification.yml"
    )
    assert not workflow.exists(), "Stage A workflow must not be deployable while Windows is NO-GO"
