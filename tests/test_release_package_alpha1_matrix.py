"""Synthetic acceptance tests for the separate, still-unqualified alpha matrix."""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from scripts.release_qualification.bundle import BundleBinding


def _inputs(
    *, run_attempt: int = 2
) -> tuple[Any, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    alpha = importlib.import_module("scripts.release_qualification.alpha1_matrix")
    binding = BundleBinding(
        "a" * 40,
        "b" * 40,
        "2.1.0a2",
        "matryca_plumber-2.1.0a2-py3-none-any.whl",
        1,
        "c" * 64,
        "matryca_plumber-2.1.0a2.tar.gz",
        2,
        "d" * 64,
        "e" * 64,
        "f" * 64,
    )
    context = alpha.MatrixContext(
        binding,
        "123",
        run_attempt,
        {
            "assets": [],
            "code_modules": [],
            "descriptor_sha256": "1" * 64,
            "manifest_sha256": "2" * 64,
        },
        {"finite": ["tests/test_fixture.py::test_boundary"]},
        "3" * 64,
        "4" * 64,
        (("setuptools", "84.0.0"), ("wheel", "0.48.0")),
        ("logseq-matryca-parser==1.9.0",),
    )
    rows: list[dict[str, Any]] = []
    for system, architecture, minor, kind in alpha.ROWS:
        target = f"{system}-{architecture}"
        key = f"{target}-{minor}-{kind}"
        runtime = {
            "implementation": "CPython",
            "version": minor + ".13",
            "system": system,
            "architecture": architecture,
            "executable_sha256": "5" * 64,
        }
        installed = alpha.installed.InstalledReceipt(
            kind=kind,
            operating_system="linux" if system == "linux" else "darwin",
            architecture="x86_64" if architecture == "x64" else "arm64",
            python_version=runtime["version"],
            version="2.1.0a2",
            location_class="isolated-venv-site-packages",
            record_sha256="6" * 64,
            resource_sha256="7" * 64,
            dependency_sha256=alpha.digest([["logseq-matryca-parser", "1.9.0"]]),
            dependencies=(("logseq-matryca-parser", "1.9.0"),),
            build_generator=alpha.installed.BuildGenerator("setuptools", "84.0.0"),
            tck_outcomes=("PASS", "PASS", "PASS"),
        ).to_dict()
        report = {
            "schema_version": 1,
            "profile": "plumber.og.operational/v1",
            "qualification": "unqualified",
            "status": "pass",
            "reason": "black_box_controls_passed",
            "resources": context.resources,
            "checks": [{"id": name, "status": "pass"} for name in alpha.OPERATIONAL_CHECKS],
            "cleanup": {"status": "verified", "retained_owned_synthetic_root": False},
            "environment": {
                "installed_origin": True,
                "editable": False,
                "operating_system": "Linux" if system == "linux" else "Darwin",
                "architecture": installed["architecture"],
                "python_version": runtime["version"],
                "plumber_version": "2.1.0a2",
                "parser_version": "1.9.0",
                "sha256": "8" * 64,
            },
            "evidence_limits": {
                "source_unit_controls": {
                    "status": "mapped_not_executed_by_installed_tck",
                    "tests": context.source_controls,
                }
            },
        }
        build = None
        if kind == "sdist":
            build = {
                "instance": key,
                "python_implementation": "CPython",
                "python_version": "3.12.13",
                "target_os": system,
                "target_architecture": architecture,
                "source_commit": binding.source_commit,
                "source_tree": binding.source_tree,
                "binding_sha256": alpha.digest(asdict(binding)),
                "sdist_name": binding.sdist_name,
                "sdist_size": binding.sdist_size,
                "sdist_sha256": binding.sdist_sha256,
                "wheel_name": binding.wheel_name,
                "wheel_size": 3,
                "wheel_sha256": "9" * 64,
                "build_lock_sha256": context.build_lock_sha256,
                "provisioning_recipe_sha256": context.recipe_sha256,
                "provisioned_packages": [
                    {"name": name, "version": version} for name, version in context.build_packages
                ],
                "before_hooks_packages": [
                    {"name": name, "version": version} for name, version in context.build_packages
                ],
                "after_hooks_packages": [
                    {"name": name, "version": version} for name, version in context.build_packages
                ],
                "after_build_packages": [
                    {"name": name, "version": version} for name, version in context.build_packages
                ],
                "environment_descriptor_sha256": alpha.digest(key),
                "provisioning_evidence_sha256": alpha.digest("provisioned:" + key),
                "python_executable_sha256": "a" * 64,
                "uv_sha256": "b" * 64,
                "uv_version": "0.12.19",
                "schema_version": 2,
                "backend": "setuptools.build_meta",
                "backend_version": "84.0.0",
                "static_requirement_records": [
                    {
                        "expression": "setuptools>=61",
                        "marker_applicable": True,
                        "satisfier": {"name": "setuptools", "version": "84.0.0"},
                    },
                    {
                        "expression": "wheel",
                        "marker_applicable": True,
                        "satisfier": {"name": "wheel", "version": "0.48.0"},
                    },
                ],
                "dynamic_requirement_records": [],
            }
        if build is not None:
            provisioning = {
                "run_id": context.run_id,
                "run_attempt": context.run_attempt,
                "instance": key,
                "operation": "uv-sync-locked-no-install-project",
            }
            build["provisioning_evidence"] = provisioning
            build["provisioning_evidence_sha256"] = alpha.digest(provisioning)
            descriptor = {
                name: build[name]
                for name in (
                    "source_commit",
                    "source_tree",
                    "binding_sha256",
                    "sdist_name",
                    "sdist_size",
                    "sdist_sha256",
                    "build_lock_sha256",
                    "provisioning_recipe_sha256",
                    "provisioning_evidence_sha256",
                    "uv_version",
                    "uv_sha256",
                    "target_os",
                    "target_architecture",
                    "python_implementation",
                    "python_version",
                    "python_executable_sha256",
                )
            }
            descriptor.update(
                schema_version=1,
                packages=build["provisioned_packages"],
                packages_sha256=alpha.digest(build["provisioned_packages"]),
            )
            build["environment_descriptor"] = descriptor
            build["environment_descriptor_sha256"] = alpha.digest(descriptor)
        rows.append(
            {
                "schema_version": 1,
                "row": key,
                "run_id": "123",
                "run_attempt": run_attempt,
                "binding_sha256": alpha.digest(asdict(binding)),
                "inputs_sha256": context.inputs_sha256,
                "job_name": alpha.row_job_name(system, architecture, minor),
                "status": "pass",
                "qualification": "unqualified",
                "cleanup": "verified",
                "runtime": runtime,
                "installed": installed,
                "operational": report,
                "build": build,
            }
        )
    jobs = [
        {
            "name": name,
            "status": "completed",
            "conclusion": "success",
            "run_id": 123,
            "head_sha": binding.source_commit,
        }
        for name in alpha.JOB_NAMES
    ]
    source = {
        "source_commit": binding.source_commit,
        "source_tree": binding.source_tree,
        "run_id": "123",
        "run_attempt": run_attempt,
        "selectors": context.source_controls,
        "status": "pass",
        "qualification": "source-only",
        "junit_sha256": "a" * 64,
        "cases": 1,
    }
    windows = {
        "source_commit": binding.source_commit,
        "source_tree": binding.source_tree,
        "run_id": "123",
        "run_attempt": run_attempt,
        "system": "Windows",
        "architecture": "AMD64",
        "status": "pass",
        "qualification": "refusal-only",
        "exit_code": 7,
        "error": "unsupported_platform",
        "graph_accesses": 0,
    }
    return context, rows, jobs, source, windows


@pytest.mark.parametrize("mutation", ["root-lock", "profile-lock"])
def test_source_context_rejects_lock_profile_mismatch_after_source_authentication(
    tmp_path: Path, mutation: str
) -> None:
    from scripts.release_qualification import alpha1_matrix as alpha

    project = Path(__file__).resolve().parents[1]
    source = tmp_path / "source"
    resource_path = Path("matryca_plumber/graph_gateway/resources/og-v1")
    shutil.copytree(project / resource_path, source / resource_path)
    for relative in (
        "uv.lock",
        "matryca_plumber/graph_gateway/consumer.py",
        "matryca_plumber/graph_gateway/tck.py",
        "release-qualification-build/uv.lock",
        "release-qualification-build/provisioning-recipe.json",
    ):
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(project / relative, target)

    def commit_source() -> tuple[str, str]:
        subprocess.run(["git", "add", "."], cwd=source, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "user.name=Release Test",
                "-c",
                "user.email=release-test@example.invalid",
                "commit",
                "-qm",
                "synthetic lock binding",
            ],
            cwd=source,
            check=True,
        )
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip(),
            subprocess.check_output(
                ["git", "rev-parse", "HEAD^{tree}"], cwd=source, text=True
            ).strip(),
        )

    subprocess.run(["git", "init", "-q", str(source)], check=True)
    commit, tree = commit_source()
    binding = replace(_inputs()[0].binding, source_commit=commit, source_tree=tree)
    assert alpha.source_context(source, binding, "123", 1).binding == binding

    if mutation == "root-lock":
        lock = source / "uv.lock"
        lock.write_bytes(lock.read_bytes() + b"\n# synthetic root-lock change\n")
    else:
        root = source / resource_path
        profile_path = root / "dependency-profile.json"
        profile = json.loads(profile_path.read_bytes())
        profile["lock_sha256"] = "0" * 64
        profile_path.write_text(json.dumps(profile), encoding="utf-8")
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        profile_digest = hashlib.sha256(profile_path.read_bytes()).hexdigest()
        manifest["files"]["dependency-profile.json"] = profile_digest
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        descriptor_path = root / "descriptor.json"
        descriptor = json.loads(descriptor_path.read_bytes())
        descriptor["resource_digests"]["dependency_profile"] = profile_digest
        descriptor["resource_digests"]["manifest"] = hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest()
        descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")

    commit, tree = commit_source()
    rebound = replace(binding, source_commit=commit, source_tree=tree)
    with pytest.raises(
        ValueError, match="Source root lock differs from the packaged dependency profile"
    ):
        alpha.source_context(source, rebound, "123", 1)


