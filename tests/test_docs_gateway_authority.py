"""Regression checks for the Plumber-owned Logseq gateway decision."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADR_PATH = ROOT / "docs" / "decisions" / "2026-09-05-plumber-logseq-gateway-authority.md"
DECISIONS_INDEX_PATH = ROOT / "docs" / "decisions" / "index.md"
CONTRACTS_INDEX_PATH = ROOT / "docs" / "contracts" / "README.md"
PERSISTENT_GOAL_PATH = (
    ROOT / "docs" / "quality" / "LOGSEQ_DB_READ_ONLY_COMPATIBILITY_PERSISTENT_GOAL_2026-09-05.md"
)
ECOSYSTEM_STRATEGY_PATH = (
    ROOT / "docs" / "roadmaps" / "TINE_LOGSEQ_ECOSYSTEM_INTEGRATION_STRATEGY_2026-08-12.md"
)
CAPABILITY_BASELINE_PATH = ROOT / "docs" / "quality" / "LOGSEQ_DB_CAPABILITY_BASELINE_2026-09-05.md"
DB_PLAN_PATH = (
    ROOT / "docs" / "superpowers" / "plans" / "2026-09-01-logseq-db-read-only-compatibility.md"
)
INVENTORY_PATH = ROOT / "docs" / "knowledge" / "inventory.json"


def test_gateway_authority_decision_defines_the_cross_repository_boundary() -> None:
    """The owner decision must keep consumer products outside Parser internals."""
    adr = ADR_PATH.read_text(encoding="utf-8")

    assert "Matryca Plumber is the sole Logseq gateway" in adr
    assert "Trama" in adr and "does not import Parser" in adr
    assert "Logseq DB official host surface" in adr
    assert "direct mutation of Logseq internal database" in adr
    assert "GraphReadPort remains filesystem/Shadow-only" in adr
    assert "GraphSessionReadPort" in adr
    assert "Operator Console" in adr
    assert "legacy/experimental LENS visualization surface" in adr
    assert "No LENS source or asset is removed or copied by this decision." in adr


def test_gateway_authority_is_discoverable_from_decision_and_contract_indexes() -> None:
    """Maintainers can find the owner decision without following stale plans."""
    decision_index = DECISIONS_INDEX_PATH.read_text(encoding="utf-8")
    contract_index = CONTRACTS_INDEX_PATH.read_text(encoding="utf-8")

    assert ADR_PATH.name in decision_index
    assert "plumber.graph.read/v1" in contract_index


def test_legacy_logseq_db_authority_surfaces_cannot_authorize_trama_adapters() -> None:
    """Historical DB planning must defer to the accepted Plumber gateway decision."""
    for legacy_surface in (PERSISTENT_GOAL_PATH, ECOSYSTEM_STRATEGY_PATH):
        text = legacy_surface.read_text(encoding="utf-8")

        assert "Historical/non-authorizing" in text
        assert "status: deprecated" in text
        assert "classification: historical" in text
        assert "../decisions/2026-09-05-plumber-logseq-gateway-authority.md" in text
        assert "GraphReadPort remains filesystem/Shadow-only" in text
        assert "does not authorize a Trama host adapter" in text
        assert "`trama.logseq.read/v1` authority" in text


def test_all_legacy_authority_surfaces_and_inventory_are_historical() -> None:
    """No legacy DB document or inventory entry can advertise current authority."""
    legacy_paths = (
        PERSISTENT_GOAL_PATH,
        ECOSYSTEM_STRATEGY_PATH,
        CAPABILITY_BASELINE_PATH,
        DB_PLAN_PATH,
    )
    for legacy_surface in legacy_paths:
        text = legacy_surface.read_text(encoding="utf-8")

        assert "Historical/non-authorizing" in text
        assert "2026-09-05-plumber-logseq-gateway-authority.md" in text
        assert "GraphReadPort remains filesystem/Shadow-only" in text
        assert "does not authorize a Trama host adapter" in text

    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    entries = {entry["path"]: entry for entry in inventory["entries"]}
    for legacy_surface in legacy_paths:
        entry = entries[str(legacy_surface.relative_to(ROOT))]

        assert entry["classification"] == "historical"
        assert entry["action"] == "archive"
        assert "Plumber Logseq gateway authority" in entry["notes"]
