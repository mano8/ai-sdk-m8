"""
Typed failures of the signed-object rule.

Every message is a fixed sentence: no token, payload, key or seed byte ever
enters an exception, and every raise drops the causing exception so a
validation error cannot carry the input along.
"""


class SignedObjectError(ValueError):
    """A signed object was refused; the subclass says at which stage."""


class MalformedSignedObjectError(SignedObjectError):
    """Refused before any signature work: size, encoding, JSON or canonical form."""


class UnknownKeyError(SignedObjectError):
    """The object's ``kid`` names no configured public key."""


class SignatureInvalidError(SignedObjectError):
    """The Ed25519 signature does not verify over the recomputed signed bytes."""


class PayloadInvalidError(SignedObjectError):
    """The payload is outside the expected closed model, ``v`` or ``typ``."""


class MissingExtraError(ImportError):
    """Signing or verification was called without the ``jobcontext`` extra."""

    def __init__(self) -> None:
        super().__init__(
            "Ed25519 signing needs the 'jobcontext' extra: "
            "pip install 'ai-sdk-m8[jobcontext]'"
        )


__all__ = [
    "MalformedSignedObjectError",
    "MissingExtraError",
    "PayloadInvalidError",
    "SignatureInvalidError",
    "SignedObjectError",
    "UnknownKeyError",
]