def test_public_matrix_has_closed_truthful_admission_job_variant() -> None:
    from scripts.release_qualification import alpha1_matrix as alpha

    context, rows, jobs, source, windows = _inputs(run_attempt=1)
    public_jobs = copy.deepcopy(jobs)
    public_jobs[0]["name"] = "Admit public OG alpha"
    for job in public_jobs:
        job["head_sha"] = "d" * 40
    result = alpha.verify_matrix(
        context,
        rows,
        public_jobs,
        source,
        windows,
        public_input=True,
        verifier_commit="d" * 40,
    )
    assert result["status"] == "pass"
    with pytest.raises(ValueError):
        alpha.verify_matrix(
            context,
            rows,
            jobs,
            source,
            windows,
            public_input=True,
            verifier_commit="d" * 40,
        )
    with pytest.raises(ValueError):
        alpha.verify_matrix(context, rows, public_jobs, source, windows)


def test_public_matrix_joins_verifier_jobs_to_unchanged_producer_rows() -> None:
    from scripts.release_qualification import alpha1_matrix as alpha

    context, rows, jobs, source, windows = _inputs(run_attempt=1)
    jobs[0]["name"] = "Admit public OG alpha"
    for job in jobs:
        job["head_sha"] = "d" * 40
    result = alpha.verify_matrix(
        context, rows, jobs, source, windows, public_input=True, verifier_commit="d" * 40
    )
    assert result["source_commit"] == "a" * 40
    assert result["source_tree"] == "b" * 40
    for bad_head in ("a" * 40, "e" * 40):
        mixed = copy.deepcopy(jobs)
        mixed[0]["head_sha"] = bad_head
        with pytest.raises(ValueError):
            alpha.verify_matrix(
                context,
                rows,
                mixed,
                source,
                windows,
                public_input=True,
                verifier_commit="d" * 40,
            )
    with pytest.raises(ValueError):
        alpha.verify_matrix(context, rows, jobs, source, windows, public_input=True)
    with pytest.raises(ValueError):
        alpha.verify_matrix(context, rows, jobs, source, windows, verifier_commit="d" * 40)


