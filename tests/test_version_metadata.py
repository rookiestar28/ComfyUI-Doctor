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
