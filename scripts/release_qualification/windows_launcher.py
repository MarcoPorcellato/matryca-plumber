"""Fail-closed byte verifier for a pinned x64 console launcher template."""

from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass, field
from typing import NoReturn

_TEMPLATE_SHA256 = "0447a4febf43fdd958e4236129d6050b1dad64c124c43355d557542b3229cae8"
_TEMPLATE_SIZE = 45_056
_MAX_IMAGE_BYTES = 16 * 1024 * 1024
_MAX_SCRIPT_BYTES = 4 * 1024 * 1024
_MAX_INTERPRETER_BYTES = 4_096
_MAX_SECTIONS = 32
_MAX_RESOURCE_ENTRIES = 512
_MAX_RESOURCE_TABLES = 512
_MAX_TOTAL_RESOURCE_ENTRIES = 2_048
_RT_RCDATA = 10
_RT_MANIFEST = 24
_CODE_PAGE_ID_EN_US = 1200
_MANIFEST_NAME = 1
_MANIFEST_LANGUAGE = 1033
_RESOURCE_LEAF_LANGUAGE = 0
_PE32_PLUS = 0x20B
_IMAGE_FILE_MACHINE_AMD64 = 0x8664
_IMAGE_SCN_CNT_INITIALIZED_DATA = 0x00000040
_IMAGE_SCN_MEM_READ = 0x40000000


def _fail(message: str) -> NoReturn:
    raise ValueError(message)


def _slice(data: bytes, offset: int, size: int, label: str) -> bytes:
    if offset < 0 or size < 0 or offset > len(data) or size > len(data) - offset:
        _fail(f"{label} lies outside the bounded image.")
    return data[offset : offset + size]


def _u16(data: bytes, offset: int, label: str) -> int:
    return int.from_bytes(_slice(data, offset, 2, label), byteorder="little")


def _u32(data: bytes, offset: int, label: str) -> int:
    return int.from_bytes(_slice(data, offset, 4, label), byteorder="little")


def _align(value: int, alignment: int, label: str) -> int:
    if alignment <= 0 or alignment & (alignment - 1):
        _fail(f"Unsupported {label} alignment.")
    result = (value + alignment - 1) & ~(alignment - 1)
    if result > 0xFFFFFFFF:
        _fail(f"{label} exceeds the PE address range.")
    return result


@dataclass(frozen=True, slots=True)
class _Section:
    header_offset: int
    name: bytes
    virtual_size: int
    virtual_address: int
    raw_size: int
    raw_pointer: int
    characteristics: int

    @property
    def raw_end(self) -> int:
        return self.raw_pointer + self.raw_size

    @property
    def virtual_end(self) -> int:
        return self.virtual_address + self.virtual_size


@dataclass(frozen=True, slots=True)
class _PeImage:
    pe_offset: int
    coff_offset: int
    optional_offset: int
    section_table_offset: int
    directories_offset: int
    first_raw: int
    last_raw_end: int
    section_alignment: int
    file_alignment: int
    size_of_headers: int
    sections: tuple[_Section, ...]
    directories: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class _ResourceData:
    payload: bytes
    codepage: int = 0
    reserved: int = 0


@dataclass(slots=True)
class _ResourceBudget:
    tables: int = 0
    entries: int = 0
    leaves: int = 0


@dataclass(slots=True)
class _ResourceTable:
    header_prefix: bytes = bytes(12)
    entries: dict[int | str, _ResourceTable | _ResourceData] = field(default_factory=dict)


type _ResourceNode = _ResourceTable | _ResourceData


