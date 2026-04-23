"""Nextflow workflow intelligence helpers (AST-lite and DAG extraction).

Supports both DSL1/DSL2 Groovy-style and the Nextflow v2 syntax introduced in
25.x.  The parser is brace-aware so it handles nested blocks (script sections,
interpolated strings, etc.) correctly without a full grammar.
"""

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


# Matches the opening line of a process block: `process NAME {`
_PROCESS_HEADER_RE = re.compile(r"\bprocess\s+(\w+)\s*\{")

FIELD_RE = {
    "cpus": re.compile(r"\bcpus\s+([^\n]+)"),
    "memory": re.compile(r"\bmemory\s+([^\n]+)"),
    "time": re.compile(r"\btime\s+([^\n]+)"),
    "container": re.compile(r"\bcontainer\s+([^\n]+)"),
}


def _extract_body(text: str, brace_pos: int) -> str:
    """Return the content between the opening brace at brace_pos and its matching close."""
    depth = 0
    i = brace_pos
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[brace_pos + 1 : i]
        i += 1
    # Unclosed brace — return everything after the opening brace
    return text[brace_pos + 1 :]


def parse_process_nodes(nf_text: str) -> list[ProcessNode]:
    nodes: list[ProcessNode] = []
    for m in _PROCESS_HEADER_RE.finditer(nf_text):
        name = m.group(1)
        # m.end() - 1 is the position of the opening '{' of the process block
        body = _extract_body(nf_text, m.end() - 1)
        values: dict[str, str | None] = {}
        for field, pattern in FIELD_RE.items():
            fm = pattern.search(body)
            values[field] = fm.group(1).strip().strip("\"'") if fm else None
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
