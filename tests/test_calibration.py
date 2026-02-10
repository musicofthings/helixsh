from helixsh.calibration import load_calibration


def test_load_calibration(tmp_path):
    p = tmp_path / "cal.json"
    p.write_text('{"cpu_multiplier":1.5,"memory_multiplier":2.0}', encoding="utf-8")
    c = load_calibration(str(p))
    assert c.cpu_multiplier == 1.5
    assert c.memory_multiplier == 2.0
