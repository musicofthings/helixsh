from helixsh.resources import estimate_resources


def test_estimate_resources_star_rnaseq():
    r = estimate_resources("star", "rnaseq", 2)
    assert r.total_cpu == 16
    assert r.total_memory_gb == 80


def test_estimate_resources_invalid_samples():
    try:
        estimate_resources("salmon", "rnaseq", 0)
    except ValueError:
        assert True
    else:
        raise AssertionError("expected ValueError")
