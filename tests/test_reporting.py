import json

from helixsh.reporting import build_validation_report, write_report


def test_report_warn_when_container_policy_fails(tmp_path):
    report = build_validation_report(schema_ok=True, container_policy_ok=False, cache_percent=83, diagnostics="oom handled")
    assert report.status == "warn"
    out = tmp_path / "report.json"
    write_report(report, str(out))
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "warn"
