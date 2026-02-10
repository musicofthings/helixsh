"""Nextflow workflow intelligence helpers (AST-lite and DAG extraction)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessNode:
    name: str
    cpus: str | None
    memory: str | None
    time: str | None
    container: str | None


PROCESS_RE = re.compile(r"process\s+(\w+)\s*\{(.*?)\}\s*", re.DOTALL)
FIELD_RE = {
    "cpus": re.compile(r"\bcpus\s+([^\n]+)"),
    "memory": re.compile(r"\bmemory\s+([^\n]+)"),
    "time": re.compile(r"\btime\s+([^\n]+)"),
    "container": re.compile(r"\bcontainer\s+([^\n]+)"),
}


def parse_process_nodes(nf_text: str) -> list[ProcessNode]:
    nodes: list[ProcessNode] = []
    for name, body in PROCESS_RE.findall(nf_text):
        values: dict[str, str | None] = {}
        for field, pattern in FIELD_RE.items():
            m = pattern.search(body)
            values[field] = m.group(1).strip().strip("\"'") if m else None
        nodes.append(
            ProcessNode(
                name=name,
                cpus=values["cpus"],
                memory=values["memory"],
                time=values["time"],
                container=values["container"],
            )
        )
    return nodes


def container_violations(nodes: list[ProcessNode]) -> list[str]:
    issues: list[str] = []
    for node in nodes:
        if not node.container:
            issues.append(f"Process {node.name} missing container")
    return issues
