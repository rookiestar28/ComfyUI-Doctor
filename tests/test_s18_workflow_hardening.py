import re
from pathlib import Path


WORKFLOW_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def workflow_files():
    return sorted(path for path in WORKFLOW_DIR.glob("*.yml"))


def test_all_workflows_declare_permissions():
    missing = []
    for path in workflow_files():
        text = path.read_text(encoding="utf-8")
        if re.search(r"(?m)^permissions\s*:", text) is None:
            missing.append(path.name)

    assert missing == []


def test_workflows_do_not_use_privileged_pr_or_oidc_publish_boundary():
    offenders = []
    for path in workflow_files():
        text = path.read_text(encoding="utf-8")
        if "pull_request_target" in text or re.search(r"(?im)id-token\s*:\s*write", text):
            offenders.append(path.name)

    assert offenders == []


def test_third_party_actions_are_pinned_to_full_sha():
    offenders = []
    for path in workflow_files():
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"(?im)uses:\s*([^\s#]+)", text):
            ref = match.group(1)
            if ref.startswith("./") or "@" not in ref:
                continue
            action, action_ref = ref.rsplit("@", 1)
            if action.lower().startswith("actions/"):
                continue
            if not re.fullmatch(r"[a-f0-9]{40}", action_ref):
                offenders.append(f"{path.name}: {ref}")

    assert offenders == []


def test_publish_workflow_does_not_checkout_submodules():
    publish_workflow = WORKFLOW_DIR / "publish.yml"
    text = publish_workflow.read_text(encoding="utf-8")

    assert "submodules: true" not in text
