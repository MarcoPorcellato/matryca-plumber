"""Keep the operator error table aligned with the source without importing a producer."""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "docs/contracts/og-graph-gateway-alpha3.md"
BOOTSTRAP = ROOT / "matryca_plumber/graph_gateway/bootstrap.py"


class GatewayInvocationDocumentationTests(unittest.TestCase):
    def test_documented_error_pairs_match_source(self) -> None:
        """A new, removed, changed or duplicated error must not leave stale operator guidance."""
        self.assertTrue(REFERENCE.is_file(), "gateway invocation reference is missing")
        tree = ast.parse(BOOTSTRAP.read_text(encoding="utf-8"))
        assignments = [
            node
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ERROR_EXITS"
        ]
        self.assertEqual(len(assignments), 1)
        value = assignments[0].value
        assert value is not None
        source = ast.literal_eval(value)
        self.assertIsInstance(source, dict)
        pairs = re.findall(
            r"^\| `([a-z_]+)` \| `(\d+)` \|",
            REFERENCE.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        )
        documented = {code: int(status) for code, status in pairs}
        self.assertEqual(len(pairs), len(documented), "duplicate documented error code")
        self.assertEqual(len(pairs), len({status for _, status in pairs}))
        self.assertEqual(documented, source)


if __name__ == "__main__":
    unittest.main()
