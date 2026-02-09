from helixsh.empirical import Observation, fit_calibration


def test_fit_calibration_mean_ratios():
    fitted = fit_calibration(
        [
            Observation(expected_cpu=4, observed_cpu=8, expected_memory_gb=8, observed_memory_gb=12),
            Observation(expected_cpu=2, observed_cpu=2, expected_memory_gb=4, observed_memory_gb=6),
        ]
    )
    assert round(fitted.cpu_multiplier, 2) == 1.5
    assert round(fitted.memory_multiplier, 2) == 1.5
