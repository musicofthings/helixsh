from helixsh.profiles import recommend_profile


def test_recommend_profile_wgs_offline():
    r = recommend_profile("wgs", "GRCh38", offline=True)
    assert r.pipeline == "nf-core/sarek"
    assert "-offline" in r.suggested_args
