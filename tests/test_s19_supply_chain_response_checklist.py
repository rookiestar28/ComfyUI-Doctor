import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_supply_chain.py"
SPEC = importlib.util.spec_from_file_location("check_supply_chain_s19", SCRIPT_PATH)
check_supply_chain = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = check_supply_chain
SPEC.loader.exec_module(check_supply_chain)


def test_triage_checklist_covers_local_ci_registry_and_evidence(capsys):
    exit_code = check_supply_chain.main(["--print-triage-checklist"])
    output = capsys.readouterr().out.lower()

    assert exit_code == 0
    assert "stop activity" in output
    assert "evidence capture" in output
    assert "ci finding" in output
    assert "registry finding" in output
    assert "rotate credentials" in output
    assert "full repository validation gate" in output


def test_triage_checklist_does_not_print_secret_like_or_private_fixture_values(capsys):
    check_supply_chain.main(["--print-triage-checklist"])
    output = capsys.readouterr().out

    forbidden = [
        "ghp" + "_",
        "xoxb" + "-",
        "sk" + "-",
        "C:\\Users\\Ray",
        "REGISTRY_ACCESS" + "_TOKEN=",
    ]

    for value in forbidden:
        assert value not in output
