from helixsh.cache import summarize_cache


def test_summarize_cache_with_invalidations():
    r = summarize_cache(total_tasks=100, cached_tasks=83, invalidated=["ALIGN_READS"])
    assert r.cached_percent == 83
    assert r.invalidated_processes == ("ALIGN_READS",)
    assert "Pin inputs" in r.recommendation
