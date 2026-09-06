"""Setuptools hook that packages Plumber's public static contract resources."""

from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _BuildPy

_ROOT = Path(__file__).resolve().parent
_CONTRACT_DIRECTORIES = (
    "plumber.consumer.package/v1",
    "plumber.graph.read/v1",
    "plumber.graph.topology/v1",
)
_TCK_SCRIPTS = (
    "run_plumber_consumer_package_v1_tck.py",
    "run_plumber_graph_read_v1_tck.py",
    "run_plumber_graph_topology_v1_tck.py",
)


class _BuildPublicContractResources(_BuildPy):
    """Copy canonical static contracts beside the installed package resources."""

    def run(self) -> None:
        super().run()
        resource_root = Path(self.build_lib) / "src" / "contract_artifacts"
        contracts_root = resource_root / "contracts"
        for contract_directory in _CONTRACT_DIRECTORIES:
            shutil.copytree(
                _ROOT / "contracts" / contract_directory,
                contracts_root / contract_directory,
                dirs_exist_ok=True,
            )
        tck_root = resource_root / "tck"
        tck_root.mkdir(parents=True, exist_ok=True)
        for script_name in _TCK_SCRIPTS:
            shutil.copy2(_ROOT / "scripts" / script_name, tck_root / script_name)


setup(cmdclass={"build_py": _BuildPublicContractResources})