def test_public_artifacts_bind_actual_verifier_head_not_package_source() -> None:
    from scripts.release_qualification import alpha1_matrix as alpha

    context = _inputs(run_attempt=1)[0]
    keys = ("admission", *alpha.ARTIFACT_KEYS[1:])
    expected = {key: {"id": str(index), "sha256": "1" * 64} for index, key in enumerate(keys, 1)}
    artifacts: list[dict[str, Any]] = [
        {
            "id": index,
            "name": "og-public-123-1-" + key,
            "digest": "sha256:" + "1" * 64,
            "expired": False,
            "workflow_run": {"id": 123, "head_sha": "d" * 40},
        }
        for index, key in enumerate(keys, 1)
    ]
    result = alpha.verify_artifacts(
        context, expected, artifacts, public_input=True, verifier_commit="d" * 40
    )
    assert set(result) == set(keys)
    artifacts[0]["workflow_run"]["head_sha"] = "a" * 40
    with pytest.raises(ValueError):
        alpha.verify_artifacts(
            context, expected, artifacts, public_input=True, verifier_commit="d" * 40
        )


def test_alpha_matrix_requires_eight_rows_and_keeps_unqualified_status() -> None:
    context, rows, jobs, source, windows = _inputs()
    alpha = importlib.import_module("scripts.release_qualification.alpha1_matrix")
    result = alpha.verify_matrix(context, rows, jobs, source, windows)
    assert result["status"] == "pass" and result["qualification"] == "unqualified"
    assert len(result["rows"]) == 8


