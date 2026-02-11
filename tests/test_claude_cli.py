from helixsh.claude_cli import generate_plan


def test_generate_plan_memory_prompt():
    plan = generate_plan("optimize memory usage")
    assert plan.confidence > 0.8
    assert "memory" in plan.proposed_diff_summary.lower()
