from helixsh.doctor import CheckResult, run_check


def test_run_check_handles_missing_binary():
    result = run_check("missing", ["definitely-not-a-real-binary", "--version"])
    assert result == CheckResult(name="missing", state="missing", details="binary not found")
