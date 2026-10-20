"""
The C-03 signed-object rule: one composition for every Ed25519 purpose.

signed bytes = ``UTF-8(domain_tag) || 0x00 || JCS(payload)``. The payload
always carries ``v``, ``typ`` (equal to the domain tag) and ``kid``. The
domain tag is supplied by the **verifier** for the one purpose it expects and
is never read from the object.

Two encodings verify over the same recomputed signed bytes:

* compact — ``b64url(JCS(payload)) "." b64url(sig)`` (headers, receipts);
* structured — ``{"record": payload, "kid": kid, "sig": b64url(sig)}``
  (sandbox attestations).

Parsing comes before any trust: the size cap, strict base64url, strict JSON
and the canonical byte-compare all run before the signature is checked, and
the closed model runs last.
"""

from collections.abc import Mapping
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ValidationError

from ai_sdk_m8.signed._encoding import (
    b64url_decode,
    b64url_encode,
    canonicalize,
    parse_strict,
)
from ai_sdk_m8.signed._errors import (
    MalformedSignedObjectError,
    PayloadInvalidError,
    SignatureInvalidError,
    UnknownKeyError,
)
from ai_sdk_m8.signed._keys import (
    SIGNATURE_BYTES,
    derive_kid,
    public_key_from_seed,
    sign_bytes,
    verify_bytes,
)


class Domain(StrEnum):
    """The three signature purposes; no seed serves two of them."""

    JOB_CONTEXT = "m8.ai.job-context.v1"
    OCR_RECEIPT = "m8.ai.ocr-receipt.v1"
    SANDBOX_ATTESTATION = "m8.doctools.sandbox-attestation.v1"


#: Total encoded size cap per purpose, checked before any decoding.
MAX_ENCODED_BYTES: Final[Mapping[Domain, int]] = {
    Domain.JOB_CONTEXT: 4 * 1024,
    Domain.OCR_RECEIPT: 4 * 1024,
    Domain.SANDBOX_ATTESTATION: 32 * 1024,
}

_RECORD_KEYS: Final = frozenset({"record", "kid", "sig"})


def _domain(domain: Domain | str) -> Domain:
    try:
        return Domain(domain)
    except ValueError:
        raise ValueError("unknown signed-object domain") from None


def signing_input(domain: Domain | str, payload_jcs: bytes) -> bytes:
    """The exact bytes Ed25519 signs: domain tag, NUL, canonical payload."""
    return _domain(domain).value.encode("utf-8") + b"\x00" + payload_jcs


def _payload_mapping(payload: Mapping[str, object] | BaseModel) -> dict[str, object]:
    if isinstance(payload, BaseModel):
        return payload.model_dump(mode="json", exclude_none=True)
    return dict(payload)


def _prepare(
    payload: Mapping[str, object] | BaseModel, domain: Domain, seed: bytes
) -> tuple[dict[str, object], bytes, str, bytes]:
    body = _payload_mapping(payload)
    kid = derive_kid(public_key_from_seed(seed))
    version = body.get("v")
    if not isinstance(version, int) or isinstance(version, bool):
        raise PayloadInvalidError("payload must carry an integer 'v'")
    if body.get("typ") != domain.value:
        raise PayloadInvalidError("payload 'typ' must equal the domain tag")
    if body.get("kid") != kid:
        raise PayloadInvalidError("payload 'kid' must be the seed's derived kid")
    try:
        payload_jcs = canonicalize(body)
    except MalformedSignedObjectError:
        raise PayloadInvalidError("payload is not integer-only JSON") from None
    signature = sign_bytes(seed, signing_input(domain, payload_jcs))
    return body, payload_jcs, kid, signature


def sign_object(
    payload: Mapping[str, object] | BaseModel, *, domain: Domain | str, seed: bytes
) -> str:
    """Sign ``payload`` for ``domain`` and return the compact encoding."""
    tag = _domain(domain)
    _, payload_jcs, _, signature = _prepare(payload, tag, seed)
    token = b64url_encode(payload_jcs) + "." + b64url_encode(signature)
    if len(token) > MAX_ENCODED_BYTES[tag]:
        raise PayloadInvalidError("signed object exceeds the domain's size cap")
    return token


