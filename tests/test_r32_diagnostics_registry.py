def test_diagnostics_registry_contains_only_concrete_production_checks():
    from services.diagnostics.checks import get_registered_checks, init_checks
    from services.diagnostics.runner import get_diagnostics_runner

    init_checks()

    registered = get_registered_checks()
    expected = {
        "workflow_lint",
        "env_deps",
        "model_assets",
        "privacy_security",
        "runtime_performance",
        "signature_packs",
    }

    assert expected.issubset(set(registered))
    assert "placeholder" not in registered

    runner = get_diagnostics_runner()
    assert expected.issubset(set(runner._check_names))
    assert "placeholder" not in runner._check_names
