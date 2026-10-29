"""Token-bounded semantic chunks that retain their source block spans."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from .external_config import ExternalSemanticSettings


class TokenCounter(Protocol):
    """Count tokens with the same special-token policy as the embedding service."""

    def count_tokens(self, text: str, *, add_special: bool = True) -> int:
        """Return the token count for text, optionally including model special tokens."""


@dataclass(frozen=True, slots=True)
class SemanticChunk:
    """One exact source slice with its bounded embedding input and token count."""

    text: str
    embedding_text: str
    start_char: int
    end_char: int
    token_count: int
    context_text: str
    split_kind: str


class ExternalChunkingError(ValueError):
    """Content-free failure while preparing token-bounded semantic input."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class _Boundary:
    """Preferred source boundary and the strategy that produced it."""

    position: int
    split_kind: str


_SENTENCE_END = re.compile(r"[.!?…]+[\"'’»)\]]*(?=\s|$)")
_WHITESPACE = re.compile(r"\s+")
_PARAGRAPH_END = re.compile(r"(?:\r?\n)[\t ]*(?:\r?\n)+")
_LINE_END = re.compile(r"\r\n|\n|\r")
_ABBREVIATIONS: frozenset[str] = frozenset(
    {
        "avv",
        "cap",
        "dott",
        "dott.ssa",
        "dr",
        "es",
        "etc",
        "ecc",
        "fig",
        "ing",
        "mr",
        "mrs",
        "n",
        "on",
        "pag",
        "p.es",
        "prof",
        "prof.ssa",
        "sig",
        "sigg",
        "vs",
    }
)


def build_block_chunks(
    content: str,
    *,
    page_title: str,
    ancestor_texts: tuple[str, ...],
    tokenizer: TokenCounter,
    settings: ExternalSemanticSettings,
) -> tuple[SemanticChunk, ...]:
    """Chunk one Logseq block without dropping or merging its source text.

    ``ancestor_texts`` is ordered nearest ancestor first. Context is copied only
    into embedding inputs; each chunk's offsets continue to refer to ``content``.
    """
    if not content:
        return ()

    context_text = _build_context(
        page_title,
        ancestor_texts,
        tokenizer=tokenizer,
        settings=settings,
    )
    if _input_fits_byte_limit(context_text, content, settings.max_input_bytes):
        full_input = _embedding_text(context_text, content)
        full_count = _count_tokens(
            tokenizer,
            full_input,
            add_special=True,
            max_input_bytes=settings.max_input_bytes,
        )
        if full_count <= settings.max_input_tokens:
            return (
                SemanticChunk(
                    text=content,
                    embedding_text=full_input,
                    start_char=0,
                    end_char=len(content),
                    token_count=full_count,
                    context_text=context_text,
                    split_kind="whole",
                ),
            )

    context_prefix = f"{context_text}\n" if context_text else ""
    source_byte_limit = settings.max_input_bytes - len(context_prefix.encode("utf-8"))
    if source_byte_limit <= 0:
        raise ExternalChunkingError("context_leaves_no_input_bytes")

    chunks: list[SemanticChunk] = []
    start = 0
    previous_end: int | None = None
    while start < len(content):
        window_end = _byte_limited_end(content, start, source_byte_limit)
        if window_end <= start:
            raise ExternalChunkingError("input_byte_limit_too_small_for_character")
        if previous_end is not None and start < previous_end and window_end <= previous_end:
            # The overlap consumes this byte window without fitting any new
            # source character. Retry exactly at the prior end with no overlap.
            start = previous_end
            continue
        boundaries = _preferred_boundaries(content, start, window_end)
        fallback_boundaries = _fallback_boundaries(content, start, window_end)
        count_cache: dict[int, int] = {}

        def count_to(
            end: int,
            *,
            start_offset: int = start,
            cache: dict[int, int] = count_cache,
        ) -> int:
            if end not in cache:
                candidate = _embedding_text(context_text, content[start_offset:end])
                cache[end] = _count_tokens(
                    tokenizer,
                    candidate,
                    add_special=True,
                    max_input_bytes=settings.max_input_bytes,
                )
            return cache[end]

        eligible_boundaries = [
            boundary
            for boundary in boundaries
            if previous_end is None or boundary.position > previous_end
        ]
        chosen = _select_near_target(
            eligible_boundaries,
            count_to,
            target_tokens=settings.target_tokens,
            max_tokens=settings.max_input_tokens,
        )
        if chosen is None:
            eligible_fallbacks = [
                boundary
                for boundary in fallback_boundaries
                if previous_end is None or boundary.position > previous_end
            ]
            chosen = _select_near_target(
                eligible_fallbacks,
                count_to,
                target_tokens=settings.target_tokens,
                max_tokens=settings.max_input_tokens,
            )

        if chosen is None:
            end = _character_fallback_end(
                start,
                window_end,
                count_to,
                target_tokens=settings.target_tokens,
                max_tokens=settings.max_input_tokens,
                minimum_end=(previous_end + 1) if previous_end is not None else start + 1,
            )
            split_kind = "character_fallback"
            token_count = count_to(end)
        else:
            boundary, token_count = chosen
            end = boundary.position
            split_kind = boundary.split_kind

        if end <= start or (previous_end is not None and end <= previous_end):
            raise ExternalChunkingError("chunking_failed_to_advance")
        if token_count > settings.max_input_tokens:
            raise ExternalChunkingError("chunk_exceeds_token_limit")

        chunk_text = content[start:end]
        embedding_text = _embedding_text(context_text, chunk_text)
        chunks.append(
            SemanticChunk(
                text=chunk_text,
                embedding_text=embedding_text,
                start_char=start,
                end_char=end,
                token_count=token_count,
                context_text=context_text,
                split_kind=split_kind,
            )
        )

        previous_end = end
        if end == len(content):
            break
        start = _overlap_start(
            content,
            current_start=start,
            end=end,
            tokenizer=tokenizer,
            max_overlap_tokens=settings.overlap_tokens,
            max_input_bytes=settings.max_input_bytes,
        )

    return tuple(chunks)


