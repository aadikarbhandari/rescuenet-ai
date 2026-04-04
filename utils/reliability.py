"""
Reliability utilities for external service calls.

Includes:
- Exponential-backoff retry with jitter
- Simple in-memory circuit breaker to prevent repeated hammering
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import random
import time
from typing import Optional, Dict, Any

import requests


@dataclass
class RetryPolicy:
    max_attempts: int = 2
    timeout_seconds: float = 20.0
    base_delay_seconds: float = 0.8
    max_delay_seconds: float = 5.0
    retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504)


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.reset_timeout_seconds = reset_timeout_seconds
        self.failures = 0
        self.opened_at: Optional[datetime] = None

    def allow_request(self) -> bool:
        if self.opened_at is None:
            return True
        if datetime.utcnow() - self.opened_at >= timedelta(seconds=self.reset_timeout_seconds):
            # Half-open reset
            self.failures = 0
            self.opened_at = None
            return True
        return False

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = datetime.utcnow()


_BREAKERS: Dict[str, CircuitBreaker] = {}


def _get_breaker(key: str) -> CircuitBreaker:
    if key not in _BREAKERS:
        _BREAKERS[key] = CircuitBreaker()
    return _BREAKERS[key]


def resilient_post(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    policy: RetryPolicy,
    breaker_key: str,
) -> Optional[requests.Response]:
    breaker = _get_breaker(breaker_key)
    if not breaker.allow_request():
        return None

    for attempt in range(1, policy.max_attempts + 1):
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=policy.timeout_seconds,
            )
            if response.status_code in policy.retry_statuses and attempt < policy.max_attempts:
                delay = min(policy.max_delay_seconds, policy.base_delay_seconds * (2 ** (attempt - 1)))
                time.sleep(delay + random.uniform(0, 0.2))
                continue
            if 200 <= response.status_code < 300:
                breaker.record_success()
            else:
                breaker.record_failure()
            return response
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            breaker.record_failure()
            if attempt >= policy.max_attempts:
                return None
            delay = min(policy.max_delay_seconds, policy.base_delay_seconds * (2 ** (attempt - 1)))
            time.sleep(delay + random.uniform(0, 0.2))
        except Exception:
            breaker.record_failure()
            return None
    return None

