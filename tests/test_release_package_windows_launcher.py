from __future__ import annotations

import struct
import zlib

import pytest
from scripts.release_qualification.windows_launcher import (
    _add_resource_values,
    _build_script_archive,
    _parse_pe,
    _parse_resource_table,
    _read_resource_tree,
    _reconstruct_launcher,
    _resource_directory,
    _resource_section,
    _ResourceBudget,
    _ResourceData,
    _ResourceTable,
    _verify_candidate_bytes,
    verify_windows_console_launcher,
)


def _resource_fixture() -> bytes:
    """Build a tiny independent RT_MANIFEST tree: type 24/name 1/lang 1033."""
    manifest = b"manifest"
    data = bytearray(96)
    # Each table has one ID entry. Offsets are relative to the resource root.
    struct.pack_into("<IIHHHH", data, 0, 0x11223344, 0x55667788, 2, 3, 0, 1)
    struct.pack_into("<II", data, 16, 24, 0x80000018)
    struct.pack_into("<IIHHHH", data, 24, 0, 0, 0, 0, 0, 1)
    struct.pack_into("<II", data, 40, 1, 0x80000030)
    struct.pack_into("<IIHHHH", data, 48, 0, 0, 0, 0, 0, 1)
    struct.pack_into("<II", data, 64, 1033, 72)
    struct.pack_into("<IIII", data, 72, 0x2058, len(manifest), 0, 0)
    data[88:] = manifest
    return bytes(data)


def _synthetic_pe() -> bytes:
    """Create a bounded PE32+ image with an interior .rsrc section."""
    image = bytearray(0xA00)
    image[:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, 0x80)
    image[0x80:0x84] = b"PE\0\0"
    coff = 0x84
    struct.pack_into("<HHIIIHH", image, coff, 0x8664, 3, 0, 0, 0, 240, 0x22)
    optional = coff + 20
    struct.pack_into("<H", image, optional, 0x20B)
    struct.pack_into("<I", image, optional + 32, 0x1000)
    struct.pack_into("<I", image, optional + 36, 0x200)
    struct.pack_into("<I", image, optional + 56, 0x4000)
    struct.pack_into("<I", image, optional + 60, 0x400)
    struct.pack_into("<I", image, optional + 64, 0)
    struct.pack_into("<I", image, optional + 108, 16)
    directories = optional + 112
    struct.pack_into("<II", image, directories + 16, 0x2000, 96)

    sections = optional + 240
    _section(image, sections, b".text\0\0\0", 0x10, 0x1000, 0x200, 0x400)
    _section(image, sections + 40, b".rsrc\0\0\0", 96, 0x2000, 0x200, 0x600)
    _section(image, sections + 80, b".reloc\0\0", 0x10, 0x3000, 0x200, 0x800)
    image[0x400:0x410] = b"text-section-001"
    image[0x600:0x660] = _resource_fixture()
    image[0x800:0x810] = b"reloc-section-01"
    return bytes(image)


def _duplicate_resource_fixture() -> bytes:
    data = bytearray(32)
    struct.pack_into("<IIHHHH", data, 0, 0, 0, 0, 0, 0, 2)
    struct.pack_into("<II", data, 16, 24, 0x80000020)
    struct.pack_into("<II", data, 24, 24, 0x80000020)
    return bytes(data)


def _empty_resource_fanout_fixture() -> bytes:
    """Build synthetic directory tables whose bounded depth still fans out widely."""
    root_children = 16
    child_entries = 64
    root_size = 16 + root_children * 8
    child_size = 16 + child_entries * 8
    child_start = root_size
    leaf_start = child_start + root_children * child_size
    leaf_table_count = root_children * child_entries
    data = bytearray(leaf_start + leaf_table_count * 16)

    struct.pack_into("<IIHHHH", data, 0, 0, 0, 0, 0, 0, root_children)
    for child_index in range(root_children):
        child_offset = child_start + child_index * child_size
        struct.pack_into(
            "<II",
            data,
            16 + child_index * 8,
            child_index + 1,
            0x80000000 | child_offset,
        )
        struct.pack_into("<IIHHHH", data, child_offset, 0, 0, 0, 0, 0, child_entries)
        for entry_index in range(child_entries):
            leaf_offset = leaf_start + (child_index * child_entries + entry_index) * 16
            entry_offset = child_offset + 16 + entry_index * 8
            struct.pack_into("<II", data, entry_offset, entry_index + 1, 0x80000000 | leaf_offset)
            struct.pack_into("<IIHHHH", data, leaf_offset, 0, 0, 0, 0, 0, 0)
    return bytes(data)


