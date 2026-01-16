from __future__ import annotations
from dataclasses import dataclass
import random


@dataclass
class Prediction:
    will_fail_probability: float
    reason: str


def predict_failure(goals_count: int, completed_ratio: float) -> Prediction:
    """
    Cheap Bayesian-ish model:
    more goals + low completed ratio -> higher failure odds
    """
    base = 0.2 + (goals_count * 0.03)
    base += (0.8 - completed_ratio)
    base = max(0.05, min(0.95, base))
    return Prediction(
        will_fail_probability=base,
        reason=f"Pattern match: {goals_count} goals, completion ratio {completed_ratio:.2f}"
    )


def update_stability(current: float, ignored_warnings: int, completed_tasks: int) -> float:
    # ignoring future reduces stability, completing increases
    delta = completed_tasks * 0.05 - ignored_warnings * 0.08
    new = max(0.0, min(1.0, current + delta + random.uniform(-0.02, 0.02)))
    return new


def should_lock_prison(stability: float, fail_prob: float) -> bool:
    return stability < 0.25 and fail_prob > 0.75
