"""
Ed25519 keys of the signed-object rule: ``kid`` derivation, encodings, seeds.

``cryptography`` is imported only when a key is used, so the core package
imports without the ``jobcontext`` extra and fails on use with
:class:`MissingExtraError`. ``kid`` derivation and the encodings need only
the standard library.
"""

import hashlib
import importlib
import os
import secrets
from pathlib import Path
from types import ModuleType
from typing import Final

from ai_sdk_m8.signed._encoding import b64url_decode, b64url_encode
from ai_sdk_m8.signed._errors import MalformedSignedObjectError, MissingExtraError

SEED_BYTES: Final = 32
PUBLIC_KEY_BYTES: Final = 32
SIGNATURE_BYTES: Final = 64
_KID_DIGEST_BYTES: Final = 16


def _ed25519() -> ModuleType:
    try:
        return importlib.import_module(
            "cryptography.hazmat.primitives.asymmetric.ed25519"
        )
    except ImportError:
        raise MissingExtraError from None


def _check_length(value: bytes, size: int, what: str) -> None:
    if not isinstance(value, bytes) or len(value) != size:
        raise ValueError(f"{what} must be exactly {size} bytes")


def derive_kid(public_key: bytes) -> str:
    """``kid`` = unpadded base64url of the first 16 bytes of SHA-256(public key)."""
    _check_length(public_key, PUBLIC_KEY_BYTES, "public key")
    return b64url_encode(hashlib.sha256(public_key).digest()[:_KID_DIGEST_BYTES])


def encode_public_key(public_key: bytes) -> str:
    """The configuration form of a raw public key: unpadded base64url."""
    _check_length(public_key, PUBLIC_KEY_BYTES, "public key")
    return b64url_encode(public_key)


def decode_public_key(text: str) -> bytes:
    """Parse :func:`encode_public_key`'s form; anything else is ``ValueError``."""
    try:
        raw = b64url_decode(text)
    except MalformedSignedObjectError:
        raise ValueError("public key is not strict unpadded base64url") from None
    _check_length(raw, PUBLIC_KEY_BYTES, "public key")
    return raw


def generate_seed() -> bytes:
    """A fresh 32-byte Ed25519 seed from the operating system's CSPRNG."""
    return secrets.token_bytes(SEED_BYTES)


def public_key_from_seed(seed: bytes) -> bytes:
    """The raw 32-byte public key of ``seed``."""
    _check_length(seed, SEED_BYTES, "seed")
    key = _ed25519().Ed25519PrivateKey.from_private_bytes(seed)
    public: bytes = key.public_key().public_bytes_raw()
    return public


def sign_bytes(seed: bytes, message: bytes) -> bytes:
    """Ed25519 signature of ``message`` under ``seed``."""
    _check_length(seed, SEED_BYTES, "seed")
    signature: bytes = (
        _ed25519().Ed25519PrivateKey.from_private_bytes(seed).sign(message)
    )
    return signature


def verify_bytes(public_key: bytes, signature: bytes, message: bytes) -> bool:
    """Whether ``signature`` is a valid Ed25519 signature of ``message``."""
    module = _ed25519()
    exceptions = importlib.import_module("cryptography.exceptions")
    try:
        module.Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
    except (exceptions.InvalidSignature, ValueError):
        return False
    return True


def write_seed_file(path: Path, seed: bytes) -> None:
    """
    Write ``seed`` to a new file created ``0600``; an existing path is refused.

    ``O_EXCL`` refuses to replace (or follow a link at) ``path``, and the
    requested mode can only be narrowed by the umask.
    """
    _check_length(seed, SEED_BYTES, "seed")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(seed)
        handle.flush()
        os.fsync(handle.fileno())


def load_seed_file(path: Path) -> bytes:
    """Read a seed written by :func:`write_seed_file`: exactly 32 raw bytes."""
    with path.open("rb") as handle:
        seed = handle.read(SEED_BYTES + 1)
    if len(seed) != SEED_BYTES:
        raise ValueError(f"seed file must hold exactly {SEED_BYTES} bytes")
    return seed


__all__ = [
    "PUBLIC_KEY_BYTES",
    "SEED_BYTES",
    "SIGNATURE_BYTES",
    "decode_public_key",
    "derive_kid",
    "encode_public_key",
    "generate_seed",
    "load_seed_file",
    "public_key_from_seed",
    "sign_bytes",
    "verify_bytes",
    "write_seed_file",
]
