"""Nextflow execution trace parser and summariser.

Nextflow writes a tab-separated `trace.txt` (or custom name via `-with-trace`)
with one row per task.  This module parses that file and produces per-process
and overall resource summaries useful for cost estimation and optimisation.

Standard trace.txt columns (subset used here):
  task_id, hash, native_id, name, status, exit, submit, duration,
  realtime, %cpu, peak_rss, peak_vmem, rchar, wchar
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TaskRecord:
    task_id: str
    name: str
    process: str          # process name extracted from name (before " (")
    status: str
    exit_code: str
    duration_ms: int      # wall-clock in milliseconds
    realtime_ms: int      # CPU time in milliseconds
    cpu_pct: float        # peak %cpu (can exceed 100 for multi-threaded)
    peak_rss_mb: float    # peak resident set size in MB
    peak_vmem_mb: float   # peak virtual memory in MB


@dataclass
class ProcessSummary:
    process: str
    task_count: int
    failed_count: int
    avg_duration_s: float
    max_duration_s: float
    avg_cpu_pct: float
    max_peak_rss_mb: float
    avg_peak_rss_mb: float
    recommendation: str = ""


@dataclass
class TraceSummary:
    trace_file: str
    total_tasks: int
    failed_tasks: int
    total_walltime_s: float
    total_cpu_hours: float
    processes: list[ProcessSummary] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _parse_duration(s: str) -> int:
    """Convert Nextflow duration string to milliseconds.  e.g. '1m 30s' → 90000."""
    s = s.strip()
    if not s or s == "-":
        return 0
    total_ms = 0
    # Nextflow formats: '1d 2h 3m 4.5s', '500 ms', '1h', etc.
    import re
    # 'ms' must come before 'm' in the alternation so regex doesn't greedily match 'm' in 'ms'
    for value, unit in re.findall(r"([\d.]+)\s*(ms|[dhms])", s, re.IGNORECASE):
        v = float(value)
        unit = unit.lower()
        if unit == "d":
            total_ms += int(v * 86_400_000)
        elif unit == "h":
            total_ms += int(v * 3_600_000)
        elif unit == "m":
            total_ms += int(v * 60_000)
        elif unit == "s":
            total_ms += int(v * 1_000)
        elif unit == "ms":
            total_ms += int(v)
    return total_ms


def _parse_memory(s: str) -> float:
    """Convert Nextflow memory string to MB.  e.g. '1.5 GB' → 1536.0."""
    s = s.strip()
    if not s or s == "-":
        return 0.0
    import re
    m = re.match(r"([\d.]+)\s*(KB|MB|GB|TB|B)", s, re.IGNORECASE)
    if not m:
        return 0.0
    value = float(m.group(1))
    unit = m.group(2).upper()
    multipliers = {"B": 1 / 1024 / 1024, "KB": 1 / 1024, "MB": 1.0, "GB": 1024.0, "TB": 1024.0 * 1024}
    return value * multipliers.get(unit, 1.0)


def _extract_process_name(name: str) -> str:
    """Extract base process name from task name.  e.g. 'STAR_ALIGN (sample1)' → 'STAR_ALIGN'."""
    return name.split("(")[0].strip().split(":")[0].strip()


def parse_trace(path: str) -> TraceSummary:
    """Parse a Nextflow trace.txt and return a TraceSummary."""
    p = Path(path)
    if not p.exists():
        return TraceSummary(
            trace_file=path, total_tasks=0, failed_tasks=0,
            total_walltime_s=0, total_cpu_hours=0,
            warnings=[f"Trace file not found: {path}"],
        )

    with p.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        if reader.fieldnames is None:
            return TraceSummary(
                trace_file=path, total_tasks=0, failed_tasks=0,
                total_walltime_s=0, total_cpu_hours=0,
                warnings=["Trace file is empty or has no header"],
            )
        rows = list(reader)

    warnings: list[str] = []
    tasks: list[TaskRecord] = []
    for row in rows:
        try:
            cpu_raw = row.get("%cpu", "0").strip().rstrip("%") or "0"
            tasks.append(TaskRecord(
                task_id=row.get("task_id", "").strip(),
                name=row.get("name", "").strip(),
                process=_extract_process_name(row.get("name", "")),
                status=row.get("status", "").strip(),
                exit_code=str(row.get("exit", "")).strip(),
                duration_ms=_parse_duration(row.get("duration", "")),
                realtime_ms=_parse_duration(row.get("realtime", "")),
                cpu_pct=float(cpu_raw) if cpu_raw not in {"", "-", "."} else 0.0,
                peak_rss_mb=_parse_memory(row.get("peak_rss", "")),
                peak_vmem_mb=_parse_memory(row.get("peak_vmem", "")),
            ))
        except (ValueError, KeyError):
            warnings.append(f"Could not parse trace row: {row.get('name', '?')}")

    if not tasks:
        return TraceSummary(
            trace_file=path, total_tasks=0, failed_tasks=0,
            total_walltime_s=0, total_cpu_hours=0,
            warnings=warnings or ["No tasks found in trace file"],
        )

    failed = [t for t in tasks if t.status.upper() not in {"COMPLETED", "CACHED"}]
    total_wall_s = sum(t.duration_ms for t in tasks) / 1000
    total_cpu_h  = sum(t.realtime_ms * t.cpu_pct / 100 for t in tasks) / 3_600_000

    # Per-process aggregation
    from collections import defaultdict
    by_process: dict[str, list[TaskRecord]] = defaultdict(list)
    for t in tasks:
        by_process[t.process].append(t)

    process_summaries: list[ProcessSummary] = []
    for pname, ptasks in sorted(by_process.items()):
        durations = [t.duration_ms / 1000 for t in ptasks]
        cpus      = [t.cpu_pct for t in ptasks]
        rss_list  = [t.peak_rss_mb for t in ptasks]
        failed_n  = sum(1 for t in ptasks if t.status.upper() not in {"COMPLETED", "CACHED"})
        avg_dur   = sum(durations) / len(durations)
        max_rss   = max(rss_list) if rss_list else 0.0
        avg_rss   = sum(rss_list) / len(rss_list) if rss_list else 0.0

        # Generate simple recommendation
        rec = ""
        if max_rss > 0 and avg_rss > 0:
            headroom = max_rss / avg_rss
            if headroom > 2.0:
                rec = f"Memory usage highly variable (max {max_rss:.0f} MB vs avg {avg_rss:.0f} MB) — consider splitting batches"
            elif max_rss > 28_000:
                rec = f"High peak RSS ({max_rss:.0f} MB) — ensure memory limit exceeds this"
        if failed_n > 0 and not rec:
            rec = f"{failed_n} task(s) failed — inspect work directories"

        process_summaries.append(ProcessSummary(
            process=pname,
            task_count=len(ptasks),
            failed_count=failed_n,
            avg_duration_s=round(avg_dur, 2),
            max_duration_s=round(max(durations), 2),
            avg_cpu_pct=round(sum(cpus) / len(cpus), 1) if cpus else 0.0,
            max_peak_rss_mb=round(max_rss, 1),
            avg_peak_rss_mb=round(avg_rss, 1),
            recommendation=rec,
        ))

    return TraceSummary(
        trace_file=path,
        total_tasks=len(tasks),
        failed_tasks=len(failed),
        total_walltime_s=round(total_wall_s, 2),
        total_cpu_hours=round(total_cpu_h, 4),
        processes=process_summaries,
        warnings=warnings,
    )