def _build_context(
    page_title: str,
    ancestor_texts: tuple[str, ...],
    *,
    tokenizer: TokenCounter,
    settings: ExternalSemanticSettings,
) -> str:
    """Fit source-only title and nearest-ancestor text within both context bounds."""
    context_byte_limit = max(0, settings.max_input_bytes - 5)
    accepted: list[str] = []
    candidates = (page_title, *ancestor_texts[:2])
    for raw_piece in candidates:
        piece = raw_piece.strip()
        if not piece:
            continue
        prefix = "\n".join(accepted)
        separator = "\n" if prefix else ""
        available_bytes = context_byte_limit - len((prefix + separator).encode("utf-8"))
        if available_bytes <= 0:
            break
        window_end = _byte_limited_end(piece, 0, available_bytes)
        if window_end <= 0:
            continue
        ends = _fallback_boundaries(piece, 0, window_end)
        count_cache: dict[int, int] = {}

        def count_context_to(
            end: int,
            *,
            cache: dict[int, int] = count_cache,
            accepted_prefix: str = prefix,
            prefix_separator: str = separator,
            source_piece: str = piece,
        ) -> int:
            if end not in cache:
                candidate = f"{accepted_prefix}{prefix_separator}{source_piece[:end]}"
                cache[end] = _count_tokens(
                    tokenizer,
                    candidate,
                    add_special=False,
                    max_input_bytes=settings.max_input_bytes,
                )
            return cache[end]

        selected = _select_near_target(
            ends,
            count_context_to,
            target_tokens=settings.context_tokens,
            max_tokens=settings.context_tokens,
        )
        if selected is None:
            try:
                selected_end = _character_fallback_end(
                    0,
                    window_end,
                    count_context_to,
                    target_tokens=settings.context_tokens,
                    max_tokens=settings.context_tokens,
                    minimum_end=1,
                )
            except ExternalChunkingError as exc:
                if exc.code != "chunk_cannot_fit_max_tokens":
                    raise
                continue
        else:
            selected_end = selected[0].position
        if selected_end <= 0:
            continue
        accepted.append(piece[:selected_end])
        if selected_end < len(piece):
            break
    return "\n".join(accepted)


def _preferred_boundaries(content: str, start: int, end: int) -> list[_Boundary]:
    """Return sentence/paragraph boundaries, or code line boundaries."""
    source = content[start:end]
    choices: dict[int, str] = {}
    if "```" in content:
        for match in _LINE_END.finditer(source):
            choices[start + match.end()] = "code_line_group"
    else:
        for match in _SENTENCE_END.finditer(source):
            punctuation = match.end() - 1
            while punctuation >= match.start() and source[punctuation] in "\"'’»)]":
                punctuation -= 1
            if punctuation < match.start():
                continue
            if source[punctuation] == "." and _is_abbreviation_or_decimal(source, punctuation):
                continue
            boundary_end = match.end()
            while boundary_end < len(source) and source[boundary_end].isspace():
                boundary_end += 1
            choices[start + boundary_end] = "sentence_group"
        for match in _PARAGRAPH_END.finditer(source):
            choices.setdefault(start + match.end(), "paragraph_group")
    return [_Boundary(position, choices[position]) for position in sorted(choices)]


def _is_abbreviation_or_decimal(text: str, period_index: int) -> bool:
    previous = text[period_index - 1] if period_index > 0 else ""
    following = text[period_index + 1] if period_index + 1 < len(text) else ""
    if previous.isdigit() and following.isdigit():
        return True
    if period_index > 0:
        token_match = re.search(r"([^\s]+)\.$", text[: period_index + 1])
        if token_match is not None:
            token = token_match.group(1).rstrip(".").casefold()
            if token in _ABBREVIATIONS:
                return True
            if len(token) == 1 and token.isalpha():
                return True
    return False


def _fallback_boundaries(content: str, start: int, end: int) -> list[_Boundary]:
    """Return bounded whitespace cuts plus the current byte-window end."""
    boundaries = [
        _Boundary(match.end(), "whitespace_fallback")
        for match in _WHITESPACE.finditer(content, start, end)
    ]
    if not boundaries:
        return []
    if boundaries[-1].position != end:
        boundaries.append(_Boundary(end, "whitespace_fallback"))
    return boundaries


