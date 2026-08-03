"""Security and isolation contract for the external Shadow cache resolver."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from src.shadow.cache_location import (
    ShadowCacheLocationError,
    legacy_graph_local_shadow_db_path,
    resolve_shadow_cache_location,
)


def _graph(tmp_path: Path, name: str = "graph") -> Path:
    root = tmp_path / name
    (root / "pages").mkdir(parents=True)
    return root


def _symlink(target: Path, link: Path, *, target_is_directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (AttributeError, NotImplementedError, OSError) as exc:
        pytest.skip(f"symlinks unavailable: {exc}")


@pytest.mark.parametrize(
    ("platform_name", "override_key", "expected"),
    [
        ("darwin", None, Path("Library/Caches/matryca-plumber")),
        ("linux", None, Path(".cache/matryca-plumber")),
        ("linux", "XDG_CACHE_HOME", Path("matryca-plumber")),
        ("win32", "LOCALAPPDATA", Path("matryca-plumber/Cache")),
    ],
)
def test_platform_default_cache_roots(
    tmp_path: Path,
    platform_name: str,
    override_key: str | None,
    expected: Path,
) -> None:
    graph = _graph(tmp_path)
    home = tmp_path / "home"
    env: dict[str, str] = {}
    expected_root = home / expected
    if override_key is not None:
        override_root = tmp_path / "platform-cache"
        env[override_key] = str(override_root)
        expected_root = override_root / expected

    location = resolve_shadow_cache_location(
        graph,
        env=env,
        platform_name=platform_name,
        home=home,
    )

    assert location.cache_root == expected_root.resolve(strict=False)
    assert location.database_path == location.shadow_dir / "shadow.sqlite"
    assert location.writer_lock_path == location.shadow_dir / "shadow.writer.flock"
    assert location.shadow_db_wal_path == location.shadow_dir / "shadow.sqlite-wal"
    assert location.shadow_db_shm_path == location.shadow_dir / "shadow.sqlite-shm"
    assert location.shadow_dir.is_relative_to(location.cache_root)


def test_explicit_external_cache_override(tmp_path: Path) -> None:
    graph = _graph(tmp_path)
    cache = tmp_path / "operator-cache"

    location = resolve_shadow_cache_location(
        graph,
        env={"MATRYCA_CACHE_PATH": str(cache)},
    )

    assert location.cache_root == cache.resolve(strict=False)


def test_graph_identity_is_stable_private_and_isolated(tmp_path: Path) -> None:
    first = _graph(tmp_path, "Private Graph Name")
    second = _graph(tmp_path, "Second Graph")
    cache = tmp_path / "cache"
    env = {"MATRYCA_CACHE_PATH": str(cache)}

    first_a = resolve_shadow_cache_location(first, env=env)
    first_b = resolve_shadow_cache_location(first, env=env)
    second_location = resolve_shadow_cache_location(second, env=env)

    assert first_a.graph_id == first_b.graph_id
    assert first_a.graph_id.startswith("v1-")
    assert "Private" not in first_a.graph_id
    assert first_a.graph_id != second_location.graph_id
    assert first_a.shadow_dir != second_location.shadow_dir


def test_graph_symlink_alias_has_same_identity(tmp_path: Path) -> None:
    graph = _graph(tmp_path)
    alias = tmp_path / "graph-alias"
    _symlink(graph, alias, target_is_directory=True)
    cache = tmp_path / "cache"
    env = {"MATRYCA_CACHE_PATH": str(cache)}

    direct = resolve_shadow_cache_location(graph, env=env)
    through_alias = resolve_shadow_cache_location(alias, env=env)

    assert direct.graph_id == through_alias.graph_id
    assert direct.shadow_dir == through_alias.shadow_dir


def test_relative_or_graph_local_cache_root_fails_closed(tmp_path: Path) -> None:
    graph = _graph(tmp_path)

    with pytest.raises(ShadowCacheLocationError) as relative:
        resolve_shadow_cache_location(graph, env={"MATRYCA_CACHE_PATH": "cache"})
    assert relative.value.reason == "cache_root_not_absolute"

    with pytest.raises(ShadowCacheLocationError) as nested:
        resolve_shadow_cache_location(
            graph,
            env={"MATRYCA_CACHE_PATH": str(graph / ".cache")},
        )
    assert nested.value.reason == "cache_path_inside_graph"


def test_cache_symlink_alias_into_graph_fails_closed(tmp_path: Path) -> None:
    graph = _graph(tmp_path)
    target = graph / "cache-target"
    target.mkdir()
    alias = tmp_path / "external-alias"
    _symlink(target, alias, target_is_directory=True)

    with pytest.raises(ShadowCacheLocationError) as exc_info:
        resolve_shadow_cache_location(
            graph,
            env={"MATRYCA_CACHE_PATH": str(alias)},
        )

    assert exc_info.value.reason == "cache_root_symlink"


def test_shadow_directory_symlink_escape_fails_before_creation(tmp_path: Path) -> None:
    graph = _graph(tmp_path)
    cache = tmp_path / "cache"
    baseline = resolve_shadow_cache_location(
        graph,
        env={"MATRYCA_CACHE_PATH": str(cache)},
    )
    graph_bucket = cache / "graphs" / baseline.graph_id
    graph_bucket.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    _symlink(outside, graph_bucket / "shadow", target_is_directory=True)

    with pytest.raises(ShadowCacheLocationError) as exc_info:
        resolve_shadow_cache_location(
            graph,
            env={"MATRYCA_CACHE_PATH": str(cache)},
        )

    assert exc_info.value.reason == "shadow_directory_escape"


@pytest.mark.parametrize(
    ("filename", "reason"),
    [
        ("shadow.sqlite", "database_symlink"),
        ("shadow.sqlite-wal", "wal_symlink"),
        ("shadow.sqlite-shm", "shm_symlink"),
        ("shadow.writer.flock", "writer_lock_symlink"),
    ],
)
def test_database_and_lock_symlinks_fail_closed(
    tmp_path: Path,
    filename: str,
    reason: str,
) -> None:
    graph = _graph(tmp_path)
    cache = tmp_path / "cache"
    baseline = resolve_shadow_cache_location(
        graph,
        env={"MATRYCA_CACHE_PATH": str(cache)},
    )
    baseline.shadow_dir.mkdir(parents=True)
    outside = tmp_path / f"outside-{filename}"
    outside.write_text("not a database", encoding="utf-8")
    _symlink(outside, baseline.shadow_dir / filename)

    with pytest.raises(ShadowCacheLocationError) as exc_info:
        resolve_shadow_cache_location(
            graph,
            env={"MATRYCA_CACHE_PATH": str(cache)},
        )

    assert exc_info.value.reason == reason


def test_ensure_directory_uses_private_permissions(tmp_path: Path) -> None:
    graph = _graph(tmp_path)
    location = resolve_shadow_cache_location(
        graph,
        env={"MATRYCA_CACHE_PATH": str(tmp_path / "cache")},
    )

    created = location.ensure_directory()

    assert created.is_dir()
    if os.name == "posix":
        for directory in (
            location.cache_root,
            location.cache_root / "graphs",
            location.shadow_dir.parent,
            location.shadow_dir,
        ):
            assert stat.S_IMODE(directory.stat().st_mode) == 0o700


def test_legacy_locator_is_detection_only_and_graph_local(tmp_path: Path) -> None:
    graph = _graph(tmp_path)

    legacy = legacy_graph_local_shadow_db_path(graph)

    assert legacy == graph / ".matryca_semantic_cache" / "shadow.sqlite"
    assert legacy.is_relative_to(graph)
    assert not legacy.exists()
