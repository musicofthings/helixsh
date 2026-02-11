from helixsh.diagnostics import diagnose_failure


def test_diagnose_oom_exit_137():
    d = diagnose_failure("QUANTIFY", 137, memory_limit_gb=4)
    assert d.likely_cause == "Out-of-memory"
    assert "node limit 4 GB" in d.context


def test_diagnose_success():
    d = diagnose_failure("ANY", 0)
    assert d.likely_cause == "No failure"
