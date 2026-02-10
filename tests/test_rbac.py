from helixsh.rbac import check_access


def test_rbac_admin_allowed():
    d = check_access("admin", "run")
    assert d.allowed is True


def test_rbac_auditor_denied_for_run():
    d = check_access("auditor", "run")
    assert d.allowed is False
