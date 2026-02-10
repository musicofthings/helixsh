from helixsh.offline import check_offline_readiness


def test_offline_readiness_not_ready(tmp_path):
    r = check_offline_readiness(str(tmp_path))
    assert r.ready is False


def test_offline_readiness_ready(tmp_path):
    (tmp_path / "schemas").mkdir()
    (tmp_path / "containers").mkdir()
    (tmp_path / "nextflow_assets").mkdir()
    r = check_offline_readiness(str(tmp_path))
    assert r.ready is True
