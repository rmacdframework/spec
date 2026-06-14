"""
RMACD Governance Packs - Signing & Verification
===============================================

Freeze and sign a governance pack with an Ed25519 key, and verify a signed pack.
A signature binds the pack's canonical ``content_hash`` (which excludes the
``content_hash`` and ``signature`` fields themselves), so signing is stable and
any post-sign edit invalidates verification.

Optional dependency: ``pip install rmacd-framework[sign]`` (the ``cryptography``
package). Importing this module is safe without it; only signing/verifying needs
it. Production loaders should ``verify_pack`` against a trusted public key before
trusting a pack's classifications.

Author: Kash Kashyap
License: CC BY 4.0
"""

from __future__ import annotations

import base64
from typing import Any

from rmacd.packs.models import GovernancePack

_SIG_PREFIX = "ed25519:"


class PackSignatureError(Exception):
    """Raised when signing or verification cannot be performed."""


def _require_cryptography() -> Any:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "Pack signing requires the 'cryptography' package. "
            "Install it with: pip install rmacd-framework[sign]"
        ) from exc
    return serialization, ed25519


def generate_keypair() -> tuple[str, str]:
    """Generate an Ed25519 keypair, returned as (private_pem, public_pem) strings."""
    serialization, ed25519 = _require_cryptography()
    private = ed25519.Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


def sign_pack(pack: GovernancePack, private_key_pem: str) -> GovernancePack:
    """Return a frozen + signed copy of *pack* (sets ``content_hash`` + ``signature``)."""
    serialization, _ = _require_cryptography()
    frozen = pack.freeze()
    assert frozen.content_hash is not None
    private = serialization.load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
    signature = private.sign(frozen.content_hash.encode("utf-8"))
    encoded = _SIG_PREFIX + base64.b64encode(signature).decode("ascii")
    return frozen.model_copy(update={"signature": encoded})


def verify_pack(pack: GovernancePack, public_key_pem: str) -> bool:
    """True iff the pack's content_hash matches its content AND the signature verifies."""
    if not pack.verify_hash():
        return False
    if not pack.signature or not pack.signature.startswith(_SIG_PREFIX):
        return False
    assert pack.content_hash is not None
    serialization, _ = _require_cryptography()
    try:
        public = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        signature = base64.b64decode(pack.signature[len(_SIG_PREFIX):])
        public.verify(signature, pack.content_hash.encode("utf-8"))
        return True
    except Exception:  # noqa: BLE001 - any verification failure is a non-match
        return False


def is_signed(pack: GovernancePack) -> bool:
    """Whether the pack carries a content hash and an Ed25519 signature."""
    return bool(pack.content_hash) and bool(
        pack.signature and pack.signature.startswith(_SIG_PREFIX)
    )


__all__ = [
    "PackSignatureError",
    "generate_keypair",
    "sign_pack",
    "verify_pack",
    "is_signed",
]