def _parse_pe(image: bytes) -> _PeImage:
    if not 0x200 <= len(image) <= _MAX_IMAGE_BYTES:
        _fail("PE image size is outside the supported bound.")
    if _slice(image, 0, 2, "DOS signature") != b"MZ":
        _fail("PE image has no DOS signature.")
    pe_offset = _u32(image, 0x3C, "PE header offset")
    if pe_offset > 65_536 or _slice(image, pe_offset, 4, "PE signature") != b"PE\0\0":
        _fail("PE signature or header offset is invalid.")
    coff_offset = pe_offset + 4
    machine = _u16(image, coff_offset, "COFF machine")
    section_count = _u16(image, coff_offset + 2, "COFF section count")
    optional_size = _u16(image, coff_offset + 16, "optional-header size")
    if machine != _IMAGE_FILE_MACHINE_AMD64:
        _fail("Only AMD64 PE images are supported.")
    if not 1 <= section_count <= _MAX_SECTIONS or optional_size != 240:
        _fail("PE section count or PE32+ optional-header size is unsupported.")
    optional_offset = coff_offset + 20
    if _u16(image, optional_offset, "optional-header magic") != _PE32_PLUS:
        _fail("Only PE32+ images are supported.")
    section_alignment = _u32(image, optional_offset + 32, "section alignment")
    file_alignment = _u32(image, optional_offset + 36, "file alignment")
    size_of_headers = _u32(image, optional_offset + 60, "SizeOfHeaders")
    directory_count = _u32(image, optional_offset + 108, "data-directory count")
    if directory_count != 16:
        _fail("PE image must declare the complete 16-entry data-directory table.")
    if not 0x200 <= file_alignment <= 0x10000:
        _fail("PE file alignment is outside the supported range.")
    if section_alignment < file_alignment or section_alignment & (section_alignment - 1):
        _fail("PE section alignment is unsupported.")
    directories_offset = optional_offset + 112
    directories = tuple(
        struct.unpack("<II", _slice(image, directories_offset + index * 8, 8, "data directory"))
        for index in range(directory_count)
    )
    section_table_offset = optional_offset + optional_size
    section_table_end = section_table_offset + section_count * 40
    _slice(image, section_table_offset, section_count * 40, "section table")
    if section_table_end > size_of_headers:
        _fail("PE section table exceeds SizeOfHeaders.")

    sections: list[_Section] = []
    names: set[bytes] = set()
    for index in range(section_count):
        offset = section_table_offset + index * 40
        name = _slice(image, offset, 8, "section name")
        virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack(
            "<IIII", _slice(image, offset + 8, 16, "section layout")
        )
        characteristics = _u32(image, offset + 36, "section characteristics")
        if name in names:
            _fail("PE section names must be unique.")
        names.add(name)
        if raw_size == 0 or raw_pointer == 0 or raw_size % file_alignment:
            _fail("PE section raw layout is unsupported.")
        _slice(image, raw_pointer, raw_size, "section raw bytes")
        if raw_pointer < size_of_headers:
            _fail("PE section overlaps its headers.")
        sections.append(
            _Section(
                offset,
                name,
                virtual_size,
                virtual_address,
                raw_size,
                raw_pointer,
                characteristics,
            )
        )

    by_raw = sorted(sections, key=lambda section: section.raw_pointer)
    for previous, current in zip(by_raw, by_raw[1:], strict=False):
        if previous.raw_end > current.raw_pointer:
            _fail("PE raw sections overlap.")
    by_virtual = sorted(sections, key=lambda section: section.virtual_address)
    for previous, current in zip(by_virtual, by_virtual[1:], strict=False):
        if previous.virtual_end > current.virtual_address:
            _fail("PE virtual sections overlap.")
    first_raw = by_raw[0].raw_pointer
    last_raw_end = by_raw[-1].raw_end
    if first_raw < size_of_headers or last_raw_end > len(image):
        _fail("PE raw section range is invalid.")
    return _PeImage(
        pe_offset,
        coff_offset,
        optional_offset,
        section_table_offset,
        directories_offset,
        first_raw,
        last_raw_end,
        section_alignment,
        file_alignment,
        size_of_headers,
        tuple(sections),
        directories,
    )


