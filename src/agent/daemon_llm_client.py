"""Daemon LLM client — semantic ``index_page`` adapter over :mod:`llm_client` (issue #58 slice)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Protocol

from ..graph.alias_index import AliasIndex
from ..utils.token_logger import OperationType
from .daemon_semantic_write import (
    SemanticIndexResult,
    _build_index_prompt,
    _normalize_index_result_aliases,
)
from .llm_client import InstructorLLMClient as _BaseInstructorLLMClient
from .llm_context_payload import prepare_llm_context_payload
from .page_prompt_session import PagePromptSession, build_page_prompt_session
from .plumber_config import load_plumber_lint_config
from .plumber_llm import BootstrapSummaryResult, GraphInsightsLLMResult
from .plumber_modules.semantic_cache_router import (
    cache_get,
    cache_put,
    semantic_cache_key,
    validate_cached_model,
)
from .semantic_lint_prompts import build_semantic_lint_system_prompt


class LLMClient(Protocol):
    """Minimal LLM surface used by the daemon (for tests)."""

    def index_page(
        self,
        page_title: str,
        content: str,
        *,
        page_path: Path | None = None,
        graph_root: Path | None = None,
        alias_index: AliasIndex | None = None,
        enable_semantic_routing: bool = False,
        llm_context: str | None = None,
        prompt_session: PagePromptSession | None = None,
    ) -> tuple[SemanticIndexResult, dict[str, int]]:
        """Return structured index and token usage dict with prompt/completion keys."""
        ...

    def harvest_page_summary(
        self,
        page_title: str,
        content: str,
        *,
        page_path: Path | None = None,
        graph_root: Path | None = None,
        task_instruction: str | None = None,
    ) -> BootstrapSummaryResult:
        """Return a one-sentence bootstrap summary."""
        ...

    def generate_graph_insights(
        self,
        *,
        metrics_json: str,
        graph_root: Path,
    ) -> GraphInsightsLLMResult:
        """Return structured graph diagnostics."""
        ...


class InstructorLLMClient(_BaseInstructorLLMClient):
    """Daemon LLM client; adds semantic ``index_page`` with alias normalization."""

    def index_page(
        self,
        page_title: str,
        content: str,
        *,
        page_path: Path | None = None,
        graph_root: Path | None = None,
        alias_index: AliasIndex | None = None,
        enable_semantic_routing: bool = False,
        llm_context: str | None = None,
        prompt_session: PagePromptSession | None = None,
    ) -> tuple[SemanticIndexResult, dict[str, int]]:
        config = load_plumber_lint_config()
        session = prompt_session
        if session is None and graph_root is not None:
            session = build_page_prompt_session(
                graph_root,
                page_title,
                content,
                config=config,
                stable_system=build_semantic_lint_system_prompt(),
                page_path=page_path,
                alias_index=alias_index,
            )
        elif session is None and llm_context is not None:
            session = None
        if session is None and llm_context is None and graph_root is not None:
            llm_context, _ = prepare_llm_context_payload(
                graph_root,
                page_title,
                content,
                config=config,
            )
        prompt = _build_index_prompt(
            page_title,
            content,
            llm_body=llm_context,
            session=session,
        )
        kv_prefix_hash: str | None = None
        if session is not None:
            session.frozen.verify_unchanged()
            kv_prefix_hash = session.prefix_sha256
        started = time.perf_counter()
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        routing_enabled = enable_semantic_routing and config.semantic_routing
        from ..utils.agent_debug_log import agent_debug_log

        agent_debug_log(
            location="daemon_llm_client.py:index_page",
            message="index_page start",
            hypothesis_id="H5",
            data={
                "page_title": page_title,
                "content_len": len(content),
                "prompt_len": len(prompt),
                "has_session": session is not None,
            },
        )
        try:
            if routing_enabled and page_path is not None and graph_root is not None:
                key = semantic_cache_key(page_path, "semantic_index")
                cached = cache_get(graph_root, "index", key)
                if cached is not None:
                    loaded = validate_cached_model(
                        cached,
                        SemanticIndexResult,
                        graph_root=graph_root,
                        namespace="index",
                        cache_key=key,
                    )
                    if loaded is not None:
                        result = _normalize_index_result_aliases(loaded, alias_index)
                        return result, usage

            result, completion = self._completion_with_structured_output(
                prompt=prompt,
                response_model=SemanticIndexResult,
                system_prompt=(
                    session.stable_system
                    if session is not None
                    else build_semantic_lint_system_prompt()
                ),
                stateless=True,
                telemetry_target=page_title,
                telemetry_operation="Concept Indexing",
                log_tokens=False,
                kv_prefix_hash=kv_prefix_hash,
            )
            result = _normalize_index_result_aliases(result, alias_index)
            latency = time.perf_counter() - started
            usage_obj = getattr(completion, "usage", None)
            if usage_obj is not None:
                usage["prompt_tokens"] = int(getattr(usage_obj, "prompt_tokens", 0) or 0)
                usage["completion_tokens"] = int(
                    getattr(usage_obj, "completion_tokens", 0) or 0,
                )
            operation: OperationType = (
                "Semantic Linting" if result.semantic_corrections else "Concept Indexing"
            )
            self.token_logger.log_turn(
                target_file=page_title,
                operation=operation,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                prompt=prompt,
                response=result.model_dump_json(),
                latency_seconds=latency,
                model=self.model,
                kv_prefix_hash=kv_prefix_hash,
            )
            if routing_enabled and page_path is not None and graph_root is not None:
                key = semantic_cache_key(page_path, "semantic_index")
                cache_put(graph_root, "index", key, result.model_dump())
            agent_debug_log(
                location="daemon_llm_client.py:index_page",
                message="index_page success",
                hypothesis_id="H1,H4",
                data={
                    "page_title": page_title,
                    "completion_tokens": usage["completion_tokens"],
                    "summary_len": len(result.summary),
                    "corrections_count": len(result.semantic_corrections),
                },
            )
            return result, usage
        except Exception as exc:  # noqa: BLE001 - log and re-raise for daemon loop
            agent_debug_log(
                location="daemon_llm_client.py:index_page",
                message="index_page failed",
                hypothesis_id="H1,H2,H3",
                data={
                    "page_title": page_title,
                    "error_head": str(exc)[:400],
                },
            )
            latency = time.perf_counter() - started
            self.token_logger.log_turn(
                target_file=page_title,
                operation="Concept Indexing",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                prompt=prompt,
                response="",
                latency_seconds=latency,
                model=self.model,
                ok=False,
                error=str(exc),
            )
            raise


__all__ = [
    "InstructorLLMClient",
    "LLMClient",
]
