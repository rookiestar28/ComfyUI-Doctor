"""Every export of the shipped web sources is used somewhere.

Eleven exports had no reference outside their own definition (a markdown helper, selector and subscription
helpers, island registry accessors, loader and key-store status flags, an intent stage formatter). Dead
exports invite a second, untested code path (the unused ``renderMarkdown`` was a second caller of the
sanitizer), so the shipped sources must not grow new ones.

The check is a deliberate lower bound: an export counts as used when its name appears anywhere in the shipped
sources or the tests besides its own definition line, so a mention in a comment also keeps it. That keeps the
guard free of false failures while still catching the real case (a name that occurs exactly once).
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = ROOT / "web"
THIS_FILE = Path(__file__).resolve()
REMOVED_EXPORTS = (
    "renderMarkdown",
    "getSelectedNodes",
    "getSessionId",
    "onProcessingChanged",
    "onWorkflowContextChanged",
    "getConfig",
    "isRegistered",
    "clearErrors",
    "isLegacyApiKeyMigrated",
    "isPreactLoaded",
    "formatIntentStage",
)
EXPORT_DECLARATION = re.compile(r"^export\s+(?:async\s+)?(?:function\*?|const|let|var|class)\s+([A-Za-z_$][\w$]*)", re.MULTILINE)
EXPORT_LIST = re.compile(r"^export\s*\{([^}]*)\}", re.MULTILINE)
CORPUS_SUFFIXES = {".js", ".mjs", ".html", ".py"}


def own_sources():
    return [
        path
        for path in sorted(WEB_ROOT.rglob("*.js"))
        if path.relative_to(WEB_ROOT).parts[0] != "lib"
    ]


def corpus_texts():
    paths = list(own_sources()) + [
        path
        for path in sorted((ROOT / "tests").rglob("*"))
        if path.suffix in CORPUS_SUFFIXES
        and path.is_file()
        and path.resolve() != THIS_FILE
        and "node_modules" not in path.parts
        and "test-results" not in path.parts
    ]
    return [path.read_text(encoding="utf-8", errors="replace") for path in paths]


def exported_names(text: str):
    names = set(EXPORT_DECLARATION.findall(text))
    for group in EXPORT_LIST.findall(text):
        for part in group.split(","):
            part = part.strip()
            if part:
                names.add(part.split(" as ")[-1].strip())
    return names


def occurrences(name: str, texts) -> int:
    pattern = re.compile(r"(?<![\w$])" + re.escape(name) + r"(?![\w$])")
    return sum(len(pattern.findall(text)) for text in texts)


def test_the_guard_sees_the_exports_and_the_corpus():
    texts = corpus_texts()
    exports = {name for path in own_sources() for name in exported_names(path.read_text(encoding="utf-8", errors="replace"))}

    assert len(own_sources()) >= 30
    assert {"loadPreact", "sanitizeHtml", "getUIText"} <= exports
    assert len(exports) >= 100
    assert occurrences("loadPreact", texts) > 1


@pytest.mark.parametrize("name", REMOVED_EXPORTS)
def test_a_removed_dead_export_stays_removed(name):
    assert occurrences(name, [path.read_text(encoding="utf-8", errors="replace") for path in own_sources()]) == 0


def test_every_export_is_used_outside_its_own_definition():
    texts = corpus_texts()
    unused = {}
    for path in own_sources():
        for name in sorted(exported_names(path.read_text(encoding="utf-8", errors="replace"))):
            if occurrences(name, texts) <= 1:
                unused.setdefault(path.relative_to(WEB_ROOT).as_posix(), []).append(name)

    assert unused == {}


def test_the_detector_counts_a_name_that_occurs_once_as_unused():
    assert occurrences("lonelyName", ["export function lonelyName() {}"]) == 1
    assert occurrences("lonelyName", ["export function lonelyName() {}", "lonelyName();"]) == 2
    assert occurrences("lonelyName", ["const lonelyNameTwo = 1;"]) == 0
    assert exported_names("export { a, b as c };\nexport async function d() {}\nexport const e = 1;") == {"a", "c", "d", "e"}
