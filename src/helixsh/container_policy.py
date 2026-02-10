"""Container image policy checks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImagePolicyResult:
    image: str
    has_digest: bool
    allowed: bool
    message: str


def check_image_policy(image: str) -> ImagePolicyResult:
    img = image.strip()
    has_digest = "@sha256:" in img
    if has_digest:
        return ImagePolicyResult(image=img, has_digest=True, allowed=True, message="Digest-pinned image")
    if not img:
        return ImagePolicyResult(image=img, has_digest=False, allowed=False, message="Empty image reference")
    return ImagePolicyResult(
        image=img,
        has_digest=False,
        allowed=True,
        message="Image allowed but digest pin recommended",
    )