def _resource_section(pe: _PeImage, image: bytes) -> tuple[_Section, int, int]:
    resource_rva, resource_size = pe.directories[2]
    if resource_rva == 0 or resource_size == 0:
        _fail("PE image has no bounded resource directory.")
    matches = [
        section
        for section in pe.sections
        if section.virtual_address <= resource_rva
        and resource_rva - section.virtual_address < section.virtual_size
    ]
    if len(matches) != 1:
        _fail("Resource directory does not map uniquely to one section.")
    section = matches[0]
    delta = resource_rva - section.virtual_address
    if delta + resource_size > section.raw_size:
        _fail("Resource directory exceeds its section's raw bytes.")
    resource_offset = section.raw_pointer + delta
    _slice(image, resource_offset, resource_size, "resource directory")
    return section, resource_offset, resource_size


def _claim(ranges: list[tuple[int, int]], start: int, size: int, limit: int, label: str) -> None:
    if start < 0 or size <= 0 or start > limit or size > limit - start:
        _fail(f"{label} exceeds the bounded resource directory.")
    end = start + size
    if any(start < other_end and other_start < end for other_start, other_end in ranges):
        _fail(f"{label} overlaps or aliases another resource structure.")
    ranges.append((start, end))


def _parse_resource_name(
    image: bytes, root_offset: int, relative: int, limit: int, ranges: list[tuple[int, int]]
) -> int | str:
    if relative & 0x80000000:
        name_offset = relative & 0x7FFFFFFF
        length = _u16(image, root_offset + name_offset, "resource-name length")
        encoded_size = 2 + length * 2
        _claim(ranges, name_offset, encoded_size, limit, "resource name")
        raw = _slice(image, root_offset + name_offset + 2, length * 2, "resource name")
        try:
            value = raw.decode("utf-16-le", errors="strict")
        except UnicodeDecodeError as error:
            raise ValueError("Resource name is not valid UTF-16LE.") from error
        if not value:
            _fail("Empty resource names are unsupported.")
        return value
    if relative > 0xFFFF:
        _fail("Numeric resource identifier has reserved bits set.")
    return relative


def _resource_sort_key(key: int | str) -> tuple[int, str | int]:
    return (0, key.upper()) if isinstance(key, str) else (1, key)


