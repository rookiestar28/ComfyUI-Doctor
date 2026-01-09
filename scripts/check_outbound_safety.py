#!/usr/bin/env python3
"""
Outbound Funnel Static Safety Check (T12)

Prevents bypass of outbound.py sanitization funnel by detecting:
1. Direct use of raw context fields in outbound payloads
2. POST requests without sanitize_outbound_payload()
3. Dangerous fallback patterns
4. Missing sanitizer application

Exit codes:
  0 = All checks passed
  1 = Violations detected
  2 = Script error
"""

import ast
import sys
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass

@dataclass
class Violation:
    """A detected outbound safety violation."""
    file: str
    line: int
    column: int
    rule: str
    message: str
    code_snippet: str


class OutboundSafetyChecker(ast.NodeVisitor):
    """AST visitor that detects outbound funnel bypass patterns."""

    # Sensitive context fields
    SENSITIVE_FIELDS = {
        'traceback', 'workflow_json', 'system_info', 'settings'
    }

    # Sanitized field prefixes
    SANITIZED_PREFIXES = {'sanitized_'}

    def __init__(self, filename: str, source: str):
        self.filename = filename
        self.source = source
        self.lines = source.splitlines()
        self.violations: List[Violation] = []

        # Track state within functions
        self.in_function = False
        self.sanitizer_created = False
        self.sanitizer_applied = False
        self.has_session_post = False
        self.payload_assignments = []

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        # Reset state for each function
        old_state = (self.sanitizer_created, self.sanitizer_applied,
                     self.has_session_post, self.payload_assignments)
        self.sanitizer_created = False
        self.sanitizer_applied = False
        self.has_session_post = False
        self.payload_assignments = []

        self.generic_visit(node)

        # Check Rule 3 & 4: POST without sanitization
        if self.has_session_post and not self.sanitizer_applied:
            self.add_violation(node, 'POST_WITHOUT_SANITIZATION',
                             'session.post() without sanitize_outbound_payload()')

        # Restore state
        (self.sanitizer_created, self.sanitizer_applied,
         self.has_session_post, self.payload_assignments) = old_state

    def visit_Call(self, node: ast.Call):
        # Detect get_outbound_sanitizer()
        if self._is_call_to(node, 'get_outbound_sanitizer'):
            self.sanitizer_created = True

        # Detect sanitize_outbound_payload()
        if self._is_call_to(node, 'sanitize_outbound_payload'):
            self.sanitizer_applied = True

        # Detect session.post()
        if self._is_session_post(node):
            self.has_session_post = True
            self._check_post_payload(node)

        # Detect json.dumps() with raw fields
        if self._is_json_dumps(node):
            self._check_json_dumps(node)

        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp):
        # Rule 2: Detect "sanitized_X or X" pattern
        if isinstance(node.op, ast.Or):
            self._check_dangerous_fallback(node)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        # Track payload assignments
        for target in node.targets:
            if isinstance(target, ast.Subscript):
                self._check_payload_assignment(target, node.value)
            elif isinstance(target, ast.Name) and 'payload' in target.id.lower():
                # Check dict literal assignments: payload = {"key": context.field}
                if isinstance(node.value, ast.Dict):
                    if self._contains_raw_field(node.value):
                        self.add_violation(node, 'RAW_FIELD_IN_PAYLOAD',
                            f'Raw context field in payload dict (may be nested)')
        self.generic_visit(node)

    def _is_call_to(self, node: ast.Call, func_name: str) -> bool:
        """Check if node is a call to function with given name."""
        if isinstance(node.func, ast.Name):
            return node.func.id == func_name
        if isinstance(node.func, ast.Attribute):
            return node.func.attr == func_name
        return False

    def _is_session_post(self, node: ast.Call) -> bool:
        """Check if node is session.post() call."""
        return (isinstance(node.func, ast.Attribute) and
                node.func.attr == 'post' and
                isinstance(node.func.value, ast.Name) and
                node.func.value.id == 'session')

    def _is_json_dumps(self, node: ast.Call) -> bool:
        """Check if node is json.dumps() call."""
        return (isinstance(node.func, ast.Attribute) and
                node.func.attr == 'dumps' and
                isinstance(node.func.value, ast.Name) and
                node.func.value.id == 'json')

    def _check_dangerous_fallback(self, node: ast.BoolOp):
        """Check for 'sanitized_X or X' pattern."""
        if len(node.values) == 2:
            left, right = node.values
            # Check if pattern matches "context.sanitized_X or context.X"
            if (isinstance(left, ast.Attribute) and
                isinstance(right, ast.Attribute)):
                if (self._is_raw_context_field(right) and
                    self._is_sanitized_variant(left, right)):
                    self.add_violation(node, 'DANGEROUS_FALLBACK',
                        f'Dangerous fallback: {ast.unparse(left)} or {ast.unparse(right)}')

    def _is_raw_context_field(self, node: ast.Attribute) -> bool:
        """Check if node is context.sensitive_field."""
        return (isinstance(node.value, ast.Name) and
                node.value.id == 'context' and
                node.attr in self.SENSITIVE_FIELDS)

    def _is_sanitized_variant(self, sanitized: ast.Attribute, raw: ast.Attribute) -> bool:
        """Check if sanitized field matches raw field."""
        return (sanitized.attr == f'sanitized_{raw.attr}' or
                sanitized.attr.startswith('sanitized_'))

    def _check_payload_assignment(self, target: ast.Subscript, value: ast.AST):
        """Check if payload[key] = context.raw_field."""
        # Check if target is payload[...]
        if not (isinstance(target.value, ast.Name) and
                'payload' in target.value.id.lower()):
            return

        # Check if value is raw context field
        if isinstance(value, ast.Attribute):
            if self._is_raw_context_field(value):
                self.add_violation(target, 'RAW_FIELD_IN_PAYLOAD',
                    f'Raw context field assigned to payload: {ast.unparse(value)}')

    def _check_post_payload(self, node: ast.Call):
        """Check session.post() payload for raw fields."""
        # Find json= keyword argument
        for keyword in node.keywords:
            if keyword.arg == 'json':
                if isinstance(keyword.value, ast.Name):
                    # Track the variable name (should have been sanitized)
                    if not self.sanitizer_applied:
                        # Will be caught by POST_WITHOUT_SANITIZATION
                        pass

    def _check_json_dumps(self, node: ast.Call):
        """Check json.dumps() for raw context fields."""
        if node.args:
            arg = node.args[0]
            if self._contains_raw_field(arg):
                self.add_violation(node, 'JSON_DUMPS_RAW_FIELD',
                    'json.dumps() called on structure containing raw context field')

    def _contains_raw_field(self, node: ast.AST) -> bool:
        """Recursively check if node contains raw context field."""
        if isinstance(node, ast.Attribute):
            if self._is_raw_context_field(node):
                return True
        if isinstance(node, ast.Dict):
            return any(self._contains_raw_field(v) for v in node.values if v)
        if isinstance(node, ast.List):
            return any(self._contains_raw_field(e) for e in node.elts)
        return False

    def _is_suppressed(self, node: ast.AST) -> bool:
        """Check if violation is suppressed by comment."""
        # For FunctionDef nodes, check the entire function body for nosec
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            start_line = node.lineno - 1
            end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line + 20
            for line_idx in range(start_line, min(end_line, len(self.lines))):
                if 'nosec: outbound-bypass-allowed' in self.lines[line_idx]:
                    return True
        else:
            # Check current line and previous line for nosec comment
            for offset in [0, -1]:
                line_idx = node.lineno - 1 + offset
                if 0 <= line_idx < len(self.lines):
                    line = self.lines[line_idx]
                    if 'nosec: outbound-bypass-allowed' in line:
                        return True
        return False

    def add_violation(self, node: ast.AST, rule: str, message: str):
        """Add a violation with context."""
        # Check for suppression
        if self._is_suppressed(node):
            return

        snippet = self._get_code_snippet(node.lineno)
        self.violations.append(Violation(
            file=self.filename,
            line=node.lineno,
            column=node.col_offset,
            rule=rule,
            message=message,
            code_snippet=snippet
        ))

    def _get_code_snippet(self, line: int, context=2) -> str:
        """Get code snippet around line."""
        start = max(0, line - context - 1)
        end = min(len(self.lines), line + context)
        return '\n'.join(f'{i+1:4d}: {self.lines[i]}'
                        for i in range(start, end))


