"""Matryca Plumber cognitive lint plugins (env-gated)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from ...graph.path_sandbox import read_graph_file_text
from ..page_prompt_session import PagePromptSession, build_page_prompt_session
from ..plumber_config import PlumberLintConfig
from ._shared import ModuleOutcome, is_journal_page_path
from .auto_split import run_auto_split
from .dangling_healer import run_dangling_healer
from .entity_consolidation import run_entity_consolidation
from .marpa_framework import run_marpa_framework
from .property_hygiene import run_property_hygiene


@dataclass
class CognitiveLintOutcome:
    """Aggregate result from all enabled cognitive modules."""

    modules_run: list[str] = field(default_factory=list)
    pages_created: list[str] = field(default_factory=list)
    pages_modified: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)


def _rebuild_prompt_session(
    graph_root: Path,
    page_path: Path,
    page_title: str,
    content: str,
    *,
    config: PlumberLintConfig,
) -> PagePromptSession:
    """Build a fresh KV-cache session from on-disk page text."""
    from ..semantic_lint_prompts import build_semantic_lint_system_prompt

    alias_index = None
    try:
        from ...graph.generational_cache import cached_build_alias_index

        alias_index = cached_build_alias_index(graph_root)
    except OSError:
        alias_index = None
    return build_page_prompt_session(
        graph_root,
        page_title,
        content,
        config=config,
        stable_system=build_semantic_lint_system_prompt(),
        page_path=page_path,
        alias_index=alias_index,
    )


def _run_cognitive_module_safe(
    module_name: str,
    runner: Callable[[], ModuleOutcome],
    outcome: CognitiveLintOutcome,
) -> ModuleOutcome:
    """Execute one cognitive module; log and skip on LLM/JSON/domain faults."""
    try:
        sub = runner()
    except Exception as exc:  # noqa: BLE001 - isolate modules; never abort daemon cycle
        logger.warning("[COGNITIVE LLM FAULT] {} skipped: {}", module_name, exc)
        outcome.modules_run.append(module_name)
        outcome.details.append(f"{module_name}:skipped:{exc}")
        return ModuleOutcome()
    outcome.modules_run.append(module_name)
    outcome.pages_created.extend(sub.pages_created)
    outcome.pages_modified.extend(sub.pages_modified)
    outcome.details.extend(sub.details)
    return sub


def _refresh_content_if_on_disk(page_path: Path, graph_root: Path, content: str) -> str:
    """Re-read page content from disk if a module wrote it; else keep the in-memory copy."""
    if page_path.is_file():
        return read_graph_file_text(page_path, graph_root, errors="replace")
    return content


def run_cognitive_lint_pipeline(
    graph_root: Path,
    page_path: Path,
    page_title: str,
    content: str,
    *,
    llm: object,
    config: PlumberLintConfig,
    prompt_session: PagePromptSession | None = None,
) -> tuple[CognitiveLintOutcome, PagePromptSession | None]:
    """Run enabled cognitive lint modules before the semantic index pass."""
    outcome = CognitiveLintOutcome()
    if not config.any_enabled:
        return outcome, prompt_session

    journal_page = is_journal_page_path(graph_root, page_path)
    initial_content = content

    session = prompt_session
    if session is None:
        session = _rebuild_prompt_session(
            graph_root,
            page_path,
            page_title,
            content,
            config=config,
        )
    llm_context = session.stable_page_block

    if config.marpa_framework and not journal_page:
        _run_cognitive_module_safe(
            "marpa_framework",
            lambda: run_marpa_framework(
                graph_root,
                page_path,
                page_title,
                content,
                llm=llm,
                config=config,
                llm_context=llm_context,
            ),
            outcome,
        )
        content = _refresh_content_if_on_disk(page_path, graph_root, content)

    if config.heal_dangling:
        _run_cognitive_module_safe(
            "heal_dangling",
            lambda: run_dangling_healer(
                graph_root,
                page_path,
                page_title,
                content,
                llm=llm,
                max_words=config.dangling_max_words,
                config=config,
            ),
            outcome,
        )

    if config.entity_consolidation and not journal_page:
        _run_cognitive_module_safe(
            "entity_consolidation",
            lambda: run_entity_consolidation(
                graph_root,
                page_path,
                page_title,
                content,
                llm=llm,
                threshold=config.similarity_threshold,
                config=config,
                llm_context=llm_context,
            ),
            outcome,
        )

    if config.auto_split:
        _run_cognitive_module_safe(
            "auto_split",
            lambda: run_auto_split(
                graph_root,
                page_path,
                page_title,
                threshold=config.split_block_threshold,
            ),
            outcome,
        )
        content = _refresh_content_if_on_disk(page_path, graph_root, content)

    if config.property_hygiene and not journal_page:
        _run_cognitive_module_safe(
            "property_hygiene",
            lambda: run_property_hygiene(
                graph_root,
                page_path,
                page_title,
                content,
                llm=llm,
                rules_path=config.property_rules_path,
                infer_missing=config.infer_missing_properties,
                config=config,
                llm_context=llm_context,
            ),
            outcome,
        )

    content = _refresh_content_if_on_disk(page_path, graph_root, content)
    disk_changed = content != initial_content or page_title in outcome.pages_modified
    if disk_changed and session is not None:
        session = _rebuild_prompt_session(
            graph_root,
            page_path,
            page_title,
            content,
            config=config,
        )

    return outcome, session


__all__ = ["CognitiveLintOutcome", "run_cognitive_lint_pipeline"]
