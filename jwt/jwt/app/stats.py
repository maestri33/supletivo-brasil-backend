"""Contadores de uso — puramente em memoria, zera no restart."""

import time
from dataclasses import dataclass, field


@dataclass
class Stats:
    tokens_issued: int = 0
    tokens_refreshed: int = 0
    jwks_fetches: int = 0
    errors: int = 0
    started_at: float = field(default_factory=time.time)

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.started_at

    def inc_issued(self):
        self.tokens_issued += 1

    def inc_refreshed(self):
        self.tokens_refreshed += 1

    def inc_jwks(self):
        self.jwks_fetches += 1

    def inc_error(self):
        self.errors += 1


_stats = Stats()


def get_stats() -> Stats:
    return _stats