def _parse_resource_table(
    image: bytes,
    pe: _PeImage,
    resource_section: _Section,
    resource_offset: int,
    root_offset: int,
    root_size: int,
    table_offset: int,
    depth: int,
    ancestors: set[int],
    ranges: list[tuple[int, int]],
    budget: _ResourceBudget,
) -> _ResourceTable:
    if depth > 2 or table_offset in ancestors:
        _fail("Resource table depth or cycle is unsupported.")
    budget.tables += 1
    if budget.tables > _MAX_RESOURCE_TABLES:
        _fail("Total resource-table bound exceeded.")
    header = _slice(image, root_offset + table_offset, 16, "resource table header")
    named_count, id_count = struct.unpack_from("<HH", header, 12)
    count = named_count + id_count
    if count > _MAX_RESOURCE_ENTRIES:
        _fail("Resource table exceeds the entry bound.")
    budget.entries += count
    if budget.entries > _MAX_TOTAL_RESOURCE_ENTRIES:
        _fail("Total resource-entry bound exceeded.")
    table_size = 16 + count * 8
    _claim(ranges, table_offset, table_size, root_size, "resource table")
    table = _ResourceTable(header[:12])
    raw_entries: list[tuple[int | str, int]] = []
    seen_keys: set[int | str] = set()
    for index in range(count):
        name_field, target = struct.unpack(
            "<II",
            _slice(image, root_offset + table_offset + 16 + index * 8, 8, "resource entry"),
        )
        key = _parse_resource_name(image, root_offset, name_field, root_size, ranges)
        raw_entries.append((key, target))
        if key in seen_keys:
            _fail("Resource table contains duplicate keys.")
        seen_keys.add(key)
    if sum(isinstance(key, str) for key, _ in raw_entries) != named_count:
        _fail("Resource table name/ID counts are inconsistent.")
    if [key for key, _ in raw_entries] != sorted(
        (key for key, _ in raw_entries), key=_resource_sort_key
    ):
        _fail("Resource entries are not in the canonical PE order.")

    ancestors.add(table_offset)
    try:
        for key, target in raw_entries:
            if target & 0x80000000:
                if depth == 2:
                    _fail("Resource leaf level unexpectedly contains a subdirectory.")
                child_offset = target & 0x7FFFFFFF
                entry: _ResourceTable | _ResourceData = _parse_resource_table(
                    image,
                    pe,
                    resource_section,
                    resource_offset,
                    root_offset,
                    root_size,
                    child_offset,
                    depth + 1,
                    ancestors,
                    ranges,
                    budget,
                )
            else:
                if depth != 2:
                    _fail("Resource data appears before the language leaf level.")
                budget.leaves += 1
                if budget.leaves > _MAX_RESOURCE_ENTRIES:
                    _fail("Resource leaf count exceeds the bound.")
                descriptor_offset = target
                _claim(ranges, descriptor_offset, 16, root_size, "resource data descriptor")
                data_rva, data_size, codepage, reserved = struct.unpack(
                    "<IIII",
                    _slice(image, root_offset + descriptor_offset, 16, "resource data descriptor"),
                )
                # Resource data must remain in this same bounded resource section.
                data_section_matches = [
                    section
                    for section in pe.sections
                    if section.virtual_address <= data_rva
                    and data_rva - section.virtual_address <= section.raw_size
                    and data_size <= section.raw_size - (data_rva - section.virtual_address)
                ]
                relative_data = data_rva - resource_section.virtual_address
                if (
                    len(data_section_matches) != 1
                    or data_section_matches[0] != resource_section
                    or relative_data < 0
                    or relative_data + data_size > resource_section.raw_size
                ):
                    _fail("Resource payload does not map within its unique resource section.")
                payload_file_offset = resource_section.raw_pointer + relative_data
                payload_relative = payload_file_offset - resource_offset
                _claim(ranges, payload_relative, data_size, root_size, "resource payload")
                payload = _slice(image, payload_file_offset, data_size, "resource payload")
                entry = _ResourceData(payload, codepage, reserved)
            table.entries[key] = entry
    finally:
        ancestors.remove(table_offset)
    return table


def _read_resource_tree(image: bytes, pe: _PeImage) -> _ResourceTable:
    section, root_offset, root_size = _resource_section(pe, image)
    if root_offset != section.raw_pointer:
        _fail("Resource root must begin at its section boundary.")
    ranges: list[tuple[int, int]] = []
    budget = _ResourceBudget()
    root = _parse_resource_table(
        image, pe, section, root_offset, root_offset, root_size, 0, 0, set(), ranges, budget
    )
    if budget.leaves == 0:
        _fail("Resource directory contains no payload entries.")
    return root


def _resource_name_bytes(name: str) -> bytes:
    encoded = name.encode("utf-16-le", errors="strict")
    units = len(encoded) // 2
    if not encoded or units > 0xFFFF:
        _fail("Resource name is empty or exceeds the UTF-16 unit bound.")
    return struct.pack("<H", units) + encoded


def _table_entries(table: _ResourceTable) -> list[tuple[int | str, _ResourceNode]]:
    return sorted(table.entries.items(), key=lambda item: _resource_sort_key(item[0]))