def sign_record(
    payload: Mapping[str, object] | BaseModel, *, domain: Domain | str, seed: bytes
) -> dict[str, object]:
    """Sign ``payload`` for ``domain`` and return the structured encoding."""
    tag = _domain(domain)
    body, _, kid, signature = _prepare(payload, tag, seed)
    record: dict[str, object] = {
        "record": body,
        "kid": kid,
        "sig": b64url_encode(signature),
    }
    if len(canonicalize(record)) > MAX_ENCODED_BYTES[tag]:
        raise PayloadInvalidError("signed object exceeds the domain's size cap")
    return record


def _split_compact(token: str, cap: int) -> tuple[object, bytes, bytes]:
    if len(token) > cap:
        raise MalformedSignedObjectError("signed object exceeds the size cap")
    parts = token.split(".")
    if len(parts) != 2:
        raise MalformedSignedObjectError("compact form needs exactly two segments")
    payload_jcs = b64url_decode(parts[0])
    signature = b64url_decode(parts[1])
    body = parse_strict(payload_jcs)
    if canonicalize(body) != payload_jcs:
        raise MalformedSignedObjectError("payload is not in canonical form")
    return body, payload_jcs, signature


def _split_record(
    record: Mapping[str, object], cap: int
) -> tuple[object, bytes, bytes]:
    if set(record) != _RECORD_KEYS:
        raise MalformedSignedObjectError("record form needs exactly record, kid, sig")
    if len(canonicalize(record)) > cap:
        raise MalformedSignedObjectError("signed object exceeds the size cap")
    body, kid, sig = record["record"], record["kid"], record["sig"]
    if not isinstance(body, Mapping) or not isinstance(sig, str):
        raise MalformedSignedObjectError("record form has the wrong member types")
    if body.get("kid") != kid:
        raise MalformedSignedObjectError("record kid differs from the payload kid")
    payload = dict(body)
    return payload, canonicalize(payload), b64url_decode(sig)


def _derives(public_key: bytes, kid: object) -> bool:
    try:
        return derive_kid(public_key) == kid
    except ValueError:
        return False


def _split(token_or_record: object, cap: int) -> tuple[dict[str, object], bytes, bytes]:
    if isinstance(token_or_record, str):
        body, payload_jcs, signature = _split_compact(token_or_record, cap)
    elif isinstance(token_or_record, Mapping):
        body, payload_jcs, signature = _split_record(token_or_record, cap)
    else:
        raise MalformedSignedObjectError("signed object is neither compact nor record")
    if not isinstance(body, dict) or len(signature) != SIGNATURE_BYTES:
        raise MalformedSignedObjectError("payload must be an object, sig 64 bytes")
    return body, payload_jcs, signature


def _public_key(body: Mapping[str, object], public_keys: Mapping[str, bytes]) -> bytes:
    kid = body.get("kid")
    public_key = public_keys.get(kid) if isinstance(kid, str) else None
    if public_key is None or not _derives(public_key, kid):
        raise UnknownKeyError("signed object names no configured key")
    return public_key


def verify_object[M: BaseModel](
    token_or_record: str | Mapping[str, object],
    *,
    domain: Domain | str,
    public_keys: Mapping[str, bytes],
    model: type[M],
) -> M:
    """
    Verify a signed object for ``domain`` and return its payload as ``model``.

    ``public_keys`` maps ``kid`` to a raw 32-byte public key; an entry whose
    key does not derive its own ``kid`` is never used. Raises a
    :class:`SignedObjectError` subclass naming the stage that refused it.
    """
    tag = _domain(domain)
    body, payload_jcs, signature = _split(token_or_record, MAX_ENCODED_BYTES[tag])
    public_key = _public_key(body, public_keys)
    if not verify_bytes(public_key, signature, signing_input(tag, payload_jcs)):
        raise SignatureInvalidError("signature does not verify")
    if body.get("typ") != tag.value or "v" not in body:
        raise PayloadInvalidError("payload 'typ' or 'v' is not this domain's")
    try:
        return model.model_validate(body)
    except ValidationError:
        raise PayloadInvalidError("payload does not match the closed model") from None


__all__ = [
    "MAX_ENCODED_BYTES",
    "Domain",
    "sign_object",
    "sign_record",
    "signing_input",
    "verify_object",
]
