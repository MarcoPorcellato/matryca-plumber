"""Synthetic acquisition errors; no public requests or package execution."""

from __future__ import annotations

import io
import json
import ssl
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

import pytest
from scripts import qualify_release_package as qualification
from scripts.release_qualification import alpha1_public as public
from scripts.release_qualification import sdist_build

TAG = "v2.1.0-alpha.3"
URL = "https://api.github.com/repos/MarcoPorcellato/matryca-plumber/releases/assets/1"
WHEEL = "matryca_plumber-2.1.0a3-py3-none-any.whl"


@pytest.mark.parametrize("status", [403, 429, 500])
@pytest.mark.parametrize(
    ("kind", "url", "asset", "size", "digest"),
    [
        ("github", URL, WHEEL, 10, "a" * 64),
        ("pypi", "https://files.pythonhosted.org/packages/fixture.whl", WHEEL, 10, "a" * 64),
        ("pypi-metadata", "https://pypi.org/pypi/matryca-plumber/2.1.0a3/json", "pypi.json", 0, ""),
    ],
)
def test_fetch_failure_reaches_admission_without_retry_or_secret_disclosure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    kind: str,
    url: str,
    asset: str,
    size: int,
    digest: str,
) -> None:
    requests = 0
    launches = 0

    def fail_request(_request: Any) -> Any:
        nonlocal requests
        requests += 1
        raise HTTPError(
            URL + "?token=synthetic-private-token",
            status,
            "synthetic-private-message\x1b[31m",
            {},  # type: ignore[arg-type]
            io.BytesIO(b"synthetic-private-body"),
        )

    def run_child(command: list[str], **kwargs: Any) -> sdist_build._CommandResult:
        nonlocal launches
        launches += 1
        assert kwargs == {"timeout": 120, "capture": True}
        output = io.StringIO()
        with (
            redirect_stdout(output),
            redirect_stderr(io.StringIO()),
            pytest.raises(SystemExit) as error,
        ):
            qualification.main(command[3:])
        assert error.value.code == 2
        return sdist_build._CommandResult(2, output.getvalue().encode())

    monkeypatch.setattr(public, "_open", fail_request)
    monkeypatch.setattr(sdist_build, "_run_bounded", run_child)
    with pytest.raises(ValueError) as error:
        public._acquire(url, tmp_path / asset, size, digest, kind, release_tag=TAG)
    message = str(error.value)
    assert "synthetic-private" not in message and "https://" not in message
    assert message.startswith("One-shot public acquisition failed: ")
    record = json.loads(message.split(": ", 1)[1])
    assert record["kind"] == kind and record["asset"] == asset
    assert record["returncode"] == 2
    assert record["failure"] == {
        "schema_version": 1,
        "error_type": "ValueError",
        "cause_type": "HTTPError",
        "message": "Public redirect limit or HTTP failure.",
        "http_status": status,
        "errno": None,
    }
    assert launches == requests == 1
    assert not (tmp_path / asset).exists()


@pytest.mark.parametrize(
    "failure",
    [
        URLError("https://private.invalid/?token=secret"),
        FileNotFoundError(2, "secret", "/private/secret-path"),
        ValueError("secret\x1b[31m\nhttps://private.invalid/?token=secret"),
    ],
    ids=["url", "path", "arbitrary-message"],
)
def test_fetch_cli_failure_emits_only_closed_diagnostic_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: OSError | ValueError,
) -> None:
    def fail_fetch(*_args: Any, **_kwargs: Any) -> None:
        raise failure

    monkeypatch.setattr(public, "fetch_file", fail_fetch)
    with pytest.raises(SystemExit) as error:
        qualification.main(
            [
                "alpha-public-fetch",
                "--url",
                URL,
                "--output",
                str(tmp_path / WHEEL),
                "--size",
                "10",
                "--sha256=" + "a" * 64,
                "--kind",
                "github",
                "--release-tag",
                TAG,
            ]
        )
    assert error.value.code == 2
    output = capsys.readouterr().out
    assert output
    record = json.loads(output)
    assert set(record) == {
        "schema_version",
        "error_type",
        "cause_type",
        "message",
        "http_status",
        "errno",
    }
    assert record["message"] == "Error details redacted."
    assert "secret" not in output and "private" not in output and "\x1b" not in output
    assert len(output.encode()) <= 4096