def _resource_directory(root: _ResourceTable, base_rva: int) -> bytes:
    tables: list[_ResourceTable] = []
    table_offsets: dict[int, int] = {}
    name_offsets: dict[tuple[int, str], int] = {}
    description_offsets: dict[tuple[int, int | str], int] = {}
    strings = bytearray()
    descriptions: list[tuple[int, int, int, int]] = []
    payloads = bytearray()
    table_cursor = 0

    def visit(table: _ResourceTable) -> None:
        nonlocal table_cursor
        if len(table.header_prefix) != 12:
            _fail("Resource table header prefix must preserve all 12 fixed bytes.")
        identity = id(table)
        if identity in table_offsets:
            _fail("Resource tree aliases a child table.")
        entries = _table_entries(table)
        if len(entries) > _MAX_RESOURCE_ENTRIES:
            _fail("Resource table exceeds the entry bound.")
        table_offsets[identity] = table_cursor
        tables.append(table)
        table_cursor += 16 + len(entries) * 8
        for key, _entry in entries:
            if isinstance(key, str):
                name_offsets[(identity, key)] = len(strings)
                strings.extend(_resource_name_bytes(key))
        for key, entry in entries:
            if isinstance(entry, _ResourceData):
                if len(entry.payload) > 0xFFFFFFFF:
                    _fail("Resource payload exceeds the PE data-entry limit.")
                description_offsets[(identity, key)] = len(descriptions) * 16
                descriptions.append((0, len(entry.payload), entry.codepage, entry.reserved))
                payloads.extend(entry.payload)
        for _key, entry in entries:
            if isinstance(entry, _ResourceTable):
                visit(entry)

    visit(root)
    table_region_size = table_cursor
    string_region_size = len(strings)
    description_region_size = len(descriptions) * 16

    # Resource payloads are appended in the same deterministic direct-leaves-then-children
    # Match the qualified resource ordering. Rewalk to assign each descriptor its payload RVA.
    payload_cursor = 0
    descriptor_index = 0
    descriptor_values: list[tuple[int, int, int, int]] = []

    def assign_payloads(table: _ResourceTable) -> None:
        nonlocal payload_cursor, descriptor_index
        for _key, entry in _table_entries(table):
            if isinstance(entry, _ResourceData):
                rva = (
                    base_rva
                    + table_region_size
                    + string_region_size
                    + description_region_size
                    + payload_cursor
                )
                if rva > 0xFFFFFFFF or len(entry.payload) > 0xFFFFFFFF - rva:
                    _fail("Resource payload RVA exceeds the PE address range.")
                descriptor_values.append((rva, len(entry.payload), entry.codepage, entry.reserved))
                payload_cursor += len(entry.payload)
                descriptor_index += 1
        for _key, entry in _table_entries(table):
            if isinstance(entry, _ResourceTable):
                assign_payloads(entry)

    assign_payloads(root)
    if descriptor_index != len(descriptions) or payload_cursor != len(payloads):
        _fail("Resource serialization accounting is inconsistent.")
    description_bytes = b"".join(struct.pack("<IIII", *item) for item in descriptor_values)

    # Build table bytes after all offsets are known; all fields are checked before packing.
    table_bytes = bytearray()
    for table in tables:
        entries = _table_entries(table)
        named_count = sum(isinstance(key, str) for key, _entry in entries)
        id_count = len(entries) - named_count
        header = table.header_prefix + struct.pack("<HH", named_count, id_count)
        if len(header) != 16:
            _fail("Serialized resource table header is not exactly 16 bytes.")
        table_bytes.extend(header)
        for key, entry in entries:
            if isinstance(key, str):
                relative_name = name_offsets[(id(table), key)]
                name_field = table_region_size + relative_name
                if name_field > 0x7FFFFFFF:
                    _fail("Resource name offset exceeds the PE directory range.")
                name_field |= 0x80000000
            else:
                if not 0 <= key <= 0xFFFF:
                    _fail("Numeric resource identifier exceeds the PE format limit.")
                name_field = key
            if isinstance(entry, _ResourceTable):
                target = table_offsets[id(entry)]
                if target > 0x7FFFFFFF:
                    _fail("Resource table offset exceeds the PE directory range.")
                target |= 0x80000000
            else:
                target = (
                    table_region_size + string_region_size + description_offsets[(id(table), key)]
                )
                if target > 0x7FFFFFFF:
                    _fail("Resource descriptor offset exceeds the PE directory range.")
            table_bytes.extend(struct.pack("<II", name_field, target))

    return bytes(table_bytes + strings + description_bytes + payloads)


