"""The installed package imports and reports its version; the legacy oracle stays independent."""
import ast
import importlib.metadata
from pathlib import Path

import analog_omni


def test_package_imports_and_reports_version():
    assert analog_omni.__version__ == "0.0.1"
    assert analog_omni.__version__ == importlib.metadata.version("analog-omni")


def test_legacy_oracle_never_imports_production_code():
    tree = ast.parse((Path(__file__).parent / "test_legacy_fixtures.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", "")) in (
            "import_module",
            "__import__",
        ):
            imported.add("<dynamic import>")
    assert "analog_omni" not in imported
    assert "<dynamic import>" not in imported