def test_success_remains_silent_and_keeps_one_shot_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def succeed(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(public, "fetch_file", succeed)
    args = qualification._parser().parse_args(
        [
            "alpha-public-fetch",
            "--url",
            URL,
            "--output",
            str(tmp_path / WHEEL),
            "--size",
            "10",
            "--sha256=" + "a" * 64,
            "--kind",
            "github",
            "--release-tag",
            TAG,
        ]
    )
    qualification._alpha_public_fetch(args)
    assert capsys.readouterr().out == ""
    calls = 0

    def run_child(_command: list[str], **kwargs: Any) -> sdist_build._CommandResult:
        nonlocal calls
        calls += 1
        assert kwargs == {"timeout": 120, "capture": True}
        return sdist_build._CommandResult(0, b"")

    monkeypatch.setattr(sdist_build, "_run_bounded", run_child)
    public._acquire(URL, tmp_path / WHEEL, 10, "a" * 64, "github", release_tag=TAG)
    assert calls == 1


@pytest.mark.parametrize(
    "output",
    [
        b"secret-token\x1b[31m",
        b'{"private":"secret"}',
        b"x" * 4097,
        b'{"schema_version":1,"error_type":"ValueError","cause_type":null,'
        b'"message":"secret","http_status":null,"errno":null}',
        b'{"schema_version":1,"error_type":"HTTPError","cause_type":null,'
        b'"message":"Error details redacted.","http_status":true,"errno":null}',
    ],
    ids=["text", "unknown-fields", "oversized", "untrusted-message", "boolean-status"],
)
def test_parent_never_echoes_unstructured_or_malformed_child_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: bytes
) -> None:
    monkeypatch.setattr(
        sdist_build,
        "_run_bounded",
        lambda *_args, **_kwargs: sdist_build._CommandResult(-15, output),
    )
    with pytest.raises(ValueError) as error:
        public._acquire(URL, tmp_path / "secret-path", 10, "a" * 64, "github", release_tag=TAG)
    message = str(error.value)
    assert message.startswith("One-shot public acquisition failed: ")
    record = json.loads(message.split(": ", 1)[1])
    assert record["returncode"] == -15 and record["failure"] is None
    assert record["asset"] == "unrecognized"
    assert record["child_stdout_bytes"] == len(output)
    assert len(record["child_stdout_sha256"]) == 64
    assert "secret" not in message and "\x1b" not in message and len(message) <= 4096


def test_process_owner_failure_is_not_relabelled_as_a_download_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    failure = ValueError("synthetic cleanup failure")

    def owner_failure(*_args: Any, **_kwargs: Any) -> Any:
        raise failure

    monkeypatch.setattr(sdist_build, "_run_bounded", owner_failure)
    with pytest.raises(ValueError) as error:
        public._acquire(URL, tmp_path / WHEEL, 10, "a" * 64, "github", release_tag=TAG)
    assert error.value is failure


def test_tls_reason_survives_without_echoing_exception_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail_fetch(*_args: Any, **_kwargs: Any) -> None:
        raise URLError(ssl.SSLCertVerificationError(1, "secret certificate text"))

    monkeypatch.setattr(public, "fetch_file", fail_fetch)
    args = qualification._parser().parse_args(
        [
            "alpha-public-fetch",
            "--url",
            URL,
            "--output",
            str(tmp_path / WHEEL),
            "--size",
            "10",
            "--sha256=" + "a" * 64,
            "--kind",
            "github",
            "--release-tag",
            TAG,
        ]
    )
    with pytest.raises(URLError):
        qualification._alpha_public_fetch(args)
    output = capsys.readouterr().out
    record = json.loads(output)
    assert record["error_type"] == "URLError"
    assert record["cause_type"] == "SSLCertVerificationError" and record["errno"] == 1
    assert "secret" not in output