def _add_resource_values(root: _ResourceTable, interpreter: str, script: bytes) -> _ResourceTable:
    if set(root.entries) != {_RT_MANIFEST}:
        _fail("Pinned template resource inventory is not the expected manifest-only tree.")
    manifest_type = root.entries[_RT_MANIFEST]
    if not isinstance(manifest_type, _ResourceTable):
        _fail("Pinned manifest type is not a resource table.")
    if set(manifest_type.entries) != {_MANIFEST_NAME}:
        _fail("Pinned template manifest identifier is unexpected.")
    manifest_name = manifest_type.entries[_MANIFEST_NAME]
    if not isinstance(manifest_name, _ResourceTable):
        _fail("Pinned manifest name is not a resource table.")
    if set(manifest_name.entries) != {_MANIFEST_LANGUAGE}:
        _fail("Pinned template manifest language is unexpected.")
    if not isinstance(manifest_name.entries[_MANIFEST_LANGUAGE], _ResourceData):
        _fail("Pinned manifest leaf is not resource data.")

    path_data = _ResourceData(interpreter.encode("utf-8"), _CODE_PAGE_ID_EN_US)
    script_data = _ResourceData(_build_script_archive(script), _CODE_PAGE_ID_EN_US)
    kind_data = _ResourceData(b"\x01", _CODE_PAGE_ID_EN_US)
    root.entries[_RT_RCDATA] = _ResourceTable(
        entries={
            "UV_PYTHON_PATH": _ResourceTable(entries={_RESOURCE_LEAF_LANGUAGE: path_data}),
            "UV_SCRIPT_DATA": _ResourceTable(entries={_RESOURCE_LEAF_LANGUAGE: script_data}),
            "UV_TRAMPOLINE_KIND": _ResourceTable(entries={_RESOURCE_LEAF_LANGUAGE: kind_data}),
        }
    )
    return root


def _build_script_archive(script: bytes) -> bytes:
    """Reproduce the pinned one-member, stored, non-ZIP64 archive layout."""
    if not isinstance(script, bytes) or not script or len(script) > _MAX_SCRIPT_BYTES:
        _fail("Expected launcher script is empty or exceeds the byte bound.")
    filename = b"__main__.py"
    crc = zlib.crc32(script) & 0xFFFFFFFF
    size = len(script)
    if size > 0xFFFFFFFF:
        _fail("Script payload exceeds the ZIP32 limit.")
    flags = 0x0800
    local = (
        struct.pack(
            "<IHHHHHIIIHH",
            0x04034B50,
            10,
            flags,
            0,
            0,
            0x0021,
            crc,
            size,
            size,
            len(filename),
            0,
        )
        + filename
        + script
    )
    central = (
        struct.pack(
            "<IHHHHHHIIIHHHHHII",
            0x02014B50,
            0x033F,
            10,
            flags,
            0,
            0,
            0x0021,
            crc,
            size,
            size,
            len(filename),
            0,
            0,
            0,
            0,
            0,
            0,
        )
        + filename
    )
    central_offset = len(local)
    if central_offset > 0xFFFFFFFF or len(central) > 0xFFFFFFFF:
        _fail("ZIP32 central directory exceeds its format limit.")
    end = struct.pack(
        "<IHHHHIIH",
        0x06054B50,
        0,
        0,
        1,
        1,
        len(central),
        central_offset,
        0,
    )
    return local + central + end


