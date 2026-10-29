from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from src.semantic.external_chunks import (
    ExternalChunkingError,
    SemanticChunk,
    build_block_chunks,
)
from src.semantic.external_config import ExternalSemanticSettings
from src.semantic.external_extract import SourceSnapshot, extract_page_blocks


class WordTokenizer:
    def count_tokens(self, text: str, *, add_special: bool = True) -> int:
        return len(text.split()) + (2 if add_special else 0)


class CharacterTokenizer:
    def count_tokens(self, text: str, *, add_special: bool = True) -> int:
        return len(text) + (2 if add_special else 0)


class FailingTokenizer:
    def count_tokens(self, text: str, *, add_special: bool = True) -> int:
        raise RuntimeError("tokenizer unavailable")


class RecordingWordTokenizer(WordTokenizer):
    def __init__(self) -> None:
        self.input_byte_lengths: list[int] = []

    def count_tokens(self, text: str, *, add_special: bool = True) -> int:
        self.input_byte_lengths.append(len(text.encode("utf-8")))
        return super().count_tokens(text, add_special=add_special)


def _settings(
    *,
    target_tokens: int = 320,
    max_input_tokens: int = 480,
    context_tokens: int = 64,
    overlap_tokens: int = 32,
    max_input_bytes: int = 32768,
) -> ExternalSemanticSettings:
    return ExternalSemanticSettings(
        target_tokens=target_tokens,
        max_input_tokens=max_input_tokens,
        context_tokens=context_tokens,
        overlap_tokens=overlap_tokens,
        max_input_bytes=max_input_bytes,
    )


def _assert_exact_coverage(chunks: tuple[SemanticChunk, ...], content: str) -> None:
    assert chunks
    assert chunks[0].start_char == 0
    assert chunks[-1].end_char == len(content)
    for chunk in chunks:
        assert chunk.text == content[chunk.start_char : chunk.end_char]
    assert "".join(chunk.text for chunk in chunks) == content


def test_short_block_stays_whole_and_keeps_source_only_context() -> None:
    content = "  A short fact.\r\n"
    tokenizer = WordTokenizer()

    chunks = build_block_chunks(
        content,
        page_title="Quarterly review",
        ancestor_texts=("Parent fact", "Grandparent fact", "ignored farther ancestor"),
        tokenizer=tokenizer,
        settings=_settings(),
    )

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.text == content
    assert chunk.embedding_text == f"{chunk.context_text}\n{content}"
    assert chunk.context_text == "Quarterly review\nParent fact\nGrandparent fact"
    assert chunk.token_count == tokenizer.count_tokens(chunk.embedding_text)
    assert chunk.split_kind == "whole"
    assert chunk.start_char == 0 and chunk.end_char == len(content)


def test_whole_block_is_retained_when_it_fits_maximum_even_above_target() -> None:
    content = (
        "one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
        "fifteen sixteen seventeen eighteen"
    )
    chunks = build_block_chunks(
        content,
        page_title="",
        ancestor_texts=(),
        tokenizer=WordTokenizer(),
        settings=_settings(
            target_tokens=16, max_input_tokens=32, context_tokens=0, overlap_tokens=0
        ),
    )

    assert len(chunks) == 1
    assert chunks[0].text == content
    assert chunks[0].token_count == 20
    assert chunks[0].split_kind == "whole"


def test_unicode_and_whitespace_content_keep_exact_source_slices() -> None:
    content = "😀 café. " * 24

    chunks = build_block_chunks(
        content,
        page_title="",
        ancestor_texts=(),
        tokenizer=WordTokenizer(),
        settings=_settings(
            target_tokens=16,
            max_input_tokens=32,
            context_tokens=0,
            overlap_tokens=0,
        ),
    )

    _assert_exact_coverage(chunks, content)
    assert any("😀" in chunk.text for chunk in chunks)

    whitespace = " \t\r\n "
    whitespace_chunks = build_block_chunks(
        whitespace,
        page_title="",
        ancestor_texts=(),
        tokenizer=WordTokenizer(),
        settings=_settings(context_tokens=0, overlap_tokens=0),
    )
    assert len(whitespace_chunks) == 1
    assert whitespace_chunks[0].text == whitespace
    assert (
        whitespace_chunks[0].text
        == whitespace[whitespace_chunks[0].start_char : whitespace_chunks[0].end_char]
    )


