#!/usr/bin/env python3
"""
Outbound Funnel Static Safety Check

Prevents bypass of outbound.py sanitization funnel by detecting:
1. Direct use of raw context fields in outbound payloads
2. POST requests without sanitize_outbound_payload()
3. Dangerous fallback patterns
4. Missing sanitizer application
5. aiohttp.ClientSession()/TCPConnector() created outside the destination-policy session modules
   (import aliases and qualified names included)
6. HTTP client calls that do not pass allow_redirects=False
7. session_manager.py sessions without a connector, or connectors without the policy resolver
8. Raw HTTP client imports (requests, httpx, urllib3, urllib.request, http.client)

Policy rules (5-8) and unreadable/unparseable files cannot be suppressed with the nosec marker;
they fail closed.

Exit codes:
  0 = All checks passed
  1 = Violations detected
  2 = Script error
"""

import ast
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
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

    # Only these modules (exact repository paths) may construct HTTP client sessions:
    # session_manager.py installs the destination-policy resolver; community_feedback.py talks to
    # the operator-configured GitHub API.
    SESSION_FACTORY_FILES = frozenset({'session_manager.py', 'services/community_feedback.py'})
    POLICY_SESSION_FILE = 'session_manager.py'
    CLIENT_CONSTRUCTORS = frozenset({'ClientSession', 'TCPConnector'})
    HTTP_METHODS = {'get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'request'}
    RAW_HTTP_CLIENT_MODULES = frozenset({'requests', 'httpx', 'urllib3', 'urllib.request', 'http.client'})
    # CRITICAL: destination-policy rules are never suppressible by the sanitization-funnel nosec
    # marker; a new outbound client must be added to the allowlist above in a reviewed change.
    POLICY_RULES = frozenset({
        'CLIENT_SESSION_OUTSIDE_POLICY',
        'REDIRECT_NOT_DISABLED',
        'CONNECTOR_WITHOUT_POLICY_RESOLVER',
        'SESSION_WITHOUT_POLICY_CONNECTOR',
        'RAW_HTTP_CLIENT_IMPORT',
    })

    def __init__(self, filename: str, source: str, relative_path: Optional[str] = None):
        self.filename = filename
        self.relative_path = relative_path
        self.source = source
        self.lines = source.splitlines()
        self.violations: List[Violation] = []
        self.module_aliases = {'aiohttp'}
        self.constructor_aliases: Dict[str, str] = {}
        self.request_aliases: set = set()

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

        # Rule 5: HTTP client sessions/connectors only in the policy/session modules
        constructor = self._client_constructor(node)
        if constructor and not self._is_session_factory_file():
            self.add_violation(node, 'CLIENT_SESSION_OUTSIDE_POLICY',
                f'aiohttp.{constructor}() outside session_manager.py bypasses the destination policy')

        # Rule 7: the policy factory must wire the destination-policy resolver into every session
        if constructor and self.relative_path == self.POLICY_SESSION_FILE:
            if constructor == 'TCPConnector' and not self._has_value_keyword(node, 'resolver'):
                self.add_violation(node, 'CONNECTOR_WITHOUT_POLICY_RESOLVER',
                    'TCPConnector() in session_manager.py must pass the destination policy resolver')
            if constructor == 'ClientSession' and not self._has_value_keyword(node, 'connector'):
                self.add_violation(node, 'SESSION_WITHOUT_POLICY_CONNECTOR',
                    'ClientSession() in session_manager.py must use a policy connector')

        # Rule 6: every HTTP client call must disable redirects explicitly
        if self._is_http_client_call(node) and not self._disables_redirects(node):
            self.add_violation(node, 'REDIRECT_NOT_DISABLED',
                f'{ast.unparse(node.func)}() without allow_redirects=False')

        self.generic_visit(node)

    def collect_imports(self, tree: ast.AST) -> None:
        """Pre-pass: record aiohttp aliases and flag raw HTTP client imports (rule 8)."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == 'aiohttp' or alias.name.startswith('aiohttp.'):
                        self.module_aliases.add(alias.asname or alias.name.split('.')[0])
                    if self._is_raw_http_module(alias.name):
                        self.add_violation(node, 'RAW_HTTP_CLIENT_IMPORT',
                            f'import {alias.name}: use the policy session from session_manager.py')
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    local = alias.asname or alias.name
                    if module == 'aiohttp' or module.startswith('aiohttp.'):
                        if alias.name in self.CLIENT_CONSTRUCTORS:
                            self.constructor_aliases[local] = alias.name
                        elif alias.name == 'request':
                            self.request_aliases.add(local)
                    if self._is_raw_http_module(module) or self._is_raw_http_module(f'{module}.{alias.name}'):
                        self.add_violation(node, 'RAW_HTTP_CLIENT_IMPORT',
                            f'from {module} import {alias.name}: use the policy session from session_manager.py')

    def _is_raw_http_module(self, name: str) -> bool:
        return any(name == module or name.startswith(module + '.') for module in self.RAW_HTTP_CLIENT_MODULES)

    def _client_constructor(self, node: ast.Call) -> Optional[str]:
        func = node.func
        if isinstance(func, ast.Name):
            if func.id in self.CLIENT_CONSTRUCTORS:
                return func.id
            return self.constructor_aliases.get(func.id)
        if isinstance(func, ast.Attribute) and func.attr in self.CLIENT_CONSTRUCTORS:
            return func.attr
        return None

    @staticmethod
    def _has_value_keyword(node: ast.Call, name: str) -> bool:
        return any(keyword.arg == name and not isinstance(keyword.value, ast.Constant)
                   for keyword in node.keywords)

    def _is_session_factory_file(self) -> bool:
        return self.relative_path in self.SESSION_FACTORY_FILES

    def _is_http_client_call(self, node: ast.Call) -> bool:
        """session.get/post/.../request(...) on a session-like receiver, or aiohttp.request(...)."""
        func = node.func
        if isinstance(func, ast.Name):
            return func.id in self.request_aliases
        if not isinstance(func, ast.Attribute) or func.attr not in self.HTTP_METHODS:
            return False
        receiver = func.value
        if isinstance(receiver, ast.Name):
            return receiver.id in self.module_aliases or receiver.id.lower().endswith('session')
        if isinstance(receiver, ast.Attribute):
            return receiver.attr.lower().endswith('session')
        return False

    @staticmethod
    def _disables_redirects(node: ast.Call) -> bool:
        for keyword in node.keywords:
            if keyword.arg == 'allow_redirects':
                return isinstance(keyword.value, ast.Constant) and keyword.value.value is False
        return False

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
        # Check for suppression (never for destination-policy rules)
        if rule not in self.POLICY_RULES and self._is_suppressed(node):
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


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Skipped by whole path segment or exact repository path (substring matching skipped unrelated
# files such as "latests/x.py" or "evil_outbound.py").
SKIP_DIRECTORIES = frozenset({
    'tests', 'reference', 'REFERENCE', '.reference', '.planning', '.tmp', '.venv', 'venv',
    'node_modules', '__pycache__',
})
SKIP_PATH_PREFIXES = ('docs/reference/',)
# The sanitization funnel itself legitimately handles raw context fields.
SKIP_FILES = frozenset({'outbound.py', 'sanitizer.py', 'pipeline/stages/sanitizer.py'})


def _relative_posix(file_path: Path, project_root: Path) -> Optional[str]:
    try:
        return file_path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return None


def _fail_closed(file_path: Path, rule: str, message: str) -> List[Violation]:
    print(f"{message} in {file_path}", file=sys.stderr)
    return [Violation(file=str(file_path), line=0, column=0, rule=rule, message=message, code_snippet='')]


def check_file(file_path: Path, project_root: Optional[Path] = None) -> List[Violation]:
    """Check a single Python file for outbound safety violations (fails closed on errors)."""
    root = project_root if project_root is not None else PROJECT_ROOT
    try:
        source = file_path.read_text(encoding='utf-8')
        tree = ast.parse(source, filename=str(file_path))
    except (OSError, UnicodeDecodeError, SyntaxError, ValueError) as e:
        return _fail_closed(file_path, 'PARSE_ERROR', f'Cannot read or parse file: {type(e).__name__}')

    try:
        checker = OutboundSafetyChecker(str(file_path), source, _relative_posix(file_path, root))
        checker.collect_imports(tree)
        checker.visit(tree)
        return checker.violations
    except Exception as e:  # checker bug: never pass silently
        return _fail_closed(file_path, 'CHECKER_ERROR', f'Checker failed: {type(e).__name__}')


def should_check_file(file_path: Path, project_root: Path) -> bool:
    """Determine if file should be checked."""
    rel_path = _relative_posix(file_path, project_root)
    if rel_path is None:
        return False
    parts = rel_path.split('/')
    if any(part in SKIP_DIRECTORIES for part in parts[:-1]):
        return False
    if rel_path in SKIP_FILES or rel_path.startswith(SKIP_PATH_PREFIXES):
        return False
    return True


def _candidate_files(project_root: Path) -> List[Path]:
    """Return git-tracked *.py files, falling back to a filesystem walk outside a git checkout."""
    try:
        output = subprocess.run(
            ['git', '-C', str(project_root), 'ls-files', '--', '*.py'],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout
        tracked = [project_root / line for line in output.splitlines() if line.strip()]
        if tracked:
            return [path for path in tracked if path.is_file()]
    except (OSError, subprocess.SubprocessError):
        pass
    return list(project_root.rglob('*.py'))


def main():
    """Main entry point."""
    project_root = PROJECT_ROOT

    print("Outbound Funnel Safety Check")
    print(f"Scanning: {project_root}\n")

    # Find tracked Python files (untracked reference checkouts are not product code)
    py_files = [f for f in _candidate_files(project_root)
                if should_check_file(f, project_root)]

    print(f"Checking {len(py_files)} Python files...\n")

    all_violations = []
    for file_path in py_files:
        violations = check_file(file_path, project_root)
        all_violations.extend(violations)

    # Report results
    if not all_violations:
        print("PASS All checks passed! No outbound safety violations detected.")
        return 0

    print(f"FAIL {len(all_violations)} violation(s) detected:\n")

    for v in all_violations:
        print(f"  File: {v.file}:{v.line}:{v.column}")
        print(f"  Rule: {v.rule}")
        print(f"  Message: {v.message}")
        print(f"\n{v.code_snippet}\n")
        print("-" * 80)

    print(f"\nABORT: {len(all_violations)} outbound safety violation(s) found")
    return 1


if __name__ == '__main__':
    sys.exit(main())
