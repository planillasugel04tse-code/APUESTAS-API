from __future__ import annotations

from dataclasses import dataclass
from math import log


@dataclass(frozen=True)
class CalibrationReport:
    samples: int
    brier_score: float
    log_loss: float
    mean_probability: float
    observed_rate: float
    mean_absolute_error: float
    calibration_error: float
    buckets: tuple[dict, ...]


def _validate(probability: float) -> None:
    if not 0 < probability < 1:
        raise ValueError("probability must be between 0 and 1")


def calibration_report(probabilities: list[float], outcomes: list[int], *, buckets: int = 10) -> CalibrationReport:
    if not probabilities or len(probabilities) != len(outcomes):
        raise ValueError("probabilities and outcomes must have the same non-zero length")
    if buckets < 2 or buckets > 20:
        raise ValueError("buckets must be between 2 and 20")
    for probability in probabilities:
        _validate(probability)
    if any(outcome not in (0, 1) for outcome in outcomes):
        raise ValueError("outcomes must contain only 0 or 1")

    n = len(probabilities)
    brier = sum((p - y) ** 2 for p, y in zip(probabilities, outcomes)) / n
    log_loss = -sum(y * log(p) + (1 - y) * log(1 - p) for p, y in zip(probabilities, outcomes)) / n
    mean_probability = sum(probabilities) / n
    observed_rate = sum(outcomes) / n
    mae = sum(abs(p - y) for p, y in zip(probabilities, outcomes)) / n

    groups: list[list[tuple[float, int]]] = [[] for _ in range(buckets)]
    for probability, outcome in zip(probabilities, outcomes):
        index = min(int(probability * buckets), buckets - 1)
        groups[index].append((probability, outcome))

    bucket_rows: list[dict] = []
    weighted_error = 0.0
    for index, group in enumerate(groups):
        if not group:
            continue
        mean_p = sum(p for p, _ in group) / len(group)
        observed = sum(y for _, y in group) / len(group)
        error = abs(mean_p - observed)
        weighted_error += error * len(group) / n
        bucket_rows.append({
            "bucket": index,
            "samples": len(group),
            "mean_probability": round(mean_p, 6),
            "observed_rate": round(observed, 6),
            "absolute_error": round(error, 6),
        })

    return CalibrationReport(
        samples=n,
        brier_score=round(brier, 8),
        log_loss=round(log_loss, 8),
        mean_probability=round(mean_probability, 8),
        observed_rate=round(observed_rate, 8),
        mean_absolute_error=round(mae, 8),
        calibration_error=round(weighted_error, 8),
        buckets=tuple(bucket_rows),
    )
