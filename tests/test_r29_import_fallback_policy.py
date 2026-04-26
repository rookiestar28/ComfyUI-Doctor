import ast
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRODUCT_ROOTS = [PROJECT_ROOT, PROJECT_ROOT / "services", PROJECT_ROOT / "pipeline"]
SKIP_DIRS = {"__pycache__", "plugins"}
SKIP_FILES = {"__init__.py", "prestartup_script.py", "verify_routes.py"}
GUARD_CALL = "ensure_absolute_import_fallback_allowed"


def _iter_product_files():
    seen = set()
    for root in PRODUCT_ROOTS:
        for path in sorted(root.rglob("*.py") if root != PROJECT_ROOT else root.glob("*.py")):
            if path in seen:
                continue
            seen.add(path)
            if path.name in SKIP_FILES:
                continue
            if any(part in SKIP_DIRS for part in path.relative_to(PROJECT_ROOT).parts):
                continue
            yield path


def _handler_calls_guard(handler: ast.ExceptHandler) -> bool:
    for node in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == GUARD_CALL:
                return True
            if isinstance(func, ast.Attribute) and func.attr == GUARD_CALL:
                return True
    return False


def _handler_imports_absolute_fallback(handler: ast.ExceptHandler) -> bool:
    return any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(ast.Module(body=handler.body, type_ignores=[])))


def _try_has_relative_import(node: ast.Try) -> bool:
    return any(isinstance(child, ast.ImportFrom) and child.level > 0 for child in ast.walk(ast.Module(body=node.body, type_ignores=[])))


def _try_handles_optional_top_level_module(node: ast.Try) -> bool:
    return any(
        isinstance(child, ast.Import) and any(alias.name == "server" for alias in child.names)
        for child in ast.walk(ast.Module(body=node.body, type_ignores=[]))
    )


def _is_import_error_handler(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return False
    if isinstance(handler.type, ast.Name):
        return handler.type.id == "ImportError"
    if isinstance(handler.type, ast.Tuple):
        return any(isinstance(elt, ast.Name) and elt.id == "ImportError" for elt in handler.type.elts)
    return False


def test_relative_first_import_fallbacks_are_guarded():
    offenders = []
    for path in _iter_product_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try) or not _try_has_relative_import(node) or _try_handles_optional_top_level_module(node):
                continue
            for handler in node.handlers:
                if (
                    _is_import_error_handler(handler)
                    and _handler_imports_absolute_fallback(handler)
                    and not _handler_calls_guard(handler)
                ):
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{handler.lineno}")

    assert offenders == []


def test_import_fallback_guard_allows_only_standalone_relative_import_context():
    from import_compat import ensure_absolute_import_fallback_allowed

    ensure_absolute_import_fallback_allowed(
        ImportError("attempted relative import with no known parent package")
    )

    with pytest.raises(ImportError, match="No module named 'missing_internal'"):
        ensure_absolute_import_fallback_allowed(
            ImportError("No module named 'missing_internal'")
        )