def test_alpha_accepts_the_existing_installed_probe_receipt(tmp_path: Path) -> None:
    """The actual probe uses lowercase OS and excludes the project and pip."""
    alpha = importlib.import_module("scripts.release_qualification.alpha1_matrix")
    context, rows, *_rest = _inputs()
    environment = tmp_path / "synthetic-environment"
    site = environment / "site-packages"
    site.mkdir(parents=True)
    for name in ("src", "frontend"):
        package = site / name
        package.mkdir()
        (package / "__init__.py").write_text('"""Inert synthetic probe package."""\n')
    for name, version in (
        ("logseq-matryca-parser", "1.9.0"),
        ("matryca-plumber", "2.1.0a2"),
        ("pip", "99.0"),
    ):
        metadata = site / (name.replace("-", "_") + "-" + version + ".dist-info")
        metadata.mkdir()
        (metadata / "METADATA").write_text(f"Name: {name}\nVersion: {version}\n")
    _site, _origin, dependency_sha, version, system, machine, dependencies = (
        alpha.installed._isolated_probe(
            Path(sys.executable), environment, site, tmp_path / "unrelated-source"
        )
    )
    assert dependencies == (("logseq-matryca-parser", "1.9.0"),)
    assert system == platform.system().lower()
    selected = (
        "linux" if system == "linux" else "macos",
        "x64" if machine == "x86_64" else "arm64",
        ".".join(version.split(".")[:2]),
        "wheel",
    )
    row = next(item for item in rows if item["row"] == "-".join(selected))
    receipt = alpha.installed.InstalledReceipt(
        kind="wheel",
        operating_system=system,
        architecture=machine,
        python_version=version,
        version="2.1.0a2",
        location_class="isolated-venv-site-packages",
        record_sha256="6" * 64,
        resource_sha256="7" * 64,
        dependency_sha256=dependency_sha,
        dependencies=dependencies,
        build_generator=alpha.installed.BuildGenerator("setuptools", "84.0.0"),
        tck_outcomes=("PASS", "PASS", "PASS"),
    )
    row["installed"] = receipt.to_dict()
    row["runtime"]["version"] = version
    row["operational"]["environment"].update(
        operating_system=platform.system(), python_version=version
    )
    alpha.verify_row(context, row, selected)


