from __future__ import annotations

from dataclasses import dataclass

from .calibration import CalibrationReport


@dataclass(frozen=True)
class CalibrationGate:
    usable: bool
    confidence_multiplier: float
    adjusted_confidence: float
    reason: str


def apply_calibration_gate(
    confidence: float,
    report: CalibrationReport | None,
    *,
    max_calibration_error: float = 0.08,
    min_samples: int = 30,
) -> CalibrationGate:
    """Reduce or reject confidence when historical probabilities are poorly calibrated.

    Calibration is evidence about the model, not a prediction of the next match.
    With too little history the gate stays neutral instead of pretending certainty.
    """
    if not 0 <= confidence <= 1:
        raise ValueError("confidence must be between 0 and 1")
    if max_calibration_error < 0:
        raise ValueError("max_calibration_error must be non-negative")
    if min_samples < 1:
        raise ValueError("min_samples must be positive")

    if report is None:
        return CalibrationGate(True, 1.0, round(confidence, 8), "no_calibration_data")
    if report.samples < min_samples:
        return CalibrationGate(True, 1.0, round(confidence, 8), "insufficient_calibration_sample")

    error = report.calibration_error
    if error <= max_calibration_error:
        return CalibrationGate(True, 1.0, round(confidence, 8), "calibration_acceptable")

    multiplier = max(0.50, 1.0 - min(error, 0.50))
    adjusted = confidence * multiplier
    usable = adjusted >= 0.50
    reason = "calibration_penalty" if usable else "poor_calibration"
    return CalibrationGate(usable, round(multiplier, 8), round(adjusted, 8), reason)
