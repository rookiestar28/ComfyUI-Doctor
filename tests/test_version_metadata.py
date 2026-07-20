import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read_pyproject_version() -> str:
    text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"\s*$', text)
    assert match, "pyproject.toml must define [project] version"
    return match.group(1)


def _read_json(path: str) -> dict:
    return json.loads((PROJECT_ROOT / path).read_text(encoding="utf-8"))


def _read_workflow_event_paths(workflow_path: str, event: str) -> set[str]:
    lines = (PROJECT_ROOT / workflow_path).read_text(encoding="utf-8").splitlines()
    event_marker = f"  {event}:"
    event_started = False
    paths_started = False
    paths: set[str] = set()

    for line in lines:
        stripped = line.strip()
        indentation = len(line) - len(line.lstrip())

        if line == event_marker:
            event_started = True
            continue
        if not event_started:
            continue
        if stripped and indentation <= 2:
            break
        if indentation == 4 and stripped == "paths:":
            paths_started = True
            continue
        if paths_started and stripped:
            if indentation <= 4:
                break
            if indentation == 6 and stripped.startswith("- "):
                paths.add(stripped.removeprefix("- ").strip("'\""))

    assert event_started, f"{workflow_path} must define the {event} event"
    assert paths_started, f"{workflow_path} {event} event must define path filters"
    return paths


def _assert_semver(version: str, source: str) -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), f"{source} version must use MAJOR.MINOR.PATCH"


def test_release_version_metadata_matches_pyproject():
    canonical_version = _read_pyproject_version()
    package_json = _read_json("package.json")
    package_lock = _read_json("package-lock.json")

    _assert_semver(canonical_version, "pyproject.toml")
    _assert_semver(package_json["version"], "package.json")

    assert package_json["version"] == canonical_version
    assert package_json.get("private") is True
    assert package_lock["version"] == canonical_version
    assert package_lock["packages"][""]["version"] == canonical_version


def test_coverage_workflow_runs_for_all_release_metadata_changes():
    required_paths = {"pyproject.toml", "package.json", "package-lock.json"}

    for event in ("push", "pull_request"):
        actual_paths = _read_workflow_event_paths(".github/workflows/coverage-baseline.yml", event)
        assert required_paths <= actual_paths, (
            f"Coverage Baseline {event}.paths must include every release metadata file; "
            f"missing {sorted(required_paths - actual_paths)}"
        )


def test_public_package_metadata_has_no_internal_markers():
    package_json = _read_json("package.json")
    public_values = [
        package_json.get("name", ""),
        package_json.get("version", ""),
        package_json.get("description", ""),
        " ".join(package_json.get("keywords", [])),
    ]
    public_text = "\n".join(str(value) for value in public_values)

    forbidden_markers = [".planning", "ROADMAP", "reference/docs", "R35", "T24", "R33", "R34"]
    for marker in forbidden_markers:
        assert marker not in public_text
