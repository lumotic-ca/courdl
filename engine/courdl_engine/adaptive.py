from __future__ import annotations

import threading


def looks_rate_limited(exc: BaseException) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    return any(
        token in text
        for token in ("429", "too many", "rate limit", "ratelimit", "slow down")
    )


class AdaptiveGate:
    """Limit in-flight course downloads. Drop to low on 429, climb back after successes."""

    def __init__(self, *, high: int = 5, low: int = 3, recover_after: int = 4):
        self.high = max(1, high)
        self.low = max(1, min(low, self.high))
        self.recover_after = max(1, recover_after)
        self.limit = self.high
        self.in_flight = 0
        self.ok_streak = 0
        self._cv = threading.Condition()

    def enter(self) -> int:
        with self._cv:
            while self.in_flight >= self.limit:
                self._cv.wait()
            self.in_flight += 1
            return self.limit

    def leave(self, *, rate_limited: bool) -> int:
        with self._cv:
            self.in_flight = max(0, self.in_flight - 1)
            if rate_limited:
                self.limit = self.low
                self.ok_streak = 0
            else:
                self.ok_streak += 1
                if self.ok_streak >= self.recover_after and self.limit < self.high:
                    self.limit += 1
                    self.ok_streak = 0
            self._cv.notify_all()
            return self.limit