@pytest.mark.parametrize("node_version", ["v22.14.0", "v24.0.0"])
def test_alpha_canonical_build_measures_frontend_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, node_version: str
) -> None:
    alpha = importlib.import_module("scripts.release_qualification.alpha1_matrix")
    context, *_rest = _inputs()
    (tmp_path / "pyproject.toml").write_text('[project]\nversion="2.1.0a2"\n')
    monkeypatch.setattr(alpha.bundle, "_git_value", lambda *_a: context.binding.source_commit)
    monkeypatch.setattr(alpha.installed, "_git_value", lambda *_a: "")
    monkeypatch.setattr(alpha, "locked_build_selection", lambda *_a: (object(), {}))
    monkeypatch.setattr(alpha, "verify_locked_build_environment", lambda *_a: None)
    monkeypatch.setattr(alpha, "build_release_artifacts", lambda *_a, **_kw: None)
    monkeypatch.setattr(alpha.bundle, "build_binding", lambda *_a, **_kw: context.binding)
    monkeypatch.setattr(
        alpha.sdist_build,
        "_run_bounded",
        lambda command, **_kw: SimpleNamespace(
            returncode=0,
            stdout=(node_version if command[0] == "node" else "10.9.2").encode() + b"\n",
        ),
    )
    if node_version != "v22.14.0":
        with pytest.raises(ValueError, match="frontend tool"):
            alpha.build_alpha(
                tmp_path,
                tmp_path / "dist",
                tmp_path / "ledger",
                tmp_path / "python",
                tmp_path / "uv",
                context.binding.source_commit,
            )
    else:
        binding, record = alpha.build_alpha(
            tmp_path,
            tmp_path / "dist",
            tmp_path / "ledger",
            tmp_path / "python",
            tmp_path / "uv",
            context.binding.source_commit,
        )
        assert binding == context.binding
        assert record["node_version"] == "v22.14.0"
        assert record["npm_version"] == "10.9.2"


def test_alpha_cli_retains_path_free_row_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    alpha = importlib.import_module("scripts.release_qualification.alpha1_matrix")
    cli = importlib.import_module("scripts.qualify_release_package")
    context, *_rest = _inputs()
    monkeypatch.setattr(cli, "_alpha_context", lambda _args: context)

    def reject(*_args: Any, **_kwargs: Any) -> None:
        raise ValueError("/synthetic-not-for-publication/hidden-input")

    monkeypatch.setattr(alpha, "run_row", reject)
    args = SimpleNamespace(
        source_root=tmp_path,
        dist_dir=tmp_path / "dist",
        python=tmp_path / "python",
        build_python=tmp_path / "build-python",
        uv=tmp_path / "uv",
        minor="3.12",
        kind="sdist",
        work=tmp_path / "work",
        output=tmp_path / "results/sdist.json",
    )
    with pytest.raises(ValueError, match="hidden-input"):
        cli._alpha_row(args)
    raw = (tmp_path / "results/sdist-failure.json").read_bytes()
    record = json.loads(raw)
    assert record["status"] == "fail" and record["stage"] == "alpha-row"
    assert record["error_type"] == "ValueError"
    assert record["source_commit"] == context.binding.source_commit
    assert b"hidden-input" not in raw and b"synthetic-not-for-publication" not in raw
    assert not args.output.exists()


