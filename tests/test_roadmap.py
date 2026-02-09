from helixsh.roadmap import compute_roadmap_status


def test_roadmap_has_all_phases():
    phases = compute_roadmap_status()
    assert len(phases) == 4
    assert phases[0].status in {"completed", "in_progress"}
