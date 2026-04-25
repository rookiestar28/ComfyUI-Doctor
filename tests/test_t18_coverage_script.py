from scripts.run_coverage_baseline import build_coverage_command, parse_args


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
