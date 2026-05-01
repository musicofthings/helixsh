"""Cross-module sanity checks for CLI/RBAC consistency."""

from __future__ import annotations

from helixsh.cli import make_parser
from helixsh.rbac import ROLE_PERMISSIONS

def _cli_command_names() -> set[str]:
    parser = make_parser()
    subparsers_action = next(a for a in parser._actions if getattr(a, "dest", None) == "command")
    return set(subparsers_action.choices.keys())

def test_rbac_references_only_known_cli_commands() -> None:
    commands = _cli_command_names()
    for role, allowed in ROLE_PERMISSIONS.items():
        unknown = sorted(set(allowed) - commands)
        assert not unknown, f"Role '{role}' contains unknown commands: {unknown}"

def test_admin_role_covers_full_cli_surface() -> None:
    commands = _cli_command_names()
    assert commands == ROLE_PERMISSIONS["admin"]
