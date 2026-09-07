from betano_analyzer.calibration import calibration_report
from betano_analyzer.calibration_gate import apply_calibration_gate


def test_master_radar_calibration_penalty_is_deterministic():
    report = calibration_report([0.90] * 30, [1] * 15 + [0] * 15)
    gate = apply_calibration_gate(0.90, report, min_samples=30)
    assert gate.usable is True
    assert gate.adjusted_confidence < 0.90
    assert gate.reason == "calibration_penalty"


def test_master_radar_calibration_is_neutral_with_small_sample():
    report = calibration_report([0.60, 0.70], [1, 0])
    gate = apply_calibration_gate(0.80, report, min_samples=30)
    assert gate.confidence_multiplier == 1.0
    assert gate.adjusted_confidence == 0.80
    assert gate.reason == "insufficient_calibration_sample"
