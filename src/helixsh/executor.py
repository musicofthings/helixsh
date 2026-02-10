"""POSIX execution boundary helpers."""

from __future__ import annotations

import subprocess
from typing import Iterable

from helixsh.nextflow import format_shell_command


def build_posix_exec(args: Iterable[str]) -> str:
    cmd = format_shell_command(args)
    return f'exec sh -c {format_shell_command([cmd])}'


def run_posix_exec(args: Iterable[str]) -> int:
    wrapped = build_posix_exec(args)
    completed = subprocess.run(["sh", "-c", wrapped], check=False)
    return completed.returncode
