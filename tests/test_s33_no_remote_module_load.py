"""The shipped web extension never loads code from a remote host.

``web/preact-loader.js`` used to fall back to version-pinned ``esm.sh`` module URLs, without integrity
checks, when the shipped local copies failed to load: a remote code load inside the ComfyUI origin. The
vendored copies in ``web/lib/`` are the only source now; a failed load rejects and the island registry
renders the vanilla UI (covered by ``tests/e2e/specs/preact-loader.spec.js``).
"""
import re
from pathlib import Path

import pytest

WEB_ROOT = Path(__file__).resolve().parent.parent / "web"
REMOTE_MODULE_HOSTS = (
    "esm.sh",
    "esm.run",
    "cdn.jsdelivr.net",
    "unpkg.com",
    "cdnjs.cloudflare.com",
    "skypack.dev",
    "jspm.io",
)
HOST_PATTERN = re.compile(
    r"(?<![\w.-])(?:%s)(?![\w-])" % "|".join(re.escape(host) for host in REMOTE_MODULE_HOSTS),
    re.IGNORECASE,
)
REMOTE_IMPORT_PATTERN = re.compile(
    r"""(?:\bimport\s*\(\s*|\bimport\s+|\bfrom\s+|@import\s+(?:url\(\s*)?)[`'"]?https?://""",
    re.IGNORECASE,
)
SOURCE_SUFFIXES = {".js", ".mjs", ".css", ".html"}


def shipped_sources():
    # web/lib/ holds third-party vendored files that are not ours to scan (they may quote their own homepage).
    return [
        path
        for path in sorted(WEB_ROOT.rglob("*"))
        if path.suffix in SOURCE_SUFFIXES and path.is_file() and path.relative_to(WEB_ROOT).parts[0] != "lib"
    ]


def violations(text: str):
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        if HOST_PATTERN.search(line) or REMOTE_IMPORT_PATTERN.search(line):
            found.append((number, line.strip()[:120]))
    return found


def test_the_scan_covers_the_shipped_sources():
    names = {path.name for path in shipped_sources()}

    assert {"preact-loader.js", "doctor.js", "chat-island.js"} <= names
    assert len(names) >= 20
    assert "preact.module.js" not in names


@pytest.mark.parametrize(
    "line",
    [
        "const url = `https://esm.sh/preact@10.26.5`;",
        "await import('https://cdn.jsdelivr.net/npm/htm');",
        'import htm from "https://unpkg.com/htm";',
        "export { x } from 'https://example.org/x.js';",
        '@import url("https://fonts.example/x.css");',
        "// fallback: skypack.dev/preact",
    ],
)
def test_the_detector_catches_remote_module_loads(line):
    assert violations(line)


@pytest.mark.parametrize(
    "line",
    [
        "import { loadPreact } from './preact-loader.js';",
        "const module = await import(localPath);",
        "// Do not add a CDN fallback here.",
        "const docs = 'see https://example.org/docs for details';",
    ],
)
def test_the_detector_ignores_local_imports_and_prose(line):
    assert violations(line) == []


def test_no_shipped_source_names_a_remote_module_host():
    offenders = {}
    for path in shipped_sources():
        found = violations(path.read_text(encoding="utf-8", errors="replace"))
        if found:
            offenders[path.relative_to(WEB_ROOT).as_posix()] = found

    assert offenders == {}
