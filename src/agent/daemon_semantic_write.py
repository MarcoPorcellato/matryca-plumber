"""Semantic index write path — OCC commits, lint corrections, structural warnings.

Single-responsibility slice of :mod:`maintenance_daemon` (issue #58). Prompt assembly
helpers used by :class:`~daemon_llm_client.InstructorLLMClient` live here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from loguru import logger
from pydantic import BaseModel, Field

from ..graph.alias_index import AliasIndex, resolve_canonical_page_title
from ..graph.generational_cache import patch_generational_caches_for_paths
from ..graph.global_fence_scanner import compute_page_protected_line_indices
from ..graph.markdown_blocks import (
    atomic_write_bytes,
    atomic_write_bytes_if_unchanged,
    block_property_insert_index,
    bullet_indent_unit,
    file_mtime_drifted,
    locate_block_by_uuid,
    occ_snapshot,
    occ_verify_before_write,
    read_file_mtime_ns,
    strip_lines_for_match,
)
from ..graph.master_catalog import SEMANTIC_INDEX_HEADER, SEMANTIC_INDEX_HEADING
from ..graph.mldoc_properties import parse_logseq_property_line
from ..graph.page_path import page_title_from_path
from ..graph.page_write_lock import page_rmw_lock
from ..graph.path_sandbox import read_graph_file_text
from ..graph.safety.validators import validate_llm_write_diff
from .page_prompt_session import PagePromptSession
from .plumber_modules.backlink_backpropagator import BacklinkCorrection, run_backlink_backpropagator
from .prompt_layout import build_cache_aligned_prompt

STRUCTURAL_LINT_HEADING = "### Matryca Structural Lint"
STRUCTURAL_LINT_HEADER = f"- {STRUCTURAL_LINT_HEADING}"

def _semantic_index_section_present(content: str) -> bool:
    return SEMANTIC_INDEX_HEADING in content


def _structural_lint_section_present(content: str) -> bool:
    return STRUCTURAL_LINT_HEADING in content


_BULLET = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_ID_LINE = re.compile(r"^\s*id::\s*(.+?)\s*$", re.IGNORECASE)
_BLOCK_CATALOG_MAX_CHARS = 8000
_MATRYCA_PLUMBER_LINE = re.compile(r"^\s*matryca-plumber::\s*", re.IGNORECASE)
_WIKILINK = re.compile(r"\[\[([^\]#|]+)(?:\|[^\]]+)?\]\]")

LintType = Literal["auto_wikilink", "tag_hygiene", "anomaly_warning"]


class SemanticLintCorrection(BaseModel):
    """Single semantic lint fix targeting one outliner block."""

    block_uuid: str = Field(description="UUID of the block to enrich (from id:: line)")
    original_text: str = Field(description="Exact bullet-line text excluding id:: properties")
    corrected_text: str = Field(description="Bullet text with added [[WikiLinks]] or #tags")
    lint_type: LintType = Field(description="Lint rule that produced this correction")
    reason: str = Field(description="Brief explanation of why the rule fired")


class SemanticCrossRef(BaseModel):
    """One semantic link extracted from page content."""

    concept: str = Field(description="Short concept label")
    relation: str = Field(description="Relationship type, e.g. related_to, see_also")
    target: str = Field(
        description=(
            "Existing [[Canonical Page Title]] or #tag from AliasIndex; "
            "never invent a new page title when an alias or canonical match exists"
        ),
    )


class SemanticIndexResult(BaseModel):
    """Structured semantic index + Karpathy-style lint payload from the local LLM."""

    summary: str = Field(description="One-sentence page summary")
    cross_references: list[SemanticCrossRef] = Field(default_factory=list)
    suggested_tags: list[str] = Field(default_factory=list)
    moc_pointers: list[str] = Field(
        default_factory=list,
        description=(
            "Suggested [[Map of Content]] links that must already exist in AliasIndex; "
            "prefer alias:: over new pages"
        ),
    )
    semantic_corrections: list[SemanticLintCorrection] = Field(
        default_factory=list,
        description="Safe per-block micro-corrections (additive WikiLinks / tags only)",
    )
def _page_title_from_path(graph_root: Path, path: Path) -> str:
    return page_title_from_path(graph_root, path)


def _normalize_block_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _bullet_inline_text(line: str) -> str:
    match = _BULLET.match(line.rstrip("\n"))
    if not match:
        return ""
    return match.group(2)


def _set_bullet_inline_text(line: str, new_text: str) -> str:
    match = _BULLET.match(line.rstrip("\n"))
    if not match:
        return line
    newline = "\n" if line.endswith("\n") else ""
    return f"{match.group(1)}- {new_text}{newline}"


def _stamp_matryca_plumber_property(
    lines: list[str],
    bullet_idx: int,
    id_idx: int,
    block_end: int,
) -> None:
    """Append ``matryca-plumber:: true`` under the modified block (Logseq audit trail)."""
    stripped = strip_lines_for_match(lines)
    insert_at = block_property_insert_index(stripped, bullet_idx, block_end)
    for i in range(bullet_idx + 1, insert_at):
        if _MATRYCA_PLUMBER_LINE.match(stripped[i]):
            return
    bullet_match = _BULLET.match(stripped[bullet_idx])
    base_ws = bullet_match.group(1) if bullet_match else ""
    indent = base_ws + bullet_indent_unit(stripped, bullet_idx)
    lines.insert(insert_at, f"{indent}matryca-plumber:: true\n")


def _enumerate_blocks_for_prompt(
    content: str,
    *,
    max_chars: int = _BLOCK_CATALOG_MAX_CHARS,
) -> str:
    """Serialize blocks with UUIDs so the LLM can target surgical lint corrections."""
    lines = content.splitlines()
    entries: list[str] = []
    for idx, line in enumerate(lines):
        id_match = _ID_LINE.match(line)
        if not id_match:
            continue
        block_uuid = id_match.group(1).strip()
        bullet_text = ""
        for j in range(idx - 1, -1, -1):
            bullet_match = _BULLET.match(lines[j])
            if bullet_match:
                bullet_text = bullet_match.group(2)
                break
        entries.append(
            f"- block_uuid: {block_uuid}\n  original_text: {bullet_text}",
        )
    if not entries:
        return "(no blocks with id:: found — omit semantic_corrections)"
    included: list[str] = []
    total = 0
    for entry in entries:
        add_len = len(entry) + (1 if included else 0)
        if included and total + add_len > max_chars:
            omitted = len(entries) - len(included)
            included.append(
                f"(block catalog truncated at {max_chars} chars; "
                f"{omitted} block(s) omitted — omit uncatalogued semantic_corrections)",
            )
            break
        if not included and len(entry) > max_chars:
            included.append(entry[:max_chars])
            included.append(
                f"(block catalog truncated at {max_chars} chars; "
                f"{len(entries) - 1} block(s) omitted — omit uncatalogued semantic_corrections)",
            )
            break
        included.append(entry)
        total += add_len
    return "\n".join(included)


def _build_index_task_instruction(page_title: str, content: str) -> str:
    block_catalog = _enumerate_blocks_for_prompt(content)
    return "\n".join(
        [
            "Task: semantic indexing and safe per-block lint for one Logseq OG outliner page.",
            "Output: structured JSON only.",
            "Steps:",
            "1. Read the page title, block catalog, AliasIndex, and page content above.",
            "2. Extract summary, cross_references, suggested_tags, and moc_pointers.",
            "3. Propose semantic_corrections only when every system-prompt safety rule "
            "is satisfied.",
            "4. Prefer existing canonical titles and alias:: over inventing new page names.",
            "",
            f"Page title: {page_title}",
            "",
            f"Blocks available for semantic_corrections:\n{block_catalog}",
        ],
    )


def _build_index_prompt(
    page_title: str,
    content: str,
    *,
    llm_body: str | None = None,
    session: PagePromptSession | None = None,
) -> str:
    if session is not None:
        return session.build_task_prompt(_build_index_task_instruction(page_title, content))
    display_body = llm_body if llm_body is not None else content
    return build_cache_aligned_prompt(
        content=display_body[:8000],
        task_instruction=_build_index_task_instruction(page_title, content),
    )


def _strip_wikilink_brackets(text: str) -> str:
    return re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)


def _rewrite_wikilinks_with_alias_index(text: str, alias_index: AliasIndex | None) -> str:
    if alias_index is None or not text:
        return text

    def _replace(match: re.Match[str]) -> str:
        target = match.group(1).strip()
        canonical = resolve_canonical_page_title(alias_index, target)
        if canonical != target:
            return f"[[{canonical}]]"
        return match.group(0)

    return _WIKILINK.sub(_replace, text)


def _normalize_index_result_aliases(
    result: SemanticIndexResult,
    alias_index: AliasIndex | None,
) -> SemanticIndexResult:
    if alias_index is None:
        return result

    cross_refs: list[SemanticCrossRef] = []
    for ref in result.cross_references:
        target = ref.target
        if target.startswith("[["):
            inner = target.strip("[]")
            canonical = resolve_canonical_page_title(alias_index, inner)
            target = f"[[{canonical}]]" if canonical != inner else target
        cross_refs.append(
            SemanticCrossRef(concept=ref.concept, relation=ref.relation, target=target),
        )

    moc_pointers = [
        (
            f"[[{resolve_canonical_page_title(alias_index, pointer.strip('[]'))}]]"
            if pointer.startswith("[[")
            else pointer
        )
        for pointer in result.moc_pointers
    ]

    corrections: list[SemanticLintCorrection] = []
    for correction in result.semantic_corrections:
        corrections.append(
            SemanticLintCorrection(
                block_uuid=correction.block_uuid,
                original_text=correction.original_text,
                corrected_text=_rewrite_wikilinks_with_alias_index(
                    correction.corrected_text,
                    alias_index,
                ),
                lint_type=correction.lint_type,
                reason=correction.reason,
            ),
        )

    return SemanticIndexResult(
        summary=result.summary,
        cross_references=cross_refs,
        suggested_tags=list(result.suggested_tags),
        moc_pointers=moc_pointers,
        semantic_corrections=corrections,
    )


def _is_safe_additive_correction(original: str, corrected: str, lint_type: LintType) -> bool:
    if lint_type == "anomaly_warning":
        return _normalize_block_text(original) == _normalize_block_text(corrected)
    orig_norm = _normalize_block_text(original)
    corr_norm = _normalize_block_text(corrected)
    if lint_type == "auto_wikilink":
        return orig_norm == _normalize_block_text(_strip_wikilink_brackets(corrected))
    if lint_type == "tag_hygiene":
        orig_plain = re.sub(r"#\S+", "", orig_norm).strip()
        corr_plain = re.sub(r"#\S+", "", _strip_wikilink_brackets(corrected)).strip()
        return orig_plain == corr_plain and len(corr_norm) >= len(orig_norm)
    return orig_norm in corr_norm and len(corr_norm) >= len(orig_norm)


@dataclass
class CorrectionOutcome:
    """Result of applying semantic lint corrections to one page."""

    applied: int = 0
    skipped: int = 0
    skip_reasons: list[str] = field(default_factory=list)
    applied_details: list[str] = field(default_factory=list)
    write_aborted: bool = False
    links_backpropagated: int = 0
def _direct_block_property_lines(
    lines: list[str],
    bullet_idx: int,
    block_end: int,
) -> list[str]:
    """Non-bullet property lines under a block that must survive bullet text edits."""
    stripped = [ln.rstrip("\n") for ln in lines]
    props: list[str] = []
    for i in range(bullet_idx + 1, min(block_end, len(lines))):
        line = stripped[i]
        if _BULLET.match(line):
            continue
        if parse_logseq_property_line(line) or _ID_LINE.match(line):
            props.append(line)
    return props


def apply_semantic_corrections_to_lines(
    lines: list[str],
    corrections: list[SemanticLintCorrection],
) -> CorrectionOutcome:
    """Apply micro-corrections in-place on ``lines`` (bullet text only, UUID-anchored)."""
    outcome = CorrectionOutcome()
    if not corrections:
        return outcome

    protected_lines = compute_page_protected_line_indices("".join(lines))
    stripped = [ln.rstrip("\n") for ln in lines]
    pending: list[tuple[int, int, int, SemanticLintCorrection]] = []
    for correction in corrections:
        located = locate_block_by_uuid(stripped, correction.block_uuid)
        if located is None:
            outcome.skipped += 1
            outcome.skip_reasons.append(f"uuid_not_found:{correction.block_uuid}")
            continue
        bullet_idx, id_idx, block_end = located
        if bullet_idx in protected_lines or any(
            idx in protected_lines for idx in range(bullet_idx, block_end)
        ):
            outcome.skipped += 1
            outcome.skip_reasons.append(f"protected_fence:{correction.block_uuid}")
            continue
        pending.append((bullet_idx, id_idx, block_end, correction))

    for bullet_idx, id_idx, block_end, correction in sorted(
        pending,
        key=lambda item: item[0],
        reverse=True,
    ):
        current_text = _bullet_inline_text(lines[bullet_idx])
        if _normalize_block_text(current_text) != _normalize_block_text(correction.original_text):
            outcome.skipped += 1
            outcome.skip_reasons.append(f"original_mismatch:{correction.block_uuid}")
            continue
        if correction.lint_type == "anomaly_warning":
            outcome.skipped += 1
            outcome.skip_reasons.append(f"anomaly_only:{correction.block_uuid}")
            continue
        if not _is_safe_additive_correction(
            correction.original_text,
            correction.corrected_text,
            correction.lint_type,
        ):
            outcome.skipped += 1
            outcome.skip_reasons.append(f"unsafe_correction:{correction.block_uuid}")
            continue
        if _normalize_block_text(current_text) == _normalize_block_text(correction.corrected_text):
            outcome.skipped += 1
            outcome.skip_reasons.append(f"no_change:{correction.block_uuid}")
            continue
        original_bullet = lines[bullet_idx]
        property_snapshot = _direct_block_property_lines(lines, bullet_idx, block_end)
        lines[bullet_idx] = _set_bullet_inline_text(lines[bullet_idx], correction.corrected_text)

        relocated = locate_block_by_uuid(
            [ln.rstrip("\n") for ln in lines],
            correction.block_uuid,
        )
        if relocated is None:
            lines[bullet_idx] = original_bullet
            outcome.skipped += 1
            outcome.skip_reasons.append(f"id_orphaned:{correction.block_uuid}")
            continue
        _, _, new_block_end = relocated
        preserved = _direct_block_property_lines(lines, bullet_idx, new_block_end)
        if property_snapshot and not all(item in preserved for item in property_snapshot):
            lines[bullet_idx] = original_bullet
            outcome.skipped += 1
            outcome.skip_reasons.append(f"property_lost:{correction.block_uuid}")
            continue

        _stamp_matryca_plumber_property(lines, bullet_idx, id_idx, block_end)
        outcome.applied += 1
        outcome.applied_details.append(
            f"{correction.lint_type}:{correction.block_uuid}:{correction.reason}",
        )
    return outcome


def _format_index_section(
    result: SemanticIndexResult,
    *,
    lint_outcome: CorrectionOutcome | None = None,
) -> str:
    stamp = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "",
        SEMANTIC_INDEX_HEADER,
        f"- indexed-at:: {stamp}",
        f"- summary:: {result.summary.strip()}",
    ]
    if result.suggested_tags:
        tag_line = " ".join(
            t if t.startswith("#") else f"#{t.lstrip('#')}" for t in result.suggested_tags
        )
        lines.append(f"- suggested-tags:: {tag_line}")
    if result.moc_pointers:
        lines.append("- moc-pointers::")
        for pointer in result.moc_pointers:
            target = pointer if pointer.startswith("[[") else f"[[{pointer.strip('[]')}]]"
            lines.append(f"  - {target}")
    if result.cross_references:
        lines.append("- cross-references::")
        for ref in result.cross_references:
            target = ref.target
            if not (target.startswith("[[") or target.startswith("#")):
                target = f"[[{target.strip('[]')}]]"
            lines.append(f"  - {ref.concept} ({ref.relation}) → {target}")
    if lint_outcome is not None and lint_outcome.applied_details:
        lines.append("- semantic-lint-applied::")
        for detail in lint_outcome.applied_details:
            lines.append(f"  - {detail}")
    warnings = [c for c in result.semantic_corrections if c.lint_type == "anomaly_warning"]
    if warnings:
        lines.append("- semantic-lint-warnings::")
        for warning in warnings:
            lines.append(f"  - {warning.reason} (block {warning.block_uuid[:8]}…)")
    lines.append("")
    return "\n".join(lines)


def append_structural_lint_warning(
    graph_root: Path,
    page_path: Path,
    malformed_refs: list[str],
) -> bool:
    """Append a non-destructive structural lint section (preserves existing malformed refs)."""

    if not page_path.is_file() or not malformed_refs:
        return False
    baseline_mtime = occ_snapshot(page_path)
    if baseline_mtime is None:
        return False
    if not occ_verify_before_write(page_path, baseline_mtime):
        logger.warning(
            "OCC Conflict: User modified {} during inference. Aborting write.",
            page_path,
        )
        return False

    with page_rmw_lock(page_path):
        if file_mtime_drifted(page_path, baseline_mtime):
            logger.warning(
                "OCC Conflict: User modified {} during inference. Aborting write.",
                page_path,
            )
            return False
        text = read_graph_file_text(page_path, graph_root, errors="replace")
        if _structural_lint_section_present(text):
            return False

        sample = malformed_refs[:5]
        section_lines = [
            "",
            STRUCTURAL_LINT_HEADER,
            "- malformed-block-refs::",
        ]
        for ref in sample:
            section_lines.append(f"  - (({ref}))")
        if len(malformed_refs) > len(sample):
            section_lines.append(f"  - ... and {len(malformed_refs) - len(sample)} more")
        section_lines.extend(
            [
                "- todo:: #todo [[Matryca Broken Reference]] — fix ((uuid)) typos in Logseq",
                "",
            ],
        )
        new_text = text.rstrip("\n") + "\n" + "\n".join(section_lines)
        return atomic_write_bytes_if_unchanged(
            page_path,
            new_text.encode("utf-8"),
            graph_root=graph_root,
            baseline_mtime=baseline_mtime,
            validate_block_refs=False,
            robot_commit_summary="appended structural lint warning",
        )


def apply_semantic_page_result(
    graph_root: Path,
    page_path: Path,
    page_title: str,
    result: SemanticIndexResult,
    *,
    backpropagate: bool = False,
    alias_index: AliasIndex | None = None,
    disable_semantic_corrections: bool = True,
    baseline_mtime: float | None = None,
) -> CorrectionOutcome:
    """Lint blocks surgically, then append the semantic index (one locked transaction)."""

    lint_outcome = CorrectionOutcome()
    if baseline_mtime is None and page_path.is_file():
        baseline_mtime = occ_snapshot(page_path)
    if baseline_mtime is not None and not occ_verify_before_write(page_path, baseline_mtime):
        logger.warning(
            "OCC Conflict: User modified {} during inference. Aborting write.",
            page_path,
        )
        lint_outcome.write_aborted = True
        return lint_outcome

    with page_rmw_lock(page_path):
        if page_path.is_file():
            prev = read_graph_file_text(page_path, graph_root, errors="replace")
            if baseline_mtime is None:
                baseline_mtime = read_file_mtime_ns(page_path)
        else:
            prev = ""
            baseline_mtime = None
        if not prev.strip():
            lint_outcome.skipped += 1
            lint_outcome.skip_reasons.append("empty_page_body")
            return lint_outcome
        if baseline_mtime is not None and file_mtime_drifted(page_path, baseline_mtime):
            logger.warning(
                "OCC Conflict: User modified {} during inference. Aborting write.",
                page_path,
            )
            lint_outcome.write_aborted = True
            return lint_outcome
        lines = prev.splitlines(keepends=True)
        if disable_semantic_corrections:
            pass
        else:
            lint_outcome = apply_semantic_corrections_to_lines(lines, result.semantic_corrections)
        body = "".join(lines)
        if not _semantic_index_section_present(body):
            body = body.rstrip("\n") + _format_index_section(result, lint_outcome=lint_outcome)
        safety = validate_llm_write_diff(prev, body)
        if not safety.ok:
            logger.warning(
                "L0 safety rejection on {}: {}",
                page_path,
                safety.reason,
            )
            lint_outcome.write_aborted = True
            lint_outcome.skip_reasons.append(f"l0_safety:{safety.reason}")
            return lint_outcome
        commit_summary = f"semantic index update on {page_title}"
        if baseline_mtime is not None and not atomic_write_bytes_if_unchanged(
            page_path,
            body.encode("utf-8"),
            graph_root=graph_root,
            baseline_mtime=baseline_mtime,
            robot_commit_summary=commit_summary,
        ):
            logger.warning(
                "File modified by user during inference, aborting write to prevent data loss: {}",
                page_path,
            )
            lint_outcome.write_aborted = True
            return lint_outcome
        if baseline_mtime is None:
            atomic_write_bytes(
                page_path,
                body.encode("utf-8"),
                graph_root=graph_root,
                robot_commit_summary=commit_summary,
            )
    patch_generational_caches_for_paths(graph_root, [page_path])

    links_backpropagated = 0
    if backpropagate and lint_outcome.applied > 0:
        backlink_corrections = [
            BacklinkCorrection(
                block_uuid=item.block_uuid,
                original_text=item.original_text,
                corrected_text=item.corrected_text,
                lint_type=item.lint_type,
                reason=item.reason,
            )
            for item in result.semantic_corrections
        ]
        backprop_outcome = run_backlink_backpropagator(
            graph_root,
            page_path,
            page_title,
            backlink_corrections,
            lint_outcome.applied_details,
            alias_index=alias_index,
        )
        links_backpropagated = sum(
            1 for detail in backprop_outcome.details if detail.startswith("backprop:")
        )
    lint_outcome.links_backpropagated = links_backpropagated
    return lint_outcome


def run_dual_embedding_after_semantic_write(
    graph_root: Path,
    page_path: Path,
    page_title: str,
    llm_client: object,
) -> None:
    """Best-effort dual block indexing when ``MATRYCA_DUAL_EMBEDDING_ENABLED`` is set."""

    from ..semantic.applicability import InstructorApplicabilityLLM
    from ..semantic.config import SemanticRuntimeConfig
    from ..semantic.embedding import get_openai_embedding_client
    from ..semantic.indexer import index_page_blocks
    from ..semantic.store import release_block_vector_store

    runtime_config = SemanticRuntimeConfig.from_env()
    if not runtime_config.dual_embedding_enabled:
        return
    try:
        index_page_blocks(
            graph_root,
            page_path,
            page_title,
            llm_client=InstructorApplicabilityLLM(llm_client),
            embedding_client=get_openai_embedding_client(),
            runtime_config=runtime_config,
        )
    except Exception as exc:  # noqa: BLE001 — never fail semantic write path
        logger.bind(page=page_title, path=str(page_path)).warning(
            "Dual embedding sidecar failed: {}",
            exc,
        )
    finally:
        release_block_vector_store(graph_root)


def append_semantic_index(
    graph_root: Path,
    page_path: Path,
    result: SemanticIndexResult,
) -> None:
    """Append a semantic index section without modifying existing user content."""
    if page_path.is_file():
        prev = read_graph_file_text(page_path, graph_root, errors="replace")
        if _semantic_index_section_present(prev):
            return
    apply_semantic_page_result(
        graph_root,
        page_path,
        _page_title_from_path(graph_root, page_path),
        result,
    )

__all__ = [
    "STRUCTURAL_LINT_HEADER",
    "STRUCTURAL_LINT_HEADING",
    "CorrectionOutcome",
    "LintType",
    "SemanticCrossRef",
    "SemanticCrossRef",
    "SemanticIndexResult",
    "SemanticLintCorrection",
    "_enumerate_blocks_for_prompt",
    "append_semantic_index",
    "append_structural_lint_warning",
    "apply_semantic_corrections_to_lines",
    "apply_semantic_page_result",
    "run_dual_embedding_after_semantic_write",
    "_semantic_index_section_present",
]
