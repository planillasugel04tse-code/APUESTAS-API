from betano_analyzer.calibration import calibration_report
from betano_analyzer.calibration_gate import apply_calibration_gate


def test_gate_is_neutral_without_enough_history():
    report = calibration_report([0.60, 0.70], [1, 0])
    gate = apply_calibration_gate(0.80, report, min_samples=30)
    assert gate.usable is True
    assert gate.confidence_multiplier == 1.0
    assert gate.reason == "insufficient_calibration_sample"


def test_gate_penalizes_poor_calibration():
    probabilities = [0.90] * 30
    outcomes = [1] * 15 + [0] * 15
    report = calibration_report(probabilities, outcomes)
    gate = apply_calibration_gate(0.90, report, max_calibration_error=0.08, min_samples=30)
    assert gate.usable is True
    assert gate.confidence_multiplier < 1.0
    assert gate.adjusted_confidence < 0.90
    assert gate.reason == "calibration_penalty"