def test_alpha_dependency_expectation_excludes_project_and_installer() -> None:
    alpha = importlib.import_module("scripts.release_qualification.alpha1_matrix")
    context, rows, *_rest = _inputs()
    assert alpha._runtime_dependencies(context, rows[0]["runtime"]) == [
        {"name": "logseq-matryca-parser", "version": "1.9.0"}
    ]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "extra",
        "replay",
        "runtime",
        "platform",
        "cleanup",
        "installed",
        "resource",
        "tck",
        "mapped",
        "build-runtime",
        "original-sdist",
        "build-instance",
        "job-failed",
        "job-skipped",
        "source",
        "windows",
        "bool-attempt",
        "dependency",
    ],
)
def test_alpha_matrix_rejects_incomplete_or_self_asserted_evidence(mutation: str) -> None:
    context, rows, jobs, source, windows = _inputs()
    alpha = importlib.import_module("scripts.release_qualification.alpha1_matrix")
    if mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows[-1] = copy.deepcopy(rows[0])
    elif mutation == "extra":
        rows.append(copy.deepcopy(rows[0]))
    elif mutation == "replay":
        rows[0]["run_attempt"] = 1
    elif mutation == "runtime":
        rows[0]["runtime"]["version"] = "3.13.13"
    elif mutation == "platform":
        rows[0]["runtime"]["system"] = "macos"
    elif mutation == "cleanup":
        rows[0]["operational"]["cleanup"]["status"] = "uncertain"
    elif mutation == "installed":
        rows[0]["installed"]["tck_outcomes"] = []
    elif mutation == "resource":
        rows[0]["operational"]["resources"] = {}
    elif mutation == "tck":
        rows[0]["operational"]["checks"].pop()
    elif mutation == "mapped":
        rows[0]["operational"]["evidence_limits"]["source_unit_controls"]["status"] = "executed"
    elif mutation == "build-runtime":
        rows[1]["build"]["python_version"] = "3.13.13"
    elif mutation == "original-sdist":
        rows[1]["build"]["sdist_sha256"] = "0" * 64
    elif mutation == "build-instance":
        rows[3]["build"]["instance"] = rows[1]["build"]["instance"]
    elif mutation == "job-failed":
        jobs[0]["conclusion"] = "failure"
    elif mutation == "job-skipped":
        jobs[1]["conclusion"] = "skipped"
    elif mutation == "source":
        source["source_tree"] = "0" * 40
    elif mutation == "windows":
        windows["graph_accesses"] = 1
    elif mutation == "bool-attempt":
        rows[0]["run_attempt"] = True
    elif mutation == "dependency":
        rows[0]["installed"]["dependencies"][0]["version"] = "1.11.0"
    with pytest.raises(ValueError):
        alpha.verify_matrix(context, rows, jobs, source, windows)


@pytest.mark.parametrize("raw", [b'{"status":"pass","status":"fail"}', b'{"n":NaN}', b"[]", b""])
def test_alpha_json_boundary_rejects_duplicate_nonstandard_and_wrong_shapes(raw: bytes) -> None:
    alpha = importlib.import_module("scripts.release_qualification.alpha1_matrix")
    with pytest.raises(ValueError):
        alpha.document(raw)


def test_alpha_context_digest_is_type_sensitive() -> None:
    alpha = importlib.import_module("scripts.release_qualification.alpha1_matrix")
    assert alpha.digest({"value": True}) != alpha.digest({"value": 1})
    assert json.loads(alpha.canonical({"b": 2, "a": 1})) == {"a": 1, "b": 2}


def test_alpha_cli_is_explicit_without_relaxing_existing_commands() -> None:
    from scripts.qualify_release_package import _parser

    parser = _parser()
    for command in (
        "alpha-build",
        "alpha-row",
        "alpha-source-controls",
        "alpha-windows-refusal",
        "alpha-aggregate",
    ):
        # A known command with missing required arguments must name its arguments,
        # not be rejected as an unknown choice.
        action = next(
            item
            for item in parser._actions
            if hasattr(item, "choices") and isinstance(item.choices, dict)
        )
        assert isinstance(action.choices, dict)
        assert command in action.choices
    assert isinstance(action.choices, dict)
    assert "verify-receipts" in action.choices


