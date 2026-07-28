"""Cloud cost estimation for bioinformatics pipeline runs.

Combines helixsh resource estimates (CPU, memory) with per-hour instance
pricing for AWS, GCP, and Azure to give a rough cost envelope before
submitting a pipeline.

Prices are hardcoded approximations (USD/hour, on-demand, us-east-1 / us-east4
/ eastus) from late 2025.  They drift over time — treat as order-of-magnitude
guidance, not billing predictions.  Users can override via --price-per-cpu-hour
and --price-per-gb-hour.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# On-demand price tables (USD/hour).
# Format: provider -> instance_family -> {"cpu": $/vCPU-h, "mem": $/GB-h}
# Sources: AWS, GCP, Azure pricing pages (approximate, late 2025).
_PRICE_TABLE: dict[str, dict[str, dict[str, float]]] = {
    "aws": {
        "general":  {"cpu": 0.048,  "mem": 0.006},   # m7i
        "compute":  {"cpu": 0.042,  "mem": 0.0056},  # c7i
        "memory":   {"cpu": 0.032,  "mem": 0.004},   # r7i
        "spot":     {"cpu": 0.014,  "mem": 0.0018},  # ~70% spot discount
    },
    "gcp": {
        "general":  {"cpu": 0.0475, "mem": 0.00638}, # n2-standard
        "compute":  {"cpu": 0.0368, "mem": 0.00492}, # c3
        "memory":   {"cpu": 0.0279, "mem": 0.00374}, # m3
        "spot":     {"cpu": 0.0143, "mem": 0.00191}, # ~70% preemptible discount
    },
    "azure": {
        "general":  {"cpu": 0.048,  "mem": 0.006},   # D-series v5
        "compute":  {"cpu": 0.038,  "mem": 0.005},   # F-series
        "memory":   {"cpu": 0.030,  "mem": 0.004},   # E-series
        "spot":     {"cpu": 0.014,  "mem": 0.0018},  # ~70% spot discount
    },
}

SUPPORTED_PROVIDERS = list(_PRICE_TABLE)
SUPPORTED_INSTANCE_FAMILIES = ["general", "compute", "memory", "spot"]


@dataclass
class CostEstimate:
    provider: str
    instance_family: str
    total_cpu: int
    total_memory_gb: int
    wall_hours: float
    cost_usd: float
    cost_usd_min: float   # spot / preemptible lower bound
    cost_usd_max: float   # on-demand upper bound
    breakdown: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def estimate_cost(
    *,
    total_cpu: int,
    total_memory_gb: int,
    wall_hours: float,
    provider: str = "aws",
    instance_family: str = "general",
    price_per_cpu_hour: float | None = None,
    price_per_gb_hour: float | None = None,
) -> CostEstimate:
    """Estimate cloud cost for a given resource footprint."""
    prov = provider.strip().lower()
    fam  = instance_family.strip().lower()

    if prov not in _PRICE_TABLE:
        raise ValueError(f"Unknown provider '{provider}'. Supported: {', '.join(SUPPORTED_PROVIDERS)}")
    if fam not in _PRICE_TABLE[prov]:
        raise ValueError(f"Unknown instance family '{instance_family}'. Supported: {SUPPORTED_INSTANCE_FAMILIES}")

    prices = _PRICE_TABLE[prov][fam]
    cpu_rate = price_per_cpu_hour if price_per_cpu_hour is not None else prices["cpu"]
    mem_rate = price_per_gb_hour  if price_per_gb_hour  is not None else prices["mem"]

    cpu_cost = total_cpu * wall_hours * cpu_rate
    mem_cost = total_memory_gb * wall_hours * mem_rate
    total    = cpu_cost + mem_cost

    # Spot/preemptible lower bound (reuse spot prices for on-demand estimate)
    spot_prices = _PRICE_TABLE[prov]["spot"]
    min_cost = total_cpu * wall_hours * spot_prices["cpu"] + total_memory_gb * wall_hours * spot_prices["mem"]

    # On-demand upper bound (use general if current family is spot)
    od_fam = "general" if fam == "spot" else fam
    od_prices = _PRICE_TABLE[prov][od_fam]
    max_cost = total_cpu * wall_hours * od_prices["cpu"] + total_memory_gb * wall_hours * od_prices["mem"]

    notes: list[str] = []
    if wall_hours > 24:
        notes.append("Long wall-time — consider checkpointing with -resume to reduce re-run costs")
    if total_memory_gb > total_cpu * 8:
        notes.append("Memory-heavy workload — consider memory-optimised instances for lower cost")
    if total_cpu > 64:
        notes.append("Large CPU footprint — spot/preemptible instances recommended")

    return CostEstimate(
        provider=prov,
        instance_family=fam,
        total_cpu=total_cpu,
        total_memory_gb=total_memory_gb,
        wall_hours=wall_hours,
        cost_usd=round(total, 4),
        cost_usd_min=round(min_cost, 4),
        cost_usd_max=round(max_cost, 4),
        breakdown={"cpu_cost_usd": round(cpu_cost, 4), "mem_cost_usd": round(mem_cost, 4)},
        notes=notes,
    )


def compare_providers(
    *,
    total_cpu: int,
    total_memory_gb: int,
    wall_hours: float,
    instance_family: str = "general",
) -> list[CostEstimate]:
    """Return cost estimates across all three providers for easy comparison."""
    results = []
    for provider in SUPPORTED_PROVIDERS:
        try:
            results.append(estimate_cost(
                total_cpu=total_cpu, total_memory_gb=total_memory_gb,
                wall_hours=wall_hours, provider=provider,
                instance_family=instance_family,
            ))
        except ValueError:
            pass
    return sorted(results, key=lambda e: e.cost_usd)
