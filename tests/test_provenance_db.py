from helixsh.provenance_db import (
    add_audit_event,
    create_execution,
    finish_execution,
    get_execution_bundle,
    init_db,
)


def test_sqlite_provenance_lifecycle(tmp_path):
    db = tmp_path / "helixsh.sqlite"
    init_db(str(db))

    create_execution(
        str(db),
        execution_id="e1",
        command="nextflow run nf-core/rnaseq",
        workflow="nf-core/rnaseq",
        agent="claude",
        model="opus",
        status="running",
        start_time="2026-01-01T00:00:00Z",
        container_digest="sha256:abc",
        input_hash="hash",
    )
    add_audit_event(str(db), execution_id="e1", event_type="execution_started", message="started")
    finish_execution(
        str(db),
        execution_id="e1",
        status="completed",
        end_time="2026-01-01T00:10:00Z",
        output_hash="out",
        exit_code=0,
    )

    bundle = get_execution_bundle(str(db), "e1")
    assert bundle["execution"]["status"] == "completed"
    assert bundle["execution"]["exit_code"] == 0
    assert bundle["audit_events"][0]["event_type"] == "execution_started"
