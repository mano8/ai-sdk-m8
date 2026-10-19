"""
The C-03 signed-object rule, implemented once for every signer and verifier.

Job contexts, OCR execution receipts and sandbox attestations all sign
``UTF-8(domain_tag) || 0x00 || JCS(payload)`` with Ed25519 under their own
key. The verifier names the one domain it expects; strict, size-capped
parsing runs before any signature work and a closed model runs last.

Importing this module needs no extra; signing and verification need the
``jobcontext`` extra (``cryptography``) and raise :class:`MissingExtraError`
without it.
"""

from ai_sdk_m8.signed._encoding import (
    MAX_DEPTH,
    b64url_decode,
    b64url_encode,
    canonicalize,
    parse_strict,
)
from ai_sdk_m8.signed._errors import (
    MalformedSignedObjectError,
    MissingExtraError,
    PayloadInvalidError,
    SignatureInvalidError,
    SignedObjectError,
    UnknownKeyError,
)
from ai_sdk_m8.signed._keys import (
    PUBLIC_KEY_BYTES,
    SEED_BYTES,
    SIGNATURE_BYTES,
    decode_public_key,
    derive_kid,
    encode_public_key,
    generate_seed,
    load_seed_file,
    public_key_from_seed,
    write_seed_file,
)
from ai_sdk_m8.signed._rule import (
    MAX_ENCODED_BYTES,
    Domain,
    sign_object,
    sign_record,
    signing_input,
    verify_object,
)

__all__ = [
    "MAX_DEPTH",
    "MAX_ENCODED_BYTES",
    "PUBLIC_KEY_BYTES",
    "SEED_BYTES",
    "SIGNATURE_BYTES",
    "Domain",
    "MalformedSignedObjectError",
    "MissingExtraError",
    "PayloadInvalidError",
    "SignatureInvalidError",
    "SignedObjectError",
    "UnknownKeyError",
    "b64url_decode",
    "b64url_encode",
    "canonicalize",
    "decode_public_key",
    "derive_kid",
    "encode_public_key",
    "generate_seed",
    "load_seed_file",
    "parse_strict",
    "public_key_from_seed",
    "sign_object",
    "sign_record",
    "signing_input",
    "verify_object",
    "write_seed_file",
]
