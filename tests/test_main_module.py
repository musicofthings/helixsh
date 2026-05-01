import runpy

import pytest


def test_module_entrypoint_propagates_exit_code(monkeypatch):
    monkeypatch.setattr("helixsh.cli.main", lambda: 2)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("helixsh", run_name="__main__")
    assert exc.value.code == 2
