import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR_PATH = PROJECT_ROOT / "scripts" / "validate_host_load.py"

_spec = importlib.util.spec_from_file_location("doctor_validate_host_load", VALIDATOR_PATH)
validate_host_load = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(validate_host_load)


def test_current_repo_passes_host_load_validator_checks():
    assert validate_host_load.check_package_imports(PROJECT_ROOT) == []
    assert validate_host_load.check_prestartup_bootstrap(PROJECT_ROOT) == []
    assert validate_host_load.check_import_policy(PROJECT_ROOT) == []


def test_import_policy_flags_bare_absolute_internal_import(tmp_path):
    (tmp_path / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "logger.py").write_text(
        "from services.time_utils import utc_now\n",
        encoding="utf-8",
    )
    services_dir = tmp_path / "services"
    services_dir.mkdir()
    (services_dir / "__init__.py").write_text("", encoding="utf-8")
    (services_dir / "time_utils.py").write_text(
        "def utc_now():\n    return 'ok'\n",
        encoding="utf-8",
    )

    issues = validate_host_load.check_import_policy(tmp_path)

    assert issues
    assert "logger.py:1" in issues[0]
    assert "services.time_utils" in issues[0]


def test_package_import_check_flags_bare_internal_import_fixture(tmp_path):
    (tmp_path / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "logger.py").write_text(
        "from services.time_utils import utc_now\nvalue = utc_now()\n",
        encoding="utf-8",
    )
    services_dir = tmp_path / "services"
    services_dir.mkdir()
    (services_dir / "__init__.py").write_text("", encoding="utf-8")
    (services_dir / "time_utils.py").write_text(
        "def utc_now():\n    return 'ok'\n",
        encoding="utf-8",
    )

    issues = validate_host_load.check_package_imports(tmp_path, modules=["logger"])

    assert issues
    assert "logger:" in issues[0]
    assert ("Blocked host-like internal import: services" in issues[0] or "No module named 'services'" in issues[0])


def test_prestartup_bootstrap_check_flags_non_ascii_console_write(tmp_path):
    (tmp_path / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "prestartup_script.py").write_text(
        'print("🏥 startup")\n',
        encoding="utf-8",
    )

    issues = validate_host_load.check_prestartup_bootstrap(tmp_path)

    assert issues
    assert any("UnicodeEncodeError" in issue for issue in issues)
