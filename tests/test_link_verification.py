"""Tests for structural link verification (#15)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from src.graph.link_verification import (
    LinkRegistryEntry,
    extract_links_from_page,
    flag_block_hygiene_property,
    link_registry_path,
    link_verify_strikes_threshold,
    load_link_registry,
    merge_page_links_into_registry,
    register_page_links_from_path,
    save_link_registry,
    verify_registry_batch,
)

BLOCK = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_BASELINE_MTIME_NS = 1_000_000_000


@pytest.fixture
def graph_with_page(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "graph"
    pages = root / "pages"
    pages.mkdir(parents=True)
    assets = root / "assets"
    assets.mkdir()
    page = pages / "demo.md"
    page.write_text(
        "\n".join(
            [
                "- Read https://example.com/ok",
                f"  id:: {BLOCK}",
                "- ![diagram](../assets/missing.png)",
                "  id:: bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "",
            ],
        ),
        encoding="utf-8",
    )
    return root, page


def test_extract_links_from_page(graph_with_page: tuple[Path, Path]) -> None:
    root, page = graph_with_page
    content = page.read_text(encoding="utf-8")
    entries = extract_links_from_page(root, page, content)
    kinds = {(e.kind, e.target) for e in entries}
    assert ("url", "https://example.com/ok") in kinds
    assert any(e.kind == "asset" and "missing.png" in e.target for e in entries)


def test_merge_registry_and_flag_asset(
    graph_with_page: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, page = graph_with_page
    monkeypatch.setenv("MATRYCA_LINK_VERIFY_STRIKES", "1")
    assert link_verify_strikes_threshold() == 1

    merge_page_links_into_registry(root, page, page.read_text(encoding="utf-8"))
    registry = load_link_registry(root)
    assert registry

    asset_key = next(k for k, v in registry.items() if v.kind == "asset")
    entry = registry[asset_key]
    entry.strikes = link_verify_strikes_threshold()

    flagged = flag_block_hygiene_property(
        root,
        entry.page_relpath,
        entry.block_uuid,
        "missing-asset",
    )
    assert flagged
    text = page.read_text(encoding="utf-8")
    assert "missing-asset:: true" in text


def test_flag_block_proceeds_when_mtime_unchanged_ns(
    graph_with_page: tuple[Path, Path],
) -> None:
    """OCC guard must not abort when on-disk st_mtime_ns matches the snapshot."""
    root, _page = graph_with_page

    with (
        patch(
            "src.graph.link_verification.occ_snapshot",
            return_value=_BASELINE_MTIME_NS,
        ),
        patch("src.graph.link_verification.occ_verify_before_write", return_value=True),
        patch(
            "src.graph.markdown_blocks.read_file_mtime",
            return_value=_BASELINE_MTIME_NS,
        ),
        patch(
            "src.graph.link_verification.atomic_write_bytes_if_unchanged", return_value=True
        ) as write_mock,
    ):
        flagged = flag_block_hygiene_property(
            root,
            "pages/demo.md",
            BLOCK,
            "missing-asset",
        )

    assert flagged
    write_mock.assert_called_once()


def test_flag_block_aborts_on_one_nanosecond_mtime_drift(
    graph_with_page: tuple[Path, Path],
) -> None:
    """Any st_mtime_ns change, even 1 ns, must abort the hygiene write."""
    root, _page = graph_with_page

    with (
        patch(
            "src.graph.link_verification.occ_snapshot",
            return_value=_BASELINE_MTIME_NS,
        ),
        patch("src.graph.link_verification.occ_verify_before_write", return_value=True),
        patch(
            "src.graph.markdown_blocks.read_file_mtime",
            return_value=_BASELINE_MTIME_NS + 1,
        ),
        patch(
            "src.graph.link_verification.atomic_write_bytes_if_unchanged", return_value=True
        ) as write_mock,
    ):
        flagged = flag_block_hygiene_property(
            root,
            "pages/demo.md",
            BLOCK,
            "missing-asset",
        )

    assert not flagged
    write_mock.assert_not_called()


@pytest.mark.asyncio
async def test_verify_registry_batch_url_dead(
    graph_with_page: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, page = graph_with_page
    monkeypatch.setenv("MATRYCA_LINK_VERIFY_STRIKES", "1")
    entry = LinkRegistryEntry(
        kind="url",
        target="https://example.com/dead",
        page_relpath="pages/demo.md",
        block_uuid=BLOCK,
    )
    registry = {entry.registry_key(): entry}

    async def fake_head(_client: object, _url: str) -> int:
        return 404

    with (
        patch("src.graph.link_verification._verify_url_status", new=fake_head),
        patch(
            "src.graph.link_verification.flag_block_hygiene_property",
            return_value=True,
        ) as flag_mock,
    ):
        result = await verify_registry_batch(root, registry, batch_size=5)

    assert result.checked == 1
    assert result.dead_urls == 1
    flag_mock.assert_called_once()
    assert link_registry_path(root).is_file()
    assert registry[entry.registry_key()].flagged is True


@pytest.mark.asyncio
async def test_flagged_url_recovers_when_check_succeeds(
    graph_with_page: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, page = graph_with_page
    monkeypatch.setenv("MATRYCA_LINK_VERIFY_STRIKES", "2")
    entry = LinkRegistryEntry(
        kind="url",
        target="https://example.com/ok",
        page_relpath="pages/demo.md",
        block_uuid=BLOCK,
        strikes=2,
        flagged=True,
    )
    registry = {entry.registry_key(): entry}

    async def fake_ok(_client: object, _url: str) -> int:
        return 200

    with (
        patch("src.graph.link_verification._verify_url_status", new=fake_ok),
        patch(
            "src.graph.link_verification.clear_block_hygiene_property",
            return_value=True,
        ) as clear_mock,
    ):
        result = await verify_registry_batch(root, registry, batch_size=5)

    assert result.checked == 1
    assert registry[entry.registry_key()].strikes == 0
    assert registry[entry.registry_key()].flagged is False
    clear_mock.assert_called_once()


@pytest.mark.asyncio
async def test_flagged_url_stays_flagged_when_clear_fails(
    graph_with_page: tuple[Path, Path],
) -> None:
    root, _page = graph_with_page
    entry = LinkRegistryEntry(
        kind="url",
        target="https://example.com/ok",
        page_relpath="pages/demo.md",
        block_uuid=BLOCK,
        strikes=2,
        flagged=True,
    )
    registry = {entry.registry_key(): entry}

    async def fake_ok(_client: object, _url: str) -> int:
        return 200

    with (
        patch("src.graph.link_verification._verify_url_status", new=fake_ok),
        patch(
            "src.graph.link_verification.clear_block_hygiene_property",
            return_value=False,
        ),
    ):
        await verify_registry_batch(root, registry, batch_size=5)

    assert registry[entry.registry_key()].flagged is True
    assert registry[entry.registry_key()].strikes == 2


def test_flag_block_idempotent_when_property_already_present(
    graph_with_page: tuple[Path, Path],
) -> None:
    root, page = graph_with_page
    merge_page_links_into_registry(root, page, page.read_text(encoding="utf-8"))
    registry = load_link_registry(root)
    asset_key = next(k for k, v in registry.items() if v.kind == "asset")
    entry = registry[asset_key]

    assert flag_block_hygiene_property(
        root,
        entry.page_relpath,
        entry.block_uuid,
        "missing-asset",
    )
    assert flag_block_hygiene_property(
        root,
        entry.page_relpath,
        entry.block_uuid,
        "missing-asset",
    )


def test_register_purges_registry_when_page_deleted(
    graph_with_page: tuple[Path, Path],
) -> None:
    root, page = graph_with_page
    merge_page_links_into_registry(root, page, page.read_text(encoding="utf-8"))
    assert load_link_registry(root)
    page.unlink()
    purged = register_page_links_from_path(root, page)
    assert purged > 0
    assert load_link_registry(root) == {}


def test_merge_prunes_links_removed_from_page(graph_with_page: tuple[Path, Path]) -> None:
    root, page = graph_with_page
    merge_page_links_into_registry(root, page, page.read_text(encoding="utf-8"))
    assert load_link_registry(root)

    stripped = "- Empty page\n"
    page.write_text(stripped, encoding="utf-8")
    merge_page_links_into_registry(root, page, stripped)
    assert load_link_registry(root) == {}


def test_asset_traversal_outside_graph_treated_as_missing(tmp_path: Path) -> None:
    from src.graph.link_verification import _asset_missing

    root = tmp_path / "graph"
    pages = root / "pages"
    pages.mkdir(parents=True)
    outside = tmp_path / "secret.png"
    outside.write_bytes(b"png")
    page = pages / "note.md"
    page.write_text("- img\n  id:: aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa\n", encoding="utf-8")
    assert _asset_missing(root, "pages/note.md", "../../secret.png") is True


def test_load_registry_drops_tampered_page_relpath(tmp_path: Path) -> None:
    root = tmp_path / "graph"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("secret\n", encoding="utf-8")
    reg_path = link_registry_path(root)
    reg_path.write_text(
        json.dumps(
            {
                "version": 1,
                "entries": {
                    "bad": {
                        "kind": "url",
                        "target": "https://example.com",
                        "page_relpath": f"../{outside.name}",
                        "block_uuid": BLOCK,
                    },
                },
            },
        ),
        encoding="utf-8",
    )
    assert load_link_registry(root) == {}


def test_flag_block_rejects_tampered_page_relpath(graph_with_page: tuple[Path, Path]) -> None:
    root, _page = graph_with_page
    assert not flag_block_hygiene_property(
        root,
        "../etc/passwd",
        BLOCK,
        "dead-link",
    )


def test_extract_links_from_page_handles_star_bullet(tmp_path: Path) -> None:
    root = tmp_path / "graph"
    pages = root / "pages"
    pages.mkdir(parents=True)
    page = pages / "star.md"
    page.write_text(
        "\n".join(
            [
                "* Read https://example.com/star",
                "  id:: cccccccc-cccc-cccc-cccc-cccccccccccc",
                "",
            ],
        ),
        encoding="utf-8",
    )
    content = page.read_text(encoding="utf-8")
    entries = extract_links_from_page(root, page, content)
    assert any(e.kind == "url" and e.target == "https://example.com/star" for e in entries)


def test_save_link_registry_uses_atomic_write_bytes(graph_with_page: tuple[Path, Path]) -> None:
    root, _page = graph_with_page
    entries = {
        "https://example.com/ok": LinkRegistryEntry(
            kind="url",
            target="https://example.com/ok",
            page_relpath="pages/demo.md",
            block_uuid=BLOCK,
        ),
    }
    captured: list[tuple[Path, bytes, Path]] = []

    def _capture(path: Path, data: bytes, *, graph_root: Path, **kwargs: object) -> None:
        _ = kwargs
        captured.append((path, data, graph_root))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    with patch("src.graph.link_verification.atomic_write_bytes", side_effect=_capture):
        save_link_registry(root, entries)

    assert len(captured) == 1
    path, data, graph_root = captured[0]
    assert path == link_registry_path(root)
    assert graph_root == root
    payload = json.loads(data.decode("utf-8"))
    assert payload["entries"]["https://example.com/ok"]["target"] == "https://example.com/ok"
    loaded = load_link_registry(root)
    assert loaded["https://example.com/ok"].target == "https://example.com/ok"
