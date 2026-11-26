"""Exercise the native runtime preparation boundary with synthetic archives."""

import hashlib
import io
import tarfile
from pathlib import Path

import pytest


def _archive(tmp_path: Path, extra: tarfile.TarInfo | None = None) -> Path:
    path = tmp_path / "runtime.tar.gz"
    with tarfile.open(path, "w:gz") as stream:
        for name, body in (
            ("python/bin/python3.12", b"not executable"),
            ("python/lib/python3.12/LICENSE.txt", b"synthetic license"),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(body)
            info.mode = 0o755
            stream.addfile(info, io.BytesIO(body))
        link = tarfile.TarInfo("python/bin/python3")
        link.type = tarfile.SYMTYPE
        link.linkname = "python3.12"
        stream.addfile(link)
        if extra is not None:
            stream.addfile(extra)
    return path


def test_extracts_archive_and_keeps_in_tree_alias(tmp_path: Path) -> None:
    from scripts.release_qualification.first_stable_runtime import extract_runtime

    archive = _archive(tmp_path)
    output = tmp_path / "runtime"
    executable = extract_runtime(
        archive,
        output,
        "3.12.16",
        archive.stat().st_size,
        hashlib.sha256(archive.read_bytes()).hexdigest(),
        case_sensitive=False,
    )
    assert executable == output / "python/bin/python3.12"
    assert executable.read_bytes() == b"not executable"
    assert (output / "python/bin/python3").is_symlink()
    assert (output / "python/lib/python3.12/LICENSE.txt").read_bytes() == b"synthetic license"


@pytest.mark.parametrize(
    ("name", "kind", "linkname"),
    [
        ("python/../escape", tarfile.REGTYPE, ""),
        ("/etc/escape", tarfile.REGTYPE, ""),
        ("python/bin/python3/through-alias", tarfile.REGTYPE, ""),
        ("python/bin/outside", tarfile.SYMTYPE, "../../../escape"),
        ("python/bin/loop", tarfile.SYMTYPE, "loop"),
        ("python/bin/missing", tarfile.SYMTYPE, "no-such-file"),
        ("python/bin/FIFO", tarfile.FIFOTYPE, ""),
        ("python/Bin/alias", tarfile.REGTYPE, ""),
    ],
)
def test_rejects_unsafe_archive_before_any_output(
    tmp_path: Path, name: str, kind: bytes, linkname: str
) -> None:
    from scripts.release_qualification.first_stable_runtime import extract_runtime

    item = tarfile.TarInfo(name)
    item.type = kind
    item.linkname = linkname
    archive = _archive(tmp_path, item)
    target = tmp_path / "runtime"
    with pytest.raises(ValueError):
        extract_runtime(
            archive,
            target,
            "3.12.16",
            archive.stat().st_size,
            hashlib.sha256(archive.read_bytes()).hexdigest(),
            case_sensitive=False,
        )
    assert not target.exists()


def test_rejects_wrong_digest_or_preexisting_output(tmp_path: Path) -> None:
    from scripts.release_qualification.first_stable_runtime import extract_runtime

    archive = _archive(tmp_path)
    size = archive.stat().st_size
    output = tmp_path / "runtime"
    with pytest.raises(ValueError, match="digest"):
        extract_runtime(archive, output, "3.12.16", size, "0" * 64, case_sensitive=False)
    assert not output.exists()
    output.mkdir()
    sentinel = output / "preserve"
    sentinel.write_bytes(b"original")
    with pytest.raises(FileExistsError):
        extract_runtime(
            archive,
            output,
            "3.12.16",
            size,
            hashlib.sha256(archive.read_bytes()).hexdigest(),
            case_sensitive=False,
        )
    assert sentinel.read_bytes() == b"original"
