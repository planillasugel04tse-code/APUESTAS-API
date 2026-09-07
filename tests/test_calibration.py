import pytest

from betano_analyzer.calibration import calibration_report


def test_calibration_report_returns_core_metrics():
    report = calibration_report([0.60, 0.70, 0.80, 0.40], [1, 1, 0, 0], buckets=4)
    assert report.samples == 4
    assert report.brier_score == pytest.approx(0.255)
    assert report.observed_rate == pytest.approx(0.5)
    assert report.mean_probability == pytest.approx(0.625)
    assert report.calibration_error >= 0
    assert report.buckets


def test_calibration_rejects_invalid_data():
    with pytest.raises(ValueError):
        calibration_report([], [])
    with pytest.raises(ValueError):
        calibration_report([0.5], [2])
    with pytest.raises(ValueError):
        calibration_report([0.0], [1])
    with pytest.raises(ValueError):
        calibration_report([0.5], [1], buckets=1)
