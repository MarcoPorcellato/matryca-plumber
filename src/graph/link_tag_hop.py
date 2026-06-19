"""Structural hop graph over Logseq ``pages/**/*.md`` (wikilinks, tags, schema rings).

Inspired by multi-hop BFS in ``obsidian-graph``, without embeddings or a database.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import cast
from urllib.parse import unquote

from .path_sandbox import read_graph_file_text

_WIKILINK = re.compile(r"\[\[([^\]#|]+)(?:\|[^\]]+)?\]\]")
# Inline #tag — avoid markdown headings (line-start # followed by space).
_TAG_INLINE = re.compile(r"(?<![\w/])#([\w/-]+)")
_TAGS_PROP = re.compile(r"^\s*tags::\s*(.+)\s*$", re.MULTILINE)
_TYPE_PROP = re.compile(r"^\s*type::\s*(.+)\s*$", re.MULTILINE)
_DOMAIN_PROP = re.compile(r"^\s*domain::\s*(.+)\s*$", re.MULTILINE)


def _line_is_atx_markdown_heading(stripped: str) -> bool:
    """True for ``# Title`` / ``## Section`` lines; false for ``#tag`` / ``#2024/01``."""
    if not stripped.startswith("#"):
        return False
    if re.match(r"^#\s+\S", stripped):
        return True
    return bool(re.match(r"^#{2,}\s", stripped))


def _iter_page_files(graph_root: Path) -> list[Path]:
    from .alias_index import iter_scannable_pages_markdown

    return iter_scannable_pages_markdown(graph_root)


def _resolve_target_to_stem(target: str, pages_dir: Path) -> str | None:
    """Map a wikilink target string to an existing page stem under ``pages/``."""
    raw = target.strip()
    if not raw:
        return None
    candidates = [
        raw,
        raw.replace("/", "_"),
        unquote(raw),
        unquote(raw).replace("/", "_"),
        raw.replace(" ", "_"),
    ]
    seen: set[str] = set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        path = pages_dir / f"{c}.md"
        if path.is_file():
            return path.stem
    return None


def _extract_inline_tags(text: str) -> set[str]:
    tags: set[str] = set()
    for line in text.splitlines():
        stripped = line.lstrip()
        if _line_is_atx_markdown_heading(stripped):
            continue
        for m in _TAG_INLINE.finditer(line):
            tags.add(m.group(1).lower())
    return tags


def _tags_prop_values(text: str) -> set[str]:
    out: set[str] = set()
    for m in _TAGS_PROP.finditer(text):
        parts = re.split(r"[,|]", m.group(1))
        for p in parts:
            t = p.strip().lstrip("#").strip().lower()
            if t:
                out.add(t)
    return out


def _first_prop(pattern: re.Pattern[str], text: str) -> str | None:
    m = pattern.search(text)
    if not m:
        return None
    return m.group(1).strip()


def _add_ring(edges: dict[str, set[tuple[str, str]]], group: list[str], reason: str) -> None:
    """Connect sorted stems in a simple ring so each node has O(1) schema neighbors."""
    if len(group) < 2:
        return
    group = sorted(set(group))
    n = len(group)
    for i in range(n):
        a, b = group[i], group[(i + 1) % n]
        edges[a].add((b, reason))
        edges[b].add((a, reason))


def build_structural_graph(graph_root: str | Path) -> dict[str, set[tuple[str, str]]]:
    """Undirected multi-reason adjacency: wikilink, tag, same_type, same_domain."""
    root = Path(graph_root).expanduser().resolve(strict=False)
    pages_dir = root / "pages"
    paths = _iter_page_files(root)
    stems = [p.stem for p in paths]

    edges: dict[str, set[tuple[str, str]]] = defaultdict(set)
    stem_set = set(stems)

    tag_to_pages: dict[str, set[str]] = defaultdict(set)
    type_groups: dict[str, list[str]] = defaultdict(list)
    domain_groups: dict[str, list[str]] = defaultdict(list)

    for path in paths:
        stem = path.stem
        try:
            text = read_graph_file_text(path, root, errors="replace")
        except OSError:
            continue

        for m in _WIKILINK.finditer(text):
            other = _resolve_target_to_stem(m.group(1), pages_dir)
            if other and other != stem and other in stem_set:
                edges[stem].add((other, "wikilink"))
                edges[other].add((stem, "wikilink"))

        tags = _extract_inline_tags(text) | _tags_prop_values(text)
        for t in tags:
            tag_to_pages[t].add(stem)

        tv = _first_prop(_TYPE_PROP, text)
        if tv:
            type_groups[tv.lower()].append(stem)
        dv = _first_prop(_DOMAIN_PROP, text)
        if dv:
            domain_groups[dv.lower()].append(stem)

    for pages in tag_to_pages.values():
        plist = sorted(pages)
        n = len(plist)
        if n < 2:
            continue
        for i in range(n):
            for j in range(i + 1, n):
                a, b = plist[i], plist[j]
                edges[a].add((b, "tag"))
                edges[b].add((a, "tag"))

    for group in type_groups.values():
        _add_ring(edges, group, "same_type")
    for group in domain_groups.values():
        _add_ring(edges, group, "same_domain")

    return dict(edges)


