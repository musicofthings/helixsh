from helixsh.roadmap import compute_roadmap_status


def test_roadmap_has_all_phases():
    phases = compute_roadmap_status()
    assert len(phases) == 4
    assert all(phase.status == "in_progress" for phase in phases)
    assert all(phase.pending for phase in phases)
    assert "Execution-time preflight enforcement" in phases[0].completed