@pytest.mark.parametrize(
    "mutation", [None, "digest", "id", "expired", "source", "missing", "duplicate", "attempt"]
)
def test_alpha_artifact_handoff_uses_independent_upstream_ids_and_digests(
    mutation: str | None,
) -> None:
    context, *_rest = _inputs()
    alpha = importlib.import_module("scripts.release_qualification.alpha1_matrix")
    expected = {
        name: {"id": str(index + 1), "sha256": "a" * 64}
        for index, name in enumerate(alpha.ARTIFACT_KEYS)
    }
    artifacts: list[dict[str, Any]] = [
        {
            "id": index + 1,
            "name": f"og-alpha-123-2-{name}",
            "digest": "sha256:" + "a" * 64,
            "expired": False,
            "workflow_run": {"id": 123, "head_sha": context.binding.source_commit},
        }
        for index, name in enumerate(alpha.ARTIFACT_KEYS)
    ]
    if mutation == "digest":
        artifacts[0]["digest"] = "sha256:" + "b" * 64
    elif mutation == "id":
        artifacts[0]["id"] = 100
    elif mutation == "expired":
        artifacts[0]["expired"] = True
    elif mutation == "source":
        artifacts[0]["workflow_run"]["head_sha"] = "0" * 40
    elif mutation == "missing":
        artifacts.pop()
    elif mutation == "duplicate":
        artifacts.append(copy.deepcopy(artifacts[0]))
    elif mutation == "attempt":
        artifacts[0]["name"] = artifacts[0]["name"].replace("-2-", "-1-")
    if mutation:
        with pytest.raises(ValueError):
            alpha.verify_artifacts(context, expected, artifacts)
    else:
        assert len(alpha.verify_artifacts(context, expected, artifacts)) == 7