def test_long_prose_splits_near_target_at_sentence_groups_and_preserves_offsets() -> None:
    sentences = [f"word{index} next{index}." for index in range(20)]
    content = " ".join(sentences)
    tokenizer = WordTokenizer()

    chunks = build_block_chunks(
        content,
        page_title="",
        ancestor_texts=(),
        tokenizer=tokenizer,
        settings=_settings(
            target_tokens=16,
            max_input_tokens=32,
            context_tokens=0,
            overlap_tokens=0,
        ),
    )

    _assert_exact_coverage(chunks, content)
    assert chunks[0].text == " ".join(sentences[:7]) + " "
    assert all(chunk.token_count <= 32 for chunk in chunks)
    assert all(chunk.split_kind == "sentence_group" for chunk in chunks)


def test_italian_abbreviations_and_decimals_are_not_sentence_boundaries() -> None:
    content = "Dott. Rossi legge 3.14. " + " ".join(f"Parola{index}." for index in range(36))

    chunks = build_block_chunks(
        content,
        page_title="",
        ancestor_texts=(),
        tokenizer=WordTokenizer(),
        settings=_settings(
            target_tokens=16,
            max_input_tokens=32,
            context_tokens=0,
            overlap_tokens=0,
        ),
    )

    _assert_exact_coverage(chunks, content)
    assert chunks[0].text.startswith("Dott. Rossi legge 3.14.")
    assert not chunks[1].text.startswith("Rossi")


def test_code_uses_line_boundaries_and_keeps_fences_and_whitespace() -> None:
    lines = [f"value_{index}" for index in range(40)]
    content = "```python\n" + "\n".join(lines) + "\n```\n"

    chunks = build_block_chunks(
        content,
        page_title="",
        ancestor_texts=(),
        tokenizer=WordTokenizer(),
        settings=_settings(
            target_tokens=16,
            max_input_tokens=32,
            context_tokens=0,
            overlap_tokens=0,
        ),
    )

    _assert_exact_coverage(chunks, content)
    assert all(chunk.start_char == 0 or content[chunk.start_char - 1] == "\n" for chunk in chunks)
    assert all(chunk.split_kind == "code_line_group" for chunk in chunks)


def test_oversized_single_word_uses_explicit_character_fallback() -> None:
    content = "x" * 101

    chunks = build_block_chunks(
        content,
        page_title="",
        ancestor_texts=(),
        tokenizer=CharacterTokenizer(),
        settings=_settings(
            target_tokens=16,
            max_input_tokens=32,
            context_tokens=0,
            overlap_tokens=0,
            max_input_bytes=256,
        ),
    )

    _assert_exact_coverage(chunks, content)
    assert len(chunks) > 1
    assert all(chunk.split_kind == "character_fallback" for chunk in chunks)
    assert all(chunk.token_count <= 32 for chunk in chunks)


def test_final_count_includes_bounded_context_and_special_tokens() -> None:
    content = "source fact stays intact"
    tokenizer = WordTokenizer()
    chunks = build_block_chunks(
        content,
        page_title="One two three four five",
        ancestor_texts=("six seven eight nine ten", "eleven twelve"),
        tokenizer=tokenizer,
        settings=_settings(
            target_tokens=16,
            max_input_tokens=32,
            context_tokens=5,
            overlap_tokens=0,
        ),
    )

    _assert_exact_coverage(chunks, content)
    assert tokenizer.count_tokens(chunks[0].context_text, add_special=False) <= 5
    assert chunks[0].token_count == tokenizer.count_tokens(chunks[0].embedding_text)
    assert chunks[0].token_count <= 32
    assert chunks[0].context_text == "One two three four five"
    assert "six seven eight nine ten" not in chunks[0].context_text