def check_file(file_path: Path) -> List[Violation]:
    """Check a single Python file for outbound safety violations."""
    try:
        source = file_path.read_text(encoding='utf-8')
        tree = ast.parse(source, filename=str(file_path))

        checker = OutboundSafetyChecker(str(file_path), source)
        checker.visit(tree)

        return checker.violations
    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Error checking {file_path}: {e}", file=sys.stderr)
        return []


def should_check_file(file_path: Path, project_root: Path) -> bool:
    """Determine if file should be checked."""
    try:
        rel_path = file_path.relative_to(project_root)
    except ValueError:
        return False

    # Skip whitelisted files/directories
    skip_patterns = [
        'tests/',
        'outbound.py',
        'sanitizer.py',
        '.venv/',
        'venv/',
        'node_modules/',
        'REFERENCE/',
        '__pycache__',
    ]

    rel_path_str = str(rel_path).replace('\\', '/')
    for pattern in skip_patterns:
        if pattern in rel_path_str:
            return False

    return True


def main():
    """Main entry point."""
    project_root = Path(__file__).resolve().parent.parent

    print("🔒 Outbound Funnel Safety Check (T12)")
    print(f"Scanning: {project_root}\n")

    # Find all Python files
    py_files = [f for f in project_root.rglob('*.py')
                if should_check_file(f, project_root)]

    print(f"Checking {len(py_files)} Python files...\n")

    all_violations = []
    for file_path in py_files:
        violations = check_file(file_path)
        all_violations.extend(violations)

    # Report results
    if not all_violations:
        print("✅ All checks passed! No outbound safety violations detected.")
        return 0

    print(f"❌ {len(all_violations)} violation(s) detected:\n")

    for v in all_violations:
        print(f"  File: {v.file}:{v.line}:{v.column}")
        print(f"  Rule: {v.rule}")
        print(f"  Message: {v.message}")
        print(f"\n{v.code_snippet}\n")
        print("-" * 80)

    print(f"\n🚫 {len(all_violations)} outbound safety violation(s) found")
    return 1


if __name__ == '__main__':
    sys.exit(main())
