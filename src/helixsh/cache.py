"""Resume/cache reporting helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CacheReport:
    cached_percent: int
    invalidated_processes: tuple[str, ...]
    recommendation: str


def summarize_cache(total_tasks: int, cached_tasks: int, invalidated: list[str]) -> CacheReport:
    if total_tasks <= 0:
        percent = 0
    else:
        percent = int((cached_tasks / total_tasks) * 100)

    recommendation = "Resume should be effective"
    if invalidated:
        recommendation = "Pin inputs/references to maximize cache hits"

    return CacheReport(
        cached_percent=percent,
        invalidated_processes=tuple(invalidated),
        recommendation=recommendation,
    )