def test_overlap_is_bounded_and_still_advances_source_offsets() -> None:
    content = " ".join(f"word{index}." for index in range(70))
    tokenizer = WordTokenizer()

    chunks = build_block_chunks(
        content,
        page_title="",
        ancestor_texts=(),
        tokenizer=tokenizer,
        settings=_settings(
            target_tokens=16,
            max_input_tokens=32,
            context_tokens=0,
            overlap_tokens=2,
        ),
    )

    assert len(chunks) > 2
    assert chunks[0].start_char == 0
    for previous, current in zip(chunks, chunks[1:], strict=False):
        assert current.end_char > previous.end_char
        overlap = content[current.start_char : previous.end_char]
        assert overlap
        assert tokenizer.count_tokens(overlap, add_special=False) <= 2
        assert current.text == content[current.start_char : current.end_char]


def test_tokenizer_candidates_never_exceed_configured_byte_window() -> None:
    content = " ".join(f"item{index}" for index in range(500))
    tokenizer = RecordingWordTokenizer()

    chunks = build_block_chunks(
        content,
        page_title="",
        ancestor_texts=(),
        tokenizer=tokenizer,
        settings=_settings(
            target_tokens=16,
            max_input_tokens=32,
            context_tokens=0,
            overlap_tokens=0,
            max_input_bytes=256,
        ),
    )

    _assert_exact_coverage(chunks, content)
    assert tokenizer.input_byte_lengths
    assert max(tokenizer.input_byte_lengths) <= 256
    assert all(chunk.token_count <= 32 for chunk in chunks)


@pytest.mark.parametrize("overlap_tokens", [0, 32])
def test_overlap_cannot_block_progress_when_byte_window_ends_at_word_boundary(
    overlap_tokens: int,
) -> None:
    content = "x " + "a" * 32766 + "😀 tail"
    tokenizer = WordTokenizer()
    settings = _settings(overlap_tokens=overlap_tokens)

    chunks = build_block_chunks(
        content,
        page_title="",
        ancestor_texts=(),
        tokenizer=tokenizer,
        settings=settings,
    )

    assert chunks[0].start_char == 0
    assert chunks[-1].end_char == len(content)
    for previous, current in zip(chunks, chunks[1:], strict=False):
        assert current.end_char > previous.end_char
        assert current.start_char <= previous.end_char
    for chunk in chunks:
        assert chunk.text == content[chunk.start_char : chunk.end_char]
        assert len(chunk.embedding_text.encode("utf-8")) <= settings.max_input_bytes
        assert chunk.token_count == tokenizer.count_tokens(chunk.embedding_text)
        assert chunk.token_count <= settings.max_input_tokens


def test_tokenizer_failure_is_explicit_and_does_not_guess_from_bytes() -> None:
    with pytest.raises(ExternalChunkingError, match="tokenizer_count_failed"):
        build_block_chunks(
            "a source fact",
            page_title="Page",
            ancestor_texts=(),
            tokenizer=FailingTokenizer(),
            settings=_settings(),
        )


