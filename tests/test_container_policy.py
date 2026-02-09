from helixsh.container_policy import check_image_policy


def test_digest_pinned_image():
    r = check_image_policy("ghcr.io/org/tool@sha256:abc")
    assert r.allowed is True
    assert r.has_digest is True


def test_empty_image_denied():
    r = check_image_policy("")
    assert r.allowed is False