def _reconstruct_launcher(template: bytes, interpreter: str, script: bytes) -> bytes:
    """Rebuild one supported PE entirely; reject layouts outside source proof."""
    if not isinstance(template, bytes) or len(template) > _MAX_IMAGE_BYTES:
        _fail("Trusted PE template exceeds the image bound.")
    try:
        interpreter_bytes = interpreter.encode("utf-8", errors="strict")
    except (AttributeError, UnicodeEncodeError) as error:
        raise ValueError("Expected interpreter is not valid UTF-8 text.") from error
    if (
        not interpreter_bytes
        or len(interpreter_bytes) > _MAX_INTERPRETER_BYTES
        or b"\0" in interpreter_bytes
    ):
        _fail("Expected interpreter is empty, contains NUL, or exceeds the bound.")

    pe = _parse_pe(template)
    cert_rva, cert_size = pe.directories[4]
    if cert_rva or cert_size:
        _fail("Certificate-bearing PE templates are outside the verified reconstruction scope.")
    section, resource_offset, _resource_size = _resource_section(pe, template)
    if section.name != b".rsrc\0\0\0" or resource_offset != section.raw_pointer:
        _fail("Resource section layout is unsupported.")
    if section is sorted(pe.sections, key=lambda item: item.raw_pointer)[-1]:
        _fail("In-place or last-section resource replacement is outside the verifier scope.")
    if any(
        index != 2 and address and section.virtual_address <= address < section.virtual_end
        for index, (address, _size) in enumerate(pe.directories)
    ):
        _fail("A second PE directory shares the resource section.")
    if pe.last_raw_end > len(template):
        _fail("PE section table exceeds its bounded template.")

    root = _read_resource_tree(template, pe)
    _add_resource_values(root, interpreter, script)
    virtual_end = max(item.virtual_end for item in pe.sections)
    virtual_address = _align(virtual_end, pe.section_alignment, "new section virtual address")
    resource_bytes = _resource_directory(root, virtual_address)
    resource_size = len(resource_bytes)
    raw_size = _align(resource_size, pe.file_alignment, "resource section")
    if raw_size <= section.raw_size:
        _fail("The pinned writer would update the existing resource section in place.")

    raw_pointer = _align(pe.last_raw_end, pe.file_alignment, "new section file offset")
    size_of_image = _align(virtual_address + resource_size, pe.section_alignment, "SizeOfImage")
    if raw_pointer + raw_size > _MAX_IMAGE_BYTES:
        _fail("Reconstructed PE exceeds the image bound.")
    if len(pe.sections) >= _MAX_SECTIONS:
        _fail("Adding a resource section would exceed the section bound.")

    section_table_end = pe.section_table_offset + len(pe.sections) * 40
    if section_table_end != max(item.header_offset + 40 for item in pe.sections):
        _fail("PE section headers are not contiguous.")
    available_header_space = pe.first_raw - section_table_end
    if available_header_space < 40:
        _fail("PE header has no verified room for the resource section header.")
    new_section_header = struct.pack(
        "<8sIIIIIIHHI",
        b".pedata\0",
        resource_size,
        virtual_address,
        raw_size,
        raw_pointer,
        0,
        0,
        0,
        0,
        _IMAGE_SCN_CNT_INITIALIZED_DATA | _IMAGE_SCN_MEM_READ,
    )
    header = bytearray(
        template[:section_table_end]
        + new_section_header
        + template[section_table_end + 40 : pe.first_raw]
    )
    if len(header) != pe.first_raw:
        _fail("PE header growth did not preserve the first section offset.")
    struct.pack_into("<H", header, pe.coff_offset + 2, len(pe.sections) + 1)
    struct.pack_into("<I", header, pe.optional_offset + 56, size_of_image)
    struct.pack_into("<I", header, pe.optional_offset + 64, 0)
    struct.pack_into("<II", header, pe.directories_offset + 2 * 8, virtual_address, resource_size)

    resource_start = section.raw_pointer
    resource_end = section.raw_end
    if not pe.first_raw <= resource_start < resource_end <= pe.last_raw_end:
        _fail("Resource section raw range is invalid.")
    padding = raw_pointer - pe.last_raw_end
    new_section_data = resource_bytes + bytes(raw_size - resource_size)
    output = bytearray(header)
    output.extend(template[pe.first_raw : resource_start])
    output.extend(template[resource_start:resource_end])
    output.extend(template[resource_end : pe.last_raw_end])
    output.extend(bytes(padding))
    output.extend(new_section_data)
    output.extend(template[pe.last_raw_end :])
    if len(output) > _MAX_IMAGE_BYTES:
        _fail("Reconstructed PE exceeds the image bound.")
    return bytes(output)


