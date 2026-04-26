All tests must follow `tests/TEST_SOP.md` first.
E2E is the final stage of the repo-local acceptance gate; do not treat it as a substitute for detect-secrets, pre-commit, host-like package/startup validation, or backend unit tests.
When you reach the E2E stage, use the standard procedure defined in `tests/E2E_TESTING_SOP.md`.


Mandatory testing-design rule:

- E2E tests must be designed to reproduce real user-visible failures and catch bugs early, not merely to pass validation.
- Do not add pass-only E2E checks that cannot fail for the bug class under review.
- For every user-reported or high-risk frontend regression, ask which E2E assertion would have caught it before release, then add or update that assertion.
<!-- ROOKIEUI-GLOBAL-E2E-NOTICE:START -->
## RookieUI-Derived Global E2E Notice

All E2E tests must follow `tests/E2E_TESTING_SOP.md`. Full acceptance workflow and gate order remain defined by `tests/TEST_SOP.md`.

Mandatory testing-design rule:

- E2E tests must be designed to reproduce real user-visible failures and catch bugs early, not merely to pass validation.
- Do not add pass-only E2E checks that cannot fail for the bug class under review.
- For every user-reported or high-risk frontend regression, ask which E2E assertion would have caught it before release, then add or update that assertion.

Exception:

- strictly documentation-only changes do not require entering the E2E workflow
- once code/tests/scripts/config/runtime files change, this exception does not apply

For transaction-sensitive features, acceptance evidence must include at least one action-level assertion of final outcome, not route-load evidence only.
<!-- ROOKIEUI-GLOBAL-E2E-NOTICE:END -->
