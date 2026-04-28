import pytest

from scripts.run_coverage_baseline import (
    build_coverage_command,
    parse_args,
    require_coverage_dependencies,
    required_coverage_dependency_modules,
)


def _requirements_dev_packages() -> set[str]:
    packages = set()
    for raw_line in open("requirements-dev.txt", encoding="utf-8"):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        package = line.split("==", 1)[0].split(">=", 1)[0].split("<", 1)[0].strip().lower()
        packages.add(package)
    return packages


def test_t18_coverage_command_defaults_to_baseline_reporting():
    command = build_coverage_command("python", xml_path="coverage.xml", fail_under=0)

    assert command == [
        "python",
        "-m",
        "pytest",
        "tests",
        "--cov=.",
        "--cov-report=term-missing:skip-covered",
        "--cov-fail-under=0",
        "--cov-report=xml:coverage.xml",
    ]


def test_t18_coverage_command_can_skip_xml_output():
    command = build_coverage_command("python", xml_path="", fail_under=0)

    assert "--cov-report=xml:coverage.xml" not in command
    assert command[-1] == "--cov-fail-under=0"


def test_t18_coverage_args_keep_zero_threshold_default():
    args = parse_args([])

    assert args.xml == "coverage.xml"
    assert args.fail_under == 0


def test_t18_requirements_dev_includes_coverage_collection_dependencies():
    packages = _requirements_dev_packages()

    assert {"aiohttp", "anyio", "numpy", "pillow"}.issubset(packages)


def test_t18_coverage_preflight_checks_collection_dependencies():
    modules = dict(required_coverage_dependency_modules())

    assert modules["pytest"] == "pytest"
    assert modules["pytest_cov"] == "pytest-cov"
    assert modules["aiohttp"] == "aiohttp"
    assert modules["anyio"] == "anyio"
    assert modules["numpy"] == "numpy"
    assert modules["PIL"] == "pillow"


def test_t18_coverage_preflight_reports_missing_collection_dependency(monkeypatch):
    def fake_find_spec(module_name):
        if module_name == "aiohttp":
            return None
        return object()

    monkeypatch.setattr("scripts.run_coverage_baseline.importlib.util.find_spec", fake_find_spec)

    with pytest.raises(RuntimeError) as exc_info:
        require_coverage_dependencies()

    message = str(exc_info.value)
    assert "aiohttp" in message
    assert "requirements-dev.txt" in message