def _verify_candidate_bytes(candidate: bytes, expected: bytes) -> None:
    if not isinstance(candidate, bytes) or len(candidate) != len(expected) or candidate != expected:
        _fail("Candidate PE does not exactly match the independently reconstructed bytes.")


def _validate_pinned_template(template: bytes) -> None:
    if len(template) != _TEMPLATE_SIZE or hashlib.sha256(template).hexdigest() != _TEMPLATE_SHA256:
        _fail("Template bytes do not match the pinned x64 console launcher source.")
    pe = _parse_pe(template)
    expected_sections = (
        (b".text\0\0\0", 0x6E40, 0x1000, 0x7000, 0x400),
        (b".rdata\0\0", 0x275C, 0x8000, 0x2800, 0x7400),
        (b".data\0\0\0", 0xFC, 0xB000, 0x200, 0x9C00),
        (b".pdata\0\0", 0x570, 0xC000, 0x600, 0x9E00),
        (b".CRT\0\0\0\0", 0x10, 0xD000, 0x200, 0xA400),
        (b".tls\0\0\0\0", 0x11, 0xE000, 0x200, 0xA600),
        (b".rsrc\0\0\0", 0x580, 0xF000, 0x600, 0xA800),
        (b".reloc\0\0", 0xE4, 0x10000, 0x200, 0xAE00),
    )
    observed = tuple(
        (
            section.name,
            section.virtual_size,
            section.virtual_address,
            section.raw_size,
            section.raw_pointer,
        )
        for section in pe.sections
    )
    if (
        pe.pe_offset != 0x78
        or observed != expected_sections
        or pe.section_alignment != 0x1000
        or pe.file_alignment != 0x200
        or pe.first_raw != 0x400
        or pe.last_raw_end != len(template)
        or pe.directories[2] != (0xF000, 0x580)
        or pe.directories[4] != (0, 0)
    ):
        _fail("Pinned PE template layout differs from the source-characterized inventory.")
    root = _read_resource_tree(template, pe)
    if set(root.entries) != {_RT_MANIFEST}:
        _fail("Pinned PE template has an unexpected resource inventory.")
    manifest_type = root.entries[_RT_MANIFEST]
    if not isinstance(manifest_type, _ResourceTable) or set(manifest_type.entries) != {
        _MANIFEST_NAME
    }:
        _fail("Pinned PE manifest type/name inventory is unexpected.")
    manifest_name = manifest_type.entries[_MANIFEST_NAME]
    if not isinstance(manifest_name, _ResourceTable) or set(manifest_name.entries) != {
        _MANIFEST_LANGUAGE
    }:
        _fail("Pinned PE manifest language inventory is unexpected.")
    manifest = manifest_name.entries[_MANIFEST_LANGUAGE]
    if not isinstance(manifest, _ResourceData) or manifest.codepage != 0 or manifest.reserved != 0:
        _fail("Pinned PE manifest data metadata is unexpected.")


def verify_windows_console_launcher(
    candidate: bytes,
    template: bytes,
    expected_interpreter: str,
    expected_script: bytes,
) -> None:
    """Verify an x64 console launcher by exact, non-executing reconstruction.

    The supplied template must be the exact pinned console trampoline. The
    interpreter display path and complete ``__main__.py`` payload are supplied
    independently by the caller. No semantic-only byte matching is accepted.
    """
    if not isinstance(candidate, bytes) or len(candidate) > _MAX_IMAGE_BYTES:
        _fail("Candidate PE is not bytes or exceeds the image bound.")
    if not isinstance(template, bytes):
        _fail("Template PE must be bytes.")
    if not isinstance(expected_interpreter, str):
        _fail("Expected interpreter path must be text.")
    if not isinstance(expected_script, bytes):
        _fail("Expected script payload must be bytes.")
    _validate_pinned_template(template)
    expected = _reconstruct_launcher(template, expected_interpreter, expected_script)
    _verify_candidate_bytes(candidate, expected)
