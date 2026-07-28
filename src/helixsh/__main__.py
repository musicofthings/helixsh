"""Executable module for zipapp/`python -m helixsh`."""

from __future__ import annotations

from helixsh.cli import main


def run() -> None:
    """Execute CLI and propagate exit code."""
    raise SystemExit(main())


if __name__ == "__main__":
    run()