def test_extract_page_blocks_preserves_identity_properties_and_ancestor_chain(
    tmp_path: Path,
) -> None:
    source_text = (
        "- Parent heading\n"
        "  id:: 11111111-1111-4111-8111-111111111111\n"
        "  topic:: project\n"
        "  - Child fact\n"
        "    id:: 22222222-2222-4222-8222-222222222222\n"
        "    status:: ready\n"
        "    - Leaf observation\n"
        "      id:: 33333333-3333-4333-8333-333333333333\n"
    )
    source = SourceSnapshot(
        relative_path="pages/Parent.md",
        title="Parent",
        source_hash=hashlib.sha256(source_text.encode()).hexdigest(),
        byte_count=len(source_text.encode()),
        mtime_ns=1,
        text=source_text,
    )

    page = extract_page_blocks(
        source,
        tmp_path,
        settings=_settings(),
        tokenizer=WordTokenizer(),
    )

    parent, child, leaf = page.blocks
    assert parent.citation_id == "11111111-1111-4111-8111-111111111111"
    assert parent.properties == {"id": parent.citation_id, "topic": "project"}
    assert parent.parent_citation_id is None
    assert parent.ancestor_citation_ids == ()
    assert child.citation_id == "22222222-2222-4222-8222-222222222222"
    assert child.properties == {"id": child.citation_id, "status": "ready"}
    assert child.parent_citation_id == parent.citation_id
    assert child.ancestor_citation_ids == (parent.citation_id,)
    assert child.block_content_hash == hashlib.sha256(child.content.encode()).hexdigest()
    assert isinstance(child.chunks, tuple)
    assert child.chunks[0].context_text == "Parent\nParent heading"
    assert leaf.citation_id == "33333333-3333-4333-8333-333333333333"
    assert leaf.parent_citation_id == child.citation_id
    assert leaf.ancestor_citation_ids == (child.citation_id, parent.citation_id)
    assert leaf.chunks[0].context_text == "Parent\nChild fact\nParent heading"


def test_extraction_tokenizer_errors_are_not_converted_to_partial_pages(
    tmp_path: Path,
) -> None:
    source_text = "- a fact\n"
    source = SourceSnapshot(
        relative_path="pages/Failure.md",
        title="Failure",
        source_hash=hashlib.sha256(source_text.encode()).hexdigest(),
        byte_count=len(source_text.encode()),
        mtime_ns=1,
        text=source_text,
    )

    with pytest.raises(ExternalChunkingError, match="tokenizer_count_failed"):
        extract_page_blocks(
            source,
            tmp_path,
            settings=_settings(),
            tokenizer=FailingTokenizer(),
        )


def test_sibling_blocks_are_chunked_independently_without_cross_block_overlap(
    tmp_path: Path,
) -> None:
    first_content = " ".join(f"alpha{index}." for index in range(70))
    second_content = " ".join(f"beta{index}." for index in range(70))
    source_text = (
        "- Parent\n"
        "  id:: 11111111-1111-4111-8111-111111111111\n"
        f"  - {first_content}\n"
        "    id:: 22222222-2222-4222-8222-222222222222\n"
        f"  - {second_content}\n"
        "    id:: 33333333-3333-4333-8333-333333333333\n"
    )
    source = SourceSnapshot(
        relative_path="pages/Siblings.md",
        title="Siblings",
        source_hash=hashlib.sha256(source_text.encode()).hexdigest(),
        byte_count=len(source_text.encode()),
        mtime_ns=1,
        text=source_text,
    )

    page = extract_page_blocks(
        source,
        tmp_path,
        settings=_settings(
            target_tokens=16,
            max_input_tokens=32,
            context_tokens=0,
            overlap_tokens=2,
            max_input_bytes=256,
        ),
        tokenizer=WordTokenizer(),
    )

    assert len(page.blocks) == 3
    first = page.blocks[1]
    second = page.blocks[2]
    assert first.citation_id == "22222222-2222-4222-8222-222222222222"
    assert second.citation_id == "33333333-3333-4333-8333-333333333333"
    assert first.chunks[0].start_char == 0
    assert second.chunks[0].start_char == 0
    assert all("beta" not in chunk.text for chunk in first.chunks)
    assert all("alpha" not in chunk.text for chunk in second.chunks)
    for block in (first, second):
        assert block.chunks[-1].end_char == len(block.content)
        for previous, current in zip(block.chunks, block.chunks[1:], strict=False):
            assert current.start_char <= previous.end_char
            assert current.end_char > previous.end_char
            assert current.text == block.content[current.start_char : current.end_char]