def _section(
    image: bytearray,
    offset: int,
    name: bytes,
    virtual_size: int,
    virtual_address: int,
    raw_size: int,
    raw_pointer: int,
) -> None:
    image[offset : offset + 8] = name
    struct.pack_into(
        "<IIIIIIHHI",
        image,
        offset + 8,
        virtual_size,
        virtual_address,
        raw_size,
        raw_pointer,
        0,
        0,
        0,
        0,
        0x40000040 if name.startswith(b".rsrc") else 0x60000020,
    )


def test_script_archive_matches_pinned_stored_archive_layout() -> None:
    assert _build_script_archive(b"x\n") == bytes.fromhex(
        "504b03040a0000080000000021001f08ea4602000000020000000b000000"
        "5f5f6d61696e5f5f2e7079780a"
        "504b01023f030a0000080000000021001f08ea4602000000020000000b00"
        "00000000000000000000000000000000"
        "5f5f6d61696e5f5f2e7079"
        "504b05060000000001000100390000002b0000000000"
    )


def test_reconstruction_adds_pedata_and_preserves_existing_sections() -> None:
    template = _synthetic_pe()
    candidate = _reconstruct_launcher(template, "python.exe", b"x" * 1_024)

    assert candidate != template
    assert struct.unpack_from("<H", candidate, 0x86)[0] == 4
    assert candidate[0x400:0xA00] == template[0x400:0xA00]
    assert candidate[0xA00:0xA10] == bytes.fromhex("44332211887766550200030000000200")
    new_section = 0x188 + 3 * 40
    assert candidate[new_section : new_section + 8] == b".pedata\0"
    virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from(
        "<IIII", candidate, new_section + 8
    )
    assert (virtual_address, raw_pointer) == (0x4000, 0xA00)
    assert raw_size == 0x600
    assert 0 < virtual_size <= raw_size
    resource_directory = 0x98 + 112 + 16
    assert struct.unpack_from("<II", candidate, resource_directory) == (
        virtual_address,
        virtual_size,
    )
    assert len(candidate) == 0x1000

    candidate_pe = _parse_pe(candidate)
    tree = _read_resource_tree(candidate, candidate_pe)
    rcdata = tree.entries[10]
    assert isinstance(rcdata, _ResourceTable)
    expected_payloads = {
        "UV_PYTHON_PATH": b"python.exe",
        "UV_SCRIPT_DATA": _build_script_archive(b"x" * 1_024),
        "UV_TRAMPOLINE_KIND": b"\x01",
    }
    for name, expected_payload in expected_payloads.items():
        language = rcdata.entries[name]
        assert isinstance(language, _ResourceTable)
        payload = language.entries[0]
        assert isinstance(payload, _ResourceData)
        assert payload.payload == expected_payload
        assert payload.payload in candidate[candidate_pe.sections[-1].raw_pointer :]


def test_reconstruction_preserves_trailing_overlay_bytes() -> None:
    overlay = b"synthetic-overlay\x00\xff"
    template = _synthetic_pe() + overlay

    candidate = _reconstruct_launcher(template, "python.exe", b"x" * 1_024)

    assert candidate.endswith(overlay)
    assert candidate != template


def test_resource_writer_preserves_all_twelve_header_prefix_bytes() -> None:
    image = _synthetic_pe()
    root = _read_resource_tree(image, _parse_pe(image))
    assert root.header_prefix == bytes.fromhex("443322118877665502000300")
    _add_resource_values(root, "python.exe", b"pass\n")

    serialized = _resource_directory(root, 0x4000)
    assert serialized[:16] == bytes.fromhex("44332211887766550200030000000200")


def test_resource_parser_rejects_duplicate_ids_before_recursing() -> None:
    image = bytearray(_synthetic_pe())
    image[0x600 : 0x600 + 32] = _duplicate_resource_fixture()
    pe = _parse_pe(bytes(image))
    section, root_offset, root_size = _resource_section(pe, bytes(image))

    with pytest.raises(ValueError, match="duplicate keys"):
        _parse_resource_table(
            bytes(image),
            pe,
            section,
            root_offset,
            root_offset,
            min(root_size, 32),
            0,
            0,
            set(),
            [],
            _ResourceBudget(),
        )


