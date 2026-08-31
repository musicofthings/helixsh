"""POSIX execution boundary helpers."""

from __future__ import annotations

import subprocess
from typing import Iterable

from helixsh.nextflow import format_shell_command


def build_posix_exec(args: Iterable[str]) -> str:
    """Render the POSIX boundary wrapper shown in plans and audit records."""
    cmd = format_shell_command(args)
    return f'exec sh -c {format_shell_command([cmd])}'


def run_posix_exec(args: Iterable[str]) -> int:
    """Execute the command as argv, without an intervening shell.

    ``build_posix_exec`` documents the boundary for the reader, but execution
    passes the argv straight through so what runs is exactly what was planned
    and audited. Round-tripping through ``sh -c`` made that equivalence depend
    on string quoting, and any gap there meant the recorded command and the
    executed one could silently diverge.
    """
    completed = subprocess.run(list(args), check=False)
    return completed.returncode