def bfs_hops(
    graph_root: str | Path,
    seeds: list[str],
    *,
    max_depth: int = 3,
    max_per_level: int = 20,
) -> tuple[list[dict[str, object]], list[tuple[str, str, str, int]]]:
    """Breadth-first expansion over the structural graph.

    Returns:
        levels: list per depth of ``{"stems": [...], "new": [...]}`` metadata.
        edges_used: ``(from_stem, to_stem, reason, depth)`` for the traversal tree.
    """
    pages_dir = Path(graph_root).expanduser().resolve(strict=False) / "pages"
    adj = build_structural_graph(graph_root)

    resolved_seeds: list[str] = []
    for s in seeds:
        st = _resolve_target_to_stem(s, pages_dir)
        if st is None and (pages_dir / f"{s}.md").is_file():
            st = s
        if st and st not in resolved_seeds:
            resolved_seeds.append(st)

    visited: set[str] = set(resolved_seeds)
    frontier = list(resolved_seeds)
    levels: list[dict[str, object]] = [
        {"depth": 0, "stems": list(resolved_seeds), "new": list(resolved_seeds)},
    ]
    edges_used: list[tuple[str, str, str, int]] = []

    for depth in range(1, max_depth + 1):
        if not frontier:
            break
        next_frontier: list[str] = []
        candidates: list[tuple[str, str, str]] = []
        for u in frontier:
            for v, reason in sorted(adj.get(u, ())):
                if v not in visited:
                    candidates.append((u, v, reason))
        candidates.sort(key=lambda t: (t[1], t[2], t[0]))
        added = 0
        for u, v, reason in candidates:
            if added >= max_per_level:
                break
            if v in visited:
                continue
            visited.add(v)
            next_frontier.append(v)
            edges_used.append((u, v, reason, depth))
            added += 1
        levels.append({"depth": depth, "stems": list(next_frontier), "new": list(next_frontier)})
        frontier = next_frontier

    return levels, edges_used


def structural_degrees(graph_root: str | Path) -> dict[str, int]:
    """Undirected degree per page stem (unique neighbors)."""
    adj = build_structural_graph(graph_root)
    root = Path(graph_root).expanduser().resolve(strict=False)
    stems = {p.stem for p in _iter_page_files(root)}
    out: dict[str, int] = {}
    for s in stems:
        out[s] = len({n for (n, _) in adj.get(s, ())})
    return out


def format_hop_report_markdown(
    graph_root: str | Path,
    seeds: list[str],
    *,
    max_depth: int = 3,
    max_per_level: int = 20,
) -> str:
    """Human-readable Markdown for MCP ``traverse_logseq_structural_hops``."""
    root = Path(graph_root).expanduser().resolve(strict=False)
    levels, edges = bfs_hops(
        root,
        seeds,
        max_depth=max_depth,
        max_per_level=max_per_level,
    )
    lines = [
        "# Structural hop traversal (BFS)",
        "",
        f"- **Graph:** `{root}`",
        f"- **Seeds:** {', '.join(seeds) or '(none)'}",
        f"- **max_depth:** {max_depth} · **max_per_level:** {max_per_level}",
        "",
        "## Levels",
        "",
    ]
    for lvl in levels:
        d = int(cast(int, lvl["depth"]))
        new = cast(list[str], lvl["new"])
        lines.append(f"- **Depth {d}:** {len(new)} new page(s)")
        for s in new[:50]:
            lines.append(f"  - [[{s}]]")
        if len(new) > 50:
            lines.append("  - _(truncated)_")
        lines.append("")
    lines.append("## Traversal edges (first expansion per hop)")
    lines.append("")
    if not edges:
        lines.append("_No edges beyond seeds (isolated or missing pages)._")
    else:
        for u, v, r, d in edges:
            lines.append(f"- d{d}: `{u}` → `{v}` _({r})_")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def format_hub_orphan_markdown(
    graph_root: str | Path,
    *,
    hub_limit: int = 15,
    orphan_limit: int = 15,
) -> str:
    """High-degree hubs and low-degree orphans (structural graph only)."""
    root = Path(graph_root).expanduser().resolve(strict=False)
    deg = structural_degrees(root)
    if not deg:
        return "# Structural hubs / orphans\n\n(No pages under `pages/`.)"

    paths = {p.stem: p for p in _iter_page_files(root)}
    mtimes: dict[str, int] = {}
    for stem, path in paths.items():
        try:
            mtimes[stem] = path.stat().st_mtime_ns
        except OSError:
            mtimes[stem] = 0

    ranked = sorted(deg.items(), key=lambda kv: (-kv[1], kv[0]))
    hubs = ranked[:hub_limit]
    orphans = sorted(deg.items(), key=lambda kv: (kv[1], -mtimes.get(kv[0], 0)))[:orphan_limit]

    lines = [
        "# Structural hubs / orphans",
        "",
        f"- **Graph:** `{root}`",
        "",
        "## Hub candidates (high neighbor count)",
        "",
    ]
    for stem, d in hubs:
        lines.append(f"- [[{stem}]] — **{d}** neighbor(s)")
    lines.extend(["", "## Orphan candidates (few neighbors)", ""])
    for stem, d in orphans:
        lines.append(f"- [[{stem}]] — **{d}** neighbor(s)")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


__all__ = [
    "bfs_hops",
    "build_structural_graph",
    "format_hop_report_markdown",
    "format_hub_orphan_markdown",
    "structural_degrees",
]