def test_resource_parser_bounds_total_empty_table_fanout() -> None:
    image = _empty_resource_fanout_fixture()
    pe = _parse_pe(_synthetic_pe())
    section = pe.sections[1]

    with pytest.raises(ValueError, match="Total resource-table bound"):
        _parse_resource_table(
            image,
            pe,
            section,
            0,
            0,
            len(image),
            0,
            0,
            set(),
            [],
            _ResourceBudget(),
        )


def test_resource_parser_bounds_aggregate_entry_count(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.release_qualification.windows_launcher as launcher

    image = _synthetic_pe()
    monkeypatch.setattr(launcher, "_MAX_TOTAL_RESOURCE_ENTRIES", 1)

    with pytest.raises(ValueError, match="Total resource-entry bound"):
        _read_resource_tree(image, _parse_pe(image))


def test_resource_parser_rejects_table_cycles() -> None:
    image = bytearray(_synthetic_pe())
    struct.pack_into("<I", image, 0x600 + 20, 0x80000000)

    with pytest.raises(ValueError, match="depth or cycle"):
        _read_resource_tree(bytes(image), _parse_pe(bytes(image)))


def test_resource_parser_rejects_descriptor_aliasing_a_table() -> None:
    image = bytearray(_synthetic_pe())
    struct.pack_into("<I", image, 0x600 + 64 + 4, 56)

    with pytest.raises(ValueError, match="overlaps or aliases"):
        _read_resource_tree(bytes(image), _parse_pe(bytes(image)))


def test_resource_parser_rejects_payload_aliasing_a_table() -> None:
    image = bytearray(_synthetic_pe())
    struct.pack_into("<II", image, 0x600 + 72, 0x2000 + 48, 4)

    with pytest.raises(ValueError, match="resource payload overlaps or aliases"):
        _read_resource_tree(bytes(image), _parse_pe(bytes(image)))


def test_resource_parser_rejects_per_table_entry_overflow() -> None:
    image = bytearray(_synthetic_pe())
    struct.pack_into("<H", image, 0x600 + 14, 513)

    with pytest.raises(ValueError, match="Resource table exceeds the entry bound"):
        _read_resource_tree(bytes(image), _parse_pe(bytes(image)))


def test_resource_parser_rejects_invalid_utf16_resource_names() -> None:
    image = bytearray(_synthetic_pe())
    resource = bytearray(96)
    struct.pack_into("<IIHHHH", resource, 0, 0, 0, 0, 0, 1, 0)
    struct.pack_into("<II", resource, 16, 0x80000020, 0x80000030)
    struct.pack_into("<H", resource, 32, 1)
    resource[34:36] = b"\x00\xd8"
    struct.pack_into("<IIHHHH", resource, 48, 0, 0, 0, 0, 0, 0)
    image[0x600 : 0x600 + len(resource)] = resource

    with pytest.raises(ValueError, match="valid UTF-16LE"):
        _read_resource_tree(bytes(image), _parse_pe(bytes(image)))


def test_resource_parser_rejects_missing_resource_directory() -> None:
    image = bytearray(_synthetic_pe())
    struct.pack_into("<II", image, 0x98 + 112 + 2 * 8, 0, 0)

    with pytest.raises(ValueError, match="no bounded resource directory"):
        _read_resource_tree(bytes(image), _parse_pe(bytes(image)))


def test_reconstruction_rejects_certificate_bearing_templates() -> None:
    template = bytearray(_synthetic_pe())
    struct.pack_into("<II", template, 0x98 + 112 + 4 * 8, 0xB000, 8)

    with pytest.raises(ValueError, match="Certificate-bearing PE templates"):
        _reconstruct_launcher(bytes(template), "python.exe", b"x")


def test_reconstruction_rejects_resource_section_at_end_of_image() -> None:
    template = bytearray(_synthetic_pe())
    section_table = 0x188
    rsrc_header = section_table + 40
    reloc_header = section_table + 80
    original_resource = bytes(template[0x600:0x800])
    original_reloc = bytes(template[0x800:0xA00])
    template[0x600:0x800] = original_reloc
    template[0x800:0xA00] = original_resource
    struct.pack_into("<I", template, rsrc_header + 20, 0x800)
    struct.pack_into("<I", template, reloc_header + 20, 0x600)

    with pytest.raises(ValueError, match="last-section resource replacement"):
        _reconstruct_launcher(bytes(template), "python.exe", b"x")


def test_reconstruction_enforces_interpreter_and_script_bounds() -> None:
    with pytest.raises(ValueError, match="interpreter is empty, contains NUL, or exceeds"):
        _reconstruct_launcher(_synthetic_pe(), "x" * (4_096 + 1), b"x")
    with pytest.raises(ValueError, match="script is empty or exceeds"):
        _build_script_archive(b"x" * (4 * 1024 * 1024 + 1))


def test_resource_parser_rejects_payload_rva_outside_resource_section() -> None:
    image = bytearray(_synthetic_pe())
    struct.pack_into("<I", image, 0x600 + 72, 0x4000)

    with pytest.raises(ValueError, match="does not map within its unique resource section"):
        _read_resource_tree(bytes(image), _parse_pe(bytes(image)))


def test_verifier_rejects_any_unmodeled_candidate_byte() -> None:
    expected = _reconstruct_launcher(_synthetic_pe(), "python.exe", b"x" * 1_024)
    altered = bytearray(expected)
    altered[0x410] ^= 1

    with pytest.raises(ValueError, match="exactly match"):
        _verify_candidate_bytes(bytes(altered), expected)


@pytest.mark.parametrize("candidate_suffix", [b"", b"\x00"])
def test_verifier_rejects_truncated_or_appended_candidate(candidate_suffix: bytes) -> None:
    expected = _reconstruct_launcher(_synthetic_pe(), "python.exe", b"x" * 1_024)
    candidate = expected[:-1] if candidate_suffix == b"" else expected + candidate_suffix

    with pytest.raises(ValueError, match="exactly match"):
        _verify_candidate_bytes(candidate, expected)


def test_public_verifier_rejects_unpinned_synthetic_template() -> None:
    template = _synthetic_pe()
    script = b"x" * 1_024
    candidate = _reconstruct_launcher(template, "python.exe", script)

    with pytest.raises(ValueError, match="pinned x64 console launcher source"):
        verify_windows_console_launcher(
            candidate,
            template,
            "python.exe",
            script,
        )


def test_zip_crc_is_for_supplied_script_bytes() -> None:
    archive = _build_script_archive(b"sample payload")
    crc = zlib.crc32(b"sample payload") & 0xFFFFFFFF
    assert struct.unpack_from("<I", archive, 14)[0] == crc


def test_added_resources_use_pinned_default_codepage() -> None:
    image = _synthetic_pe()
    root = _read_resource_tree(image, _parse_pe(image))
    _add_resource_values(root, "python.exe", b"pass\n")

    rcdata = root.entries[10]
    assert isinstance(rcdata, _ResourceTable)
    for name in ("UV_PYTHON_PATH", "UV_SCRIPT_DATA", "UV_TRAMPOLINE_KIND"):
        language = rcdata.entries[name]
        assert isinstance(language, _ResourceTable)
        payload = language.entries[0]
        assert isinstance(payload, _ResourceData)
        assert payload.codepage == 1200


@pytest.mark.parametrize(
    ("candidate", "template", "interpreter", "script", "message"),
    [
        (None, b"template", "python.exe", b"script", "Candidate PE is not bytes"),
        (b"candidate", None, "python.exe", b"script", "Template PE must be bytes"),
        (b"candidate", b"template", None, "script", "interpreter path must be text"),
        (b"candidate", b"template", "python.exe", None, "script payload must be bytes"),
    ],
)
def test_public_verifier_rejects_non_bytes_or_non_text_inputs(
    candidate: object,
    template: object,
    interpreter: object,
    script: object,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        verify_windows_console_launcher(candidate, template, interpreter, script)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changed_field",
    ["interpreter", "script"],
)
def test_synthetic_candidate_rejects_changed_expected_content(
    changed_field: str,
) -> None:
    template = _synthetic_pe()
    original_script = b"original script " + b"x" * 1_024
    interpreter = "other-python.exe" if changed_field == "interpreter" else "python.exe"
    expected_script = (
        original_script
        if changed_field == "interpreter"
        else b"changed script " + b"x" * 1_024
    )
    candidate = _reconstruct_launcher(template, "python.exe", original_script)
    expected = _reconstruct_launcher(template, interpreter, expected_script)

    with pytest.raises(ValueError, match="exactly match"):
        _verify_candidate_bytes(candidate, expected)