@pytest.mark.parametrize(
    "kind,minor,failure,implementation",
    [
        ("wheel", "3.12", "", "CPython"),
        ("wheel", "3.13", "", "CPython"),
        ("sdist", "3.12", "", "CPython"),
        ("sdist", "3.13", "", "CPython"),
        ("wheel", "3.12", "operational", "CPython"),
        ("sdist", "3.12", "build", "CPython"),
        ("wheel", "3.12", "", "PyPy"),
    ],
)
def test_mocked_row_composition_preserves_original_artifact_and_runtime_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    minor: str,
    failure: str,
    implementation: str,
) -> None:
    alpha = importlib.import_module("scripts.release_qualification.alpha1_matrix")
    context, templates, *_rest = _inputs()
    template = next(row for row in templates if row["row"] == f"linux-x64-{minor}-{kind}")
    dist = tmp_path / "dist"
    dist.mkdir()
    for name in (context.binding.wheel_name, context.binding.sdist_name):
        (dist / name).write_bytes(b"synthetic original")
    runtime = tmp_path / "runtime/bin/python"
    build_python = tmp_path / "build/bin/python"
    uv = tmp_path / "uv"
    for path in (runtime, build_python, uv):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic executable")
    selected = alpha.LockedBuildEnvironment(
        build_python, uv, "a" * 64, "b" * 64, context.build_lock_sha256, context.build_packages
    )
    record = {
        "packages": [
            {"name": name, "version": version} for name, version in context.build_packages
        ],
        "target_os": "linux",
        "target_architecture": "x64",
        "uv_version": "0.12.19",
        "uv_sha256": selected.uv_sha256,
        "python_version": "3.12.13",
        "python_implementation": "CPython",
        "python_executable_sha256": selected.python_sha256,
        "build_lock_sha256": selected.lock_sha256,
    }
    calls: list[tuple[str, Any]] = []
    monkeypatch.setattr(
        alpha.bundle, "verify_handoff", lambda *_a, **kw: calls.append(("handoff", kw["policy"]))
    )
    monkeypatch.setattr(alpha.sdist_build, "_native_marker_target", lambda: ("linux", "x64"))
    monkeypatch.setattr(
        alpha.installed,
        "_selected_environment",
        lambda _p: (runtime.parent.parent, tmp_path / "site", minor + ".13", "linux", "x86_64"),
    )
    monkeypatch.setattr(
        alpha.installed,
        "_run_bounded",
        lambda *_a, **_kw: (0, (implementation + "\n").encode(), b""),
    )
    monkeypatch.setattr(alpha, "locked_build_selection", lambda *_a: (selected, record))
    temporary = b"synthetic temporary wheel"

    def prepare(original: Path, *_args: Any, **kwargs: Any) -> SimpleNamespace:
        assert original == dist / context.binding.sdist_name and kwargs["policy"] == "og-alpha2"
        if failure == "build":
            raise ValueError("Synthetic build failure")
        output = _args[-1] / context.binding.wheel_name
        output.write_bytes(temporary)
        value = copy.deepcopy(template["build"])
        for name in ("instance", "environment_descriptor", "provisioning_evidence"):
            value.pop(name)
        descriptor = alpha.read_document(kwargs["environment_descriptor"])
        value.update(
            environment_descriptor_sha256=kwargs["expected_build_environment_sha256"],
            provisioning_evidence_sha256=descriptor["provisioning_evidence_sha256"],
            wheel_size=len(temporary),
            wheel_sha256=alpha.hashlib.sha256(temporary).hexdigest(),
        )
        calls.append(("build", original))
        return SimpleNamespace(
            wheel_size=value["wheel_size"],
            wheel_sha256=value["wheel_sha256"],
            to_dict=lambda: value,
        )

    monkeypatch.setattr(alpha.sdist_build, "prepare_sdist_build", prepare)

    def verify(
        _python: Path,
        _binding: object,
        _source: Path,
        observed_kind: str,
        *,
        artifact: Path,
        policy: str,
    ) -> SimpleNamespace:
        assert _python == runtime and observed_kind == kind and policy == "og-alpha2"
        assert artifact == dist / (
            context.binding.wheel_name if kind == "wheel" else context.binding.sdist_name
        )
        return SimpleNamespace(
            operating_system="linux", architecture="x86_64", to_dict=lambda: template["installed"]
        )

    monkeypatch.setattr(alpha.installed, "verify_installed", verify)

    def run(command: list[str], **kwargs: Any) -> SimpleNamespace:
        if command[1:3] == ["pip", "install"]:
            assert "--no-deps" in command and "--offline" in command
            assert (
                command[-1] == str(dist / context.binding.wheel_name)
                if kind == "wheel"
                else command[-1].endswith("temporary-wheel/" + context.binding.wheel_name)
            )
            calls.append(("install", command[-1]))
            return SimpleNamespace(returncode=0, stdout=b"")
        assert command[:5] == [str(runtime), "-I", "-B", "-m", "matryca_plumber.graph_gateway.tck"]
        Path(command[-1]).write_bytes(alpha.canonical(template["operational"]) + b"\n")
        return SimpleNamespace(returncode=1 if failure == "operational" else 0, stdout=b"")

    monkeypatch.setattr(alpha.sdist_build, "_run_bounded", run)
    report = tmp_path / "results/operational.json"
    if failure or implementation != "CPython":
        message = (
            "measured CPython"
            if implementation != "CPython"
            else "Synthetic build failure"
            if failure == "build"
            else "operational TCK failed"
        )
        with pytest.raises(ValueError, match=message):
            alpha.run_row(
                context,
                tmp_path,
                dist,
                runtime,
                build_python,
                uv,
                minor,
                kind,
                tmp_path / "work",
                report,
            )
        if failure == "operational":
            assert report.is_file()
        elif failure == "build":
            assert (
                alpha.read_document(tmp_path / "results/build-environment.json")["source_commit"]
                == context.binding.source_commit
            )
            assert (
                alpha.read_document(tmp_path / "results/provisioning-evidence.json")["instance"]
                == "linux-x64-3.12-sdist"
            )
        else:
            assert not report.exists()
    else:
        result = alpha.run_row(
            context,
            tmp_path,
            dist,
            runtime,
            build_python,
            uv,
            minor,
            kind,
            tmp_path / "work",
            report,
        )
        assert result["runtime"]["version"].startswith(minor + ".")
        assert (result["build"] is not None) == (kind == "sdist")
        assert sum(name == "build" for name, _value in calls) == int(kind == "sdist")