def _select_near_target(
    boundaries: list[_Boundary],
    count_at: Callable[[int], int],
    *,
    target_tokens: int,
    max_tokens: int,
) -> tuple[_Boundary, int] | None:
    """Choose a nearby preferred boundary using bounded token-count searches."""
    if not boundaries:
        return None
    low = 0
    high = len(boundaries) - 1
    under_target: tuple[_Boundary, int] | None = None
    over_target: tuple[_Boundary, int] | None = None
    any_fit: tuple[_Boundary, int] | None = None
    while low <= high:
        middle = (low + high) // 2
        boundary = boundaries[middle]
        count = count_at(boundary.position)
        if count <= max_tokens:
            any_fit = (boundary, count)
            if count <= target_tokens:
                under_target = (boundary, count)
                low = middle + 1
            else:
                over_target = (boundary, count)
                high = middle - 1
        else:
            high = middle - 1

    if under_target is None:
        return over_target or any_fit
    if over_target is None:
        return under_target
    if over_target[1] - target_tokens < target_tokens - under_target[1]:
        return over_target
    return under_target


def _character_fallback_end(
    start: int,
    end: int,
    count_at: Callable[[int], int],
    *,
    target_tokens: int,
    max_tokens: int,
    minimum_end: int,
) -> int:
    """Binary-search a Unicode codepoint boundary when words cannot fit."""
    low = max(start + 1, minimum_end)
    high = end
    if low > high:
        raise ExternalChunkingError("chunking_failed_to_advance")
    under_target: int | None = None
    over_target: int | None = None
    while low <= high:
        middle = (low + high) // 2
        count = count_at(middle)
        if count <= max_tokens:
            if count <= target_tokens:
                under_target = middle
                low = middle + 1
            else:
                over_target = middle
                high = middle - 1
        else:
            high = middle - 1
    if under_target is not None and over_target is not None:
        under_count = count_at(under_target)
        over_count = count_at(over_target)
        if over_count - target_tokens < target_tokens - under_count:
            return over_target
        return under_target
    if under_target is not None:
        return under_target
    if over_target is not None and count_at(over_target) <= max_tokens:
        return over_target
    raise ExternalChunkingError("chunk_cannot_fit_max_tokens")


def _overlap_start(
    content: str,
    *,
    current_start: int,
    end: int,
    tokenizer: TokenCounter,
    max_overlap_tokens: int,
    max_input_bytes: int,
) -> int:
    """Return a verified, word-aligned same-block suffix start for next chunk."""
    if max_overlap_tokens <= 0 or end <= current_start:
        return end
    starts = [
        match.end()
        for match in _WHITESPACE.finditer(content, current_start, end)
        if match.end() < end
    ]
    if not starts:
        return end
    starts.reverse()

    def suffix_count(start: int) -> int:
        return _count_tokens(
            tokenizer,
            content[start:end],
            add_special=False,
            max_input_bytes=max_input_bytes,
        )

    low = 0
    high = len(starts) - 1
    selected: int | None = None
    while low <= high:
        middle = (low + high) // 2
        candidate_start = starts[middle]
        if suffix_count(candidate_start) <= max_overlap_tokens:
            selected = candidate_start
            low = middle + 1
        else:
            high = middle - 1
    if selected is not None:
        return selected
    # A tokenizer can merge pieces non-monotonically. Verify a one-word suffix
    # directly before giving up; any returned overlap has an exact measured cap.
    shortest_start = starts[0]
    if suffix_count(shortest_start) <= max_overlap_tokens:
        return shortest_start
    return end


def _byte_limited_end(text: str, start: int, max_bytes: int) -> int:
    """Find a UTF-8 boundary without materializing an unbounded candidate."""
    if max_bytes <= 0:
        return start
    used_bytes = 0
    for index in range(start, len(text)):
        char_bytes = len(text[index].encode("utf-8"))
        if used_bytes + char_bytes > max_bytes:
            break
        used_bytes += char_bytes
    else:
        return len(text)
    return index


def _embedding_text(context_text: str, source_text: str) -> str:
    return f"{context_text}\n{source_text}" if context_text else source_text


def _input_fits_byte_limit(context_text: str, source_text: str, max_bytes: int) -> bool:
    return len(_embedding_text(context_text, source_text).encode("utf-8")) <= max_bytes


def _count_tokens(
    tokenizer: TokenCounter,
    text: str,
    *,
    add_special: bool,
    max_input_bytes: int,
) -> int:
    if len(text.encode("utf-8")) > max_input_bytes:
        raise ExternalChunkingError("candidate_exceeds_byte_limit")
    try:
        count = tokenizer.count_tokens(text, add_special=add_special)
    except Exception:
        raise ExternalChunkingError("tokenizer_count_failed") from None
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ExternalChunkingError("tokenizer_count_invalid")
    return count


__all__ = [
    "ExternalChunkingError",
    "SemanticChunk",
    "TokenCounter",
    "build_block_chunks",
]
