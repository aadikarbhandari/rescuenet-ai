"""SLO helpers for pass-15 load validation."""
from __future__ import annotations

from typing import List, Tuple


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    rank = (p / 100.0) * (len(vals) - 1)
    lo = int(rank)
    hi = min(len(vals) - 1, lo + 1)
    frac = rank - lo
    return vals[lo] + (vals[hi] - vals[lo]) * frac


def evaluate_slo(latencies_ms: List[float], errors: int, total: int,
                 p95_budget_ms: float, max_error_rate: float) -> Tuple[bool, dict]:
    p95 = percentile(latencies_ms, 95.0)
    err_rate = 0.0 if total == 0 else errors / float(total)
    passed = p95 <= p95_budget_ms and err_rate <= max_error_rate
    return passed, {
        "p95_ms": round(p95, 2),
        "error_rate": round(err_rate, 4),
        "total": total,
        "errors": errors,
        "p95_budget_ms": p95_budget_ms,
        "max_error_rate": max_error_rate,
    }
