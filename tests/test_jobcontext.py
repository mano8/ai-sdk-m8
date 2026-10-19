"""
Job contexts: the S-04 matrix rows a single token decides, and the payloads.

Rows that need the gateway's state (registered issuers and scopes, the
presenter equal to ``azp``, request binding, ``jti`` redemption on the
database clock) are the gateway's tests; :func:`verify` returns the claims
they compare.
"""

import json
from collections.abc import Callable

import pytest
from pydantic import ValidationError
from vectors_gen import (
    AUD,
    NOW,
    OCR_CLAIMS,
    attestation_claims,
    context_claims,
    kid_of,
    raw_token,
    receipt_claims,
    seed_of,
)

from ai_sdk_m8.jobcontext import (
    DEFAULT_DISPATCH_MAX_TTL_SECONDS,
    ContextExpiredError,
    ContextInvalidError,
    JobContextPayload,
    JobContextPhase,
    JobContextToken,
    OcrReceiptPayload,
    sign,
    verify,
)
from ai_sdk_m8.schemas import AiErrorCode
from ai_sdk_m8.signed import (
    Domain,
    PayloadInvalidError,
    SignedObjectError,
    b64url_decode,
    b64url_encode,
    derive_kid,
    public_key_from_seed,
    sign_object,
    sign_record,
    verify_object,
)

SEED = seed_of("job_context")
KEYS = {
    kid_of(name): public_key_from_seed(seed_of(name))
    for name in ("job_context", "ocr_receipt", "sandbox_attestation")
}
SPOOL_ID = "7e2a9c41-0d5b-4f63-8a17-c4e9b2d06f58"


def _payload(**claims: object) -> JobContextPayload:
    return JobContextPayload.model_validate(context_claims(**claims))


def _token(**claims: object) -> JobContextToken:
    return sign(_payload(**claims), seed=SEED)


def _verify(token: object, *, now: int = NOW + 1, aud: str = AUD) -> JobContextPayload:
    return verify(
        token,  # type: ignore[arg-type]
        public_keys=KEYS,
        aud=aud,
        now=now,
        max_ttl=900,
        skew=5,
    )


# --- valid -------------------------------------------------------------------


@pytest.mark.parametrize(
    "claims",
    [
        {},
        {"user_id": "user-42", "allowed_boundaries": ["local"]},
        {**OCR_CLAIMS, "phase": "spool"},
        {**OCR_CLAIMS, "phase": "dispatch", "spool_id": SPOOL_ID, "exp": NOW + 30},
    ],
)
def test_valid_context_round_trips(claims: dict[str, object]) -> None:
    payload = _payload(**claims)
    assert _verify(sign(payload, seed=SEED)) == payload


def test_absent_claims_are_omitted_from_the_signed_payload() -> None:
    token = _token()
    body = json.loads(payload_bytes(token))
    assert "user_id" not in body
    assert "phase" not in body


def payload_bytes(token: str) -> bytes:
    return b64url_decode(token.split(".")[0])


# --- signature and encoding --------------------------------------------------


def test_unknown_kid_is_invalid() -> None:
    seed = seed_of("unregistered")
    token = sign_object(
        context_claims(kid=kid_of("unregistered")),
        domain=Domain.JOB_CONTEXT,
        seed=seed,
    )
    with pytest.raises(ContextInvalidError):
        _verify(token)


def test_tampered_payload_and_signature_are_invalid() -> None:
    payload, signature = _token().split(".")
    tampered = json.loads(payload_bytes(_token()))
    tampered["attempt"] = 2
    raw = json.dumps(tampered, sort_keys=True, separators=(",", ":")).encode()
    for token in (
        b64url_encode(raw) + "." + signature,
        payload
        + "."
        + signature[:10]
        + ("A" if signature[10] != "A" else "B")
        + signature[11:],
    ):
        with pytest.raises(ContextInvalidError):
            _verify(token)


def test_signed_with_another_clients_key_is_invalid() -> None:
    raw = json.dumps(context_claims(), sort_keys=True, separators=(",", ":"))
    with pytest.raises(ContextInvalidError):
        _verify(raw_token(raw.encode(), key="ocr_receipt"))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda t: t + "=",
        lambda t: t.replace(".", ".."),
        lambda t: "x" * 5 * 1024,
        lambda t: t[:-1] + "+",
    ],
)
def test_malformed_encodings_are_invalid(mutate: object) -> None:
    with pytest.raises(ContextInvalidError):
        _verify(mutate(_token()))  # type: ignore[operator]


@pytest.mark.parametrize(
    "raw",
    [
        json.dumps(context_claims(), sort_keys=True).encode(),
        json.dumps(context_claims(), sort_keys=True, separators=(",", ":"))
        .replace('"attempt":1', '"attempt":1.0')
        .encode(),
        json.dumps(context_claims(), sort_keys=True, separators=(",", ":"))
        .replace('"aud":', '"attempt":1,"aud":', 1)
        .encode(),
    ],
)
def test_non_canonical_float_and_duplicate_keys_are_invalid(raw: bytes) -> None:
    with pytest.raises(ContextInvalidError):
        _verify(raw_token(raw))


def test_non_string_token_is_invalid() -> None:
    with pytest.raises(ContextInvalidError):
        _verify(b"bytes")


# --- cross-purpose substitution ----------------------------------------------


def test_receipt_and_attestation_are_not_contexts() -> None:
    receipt = sign_object(
        receipt_claims(), domain=Domain.OCR_RECEIPT, seed=seed_of("ocr_receipt")
    )
    record = sign_record(
        attestation_claims(),
        domain=Domain.SANDBOX_ATTESTATION,
        seed=seed_of("sandbox_attestation"),
    )
    with pytest.raises(ContextInvalidError):
        _verify(receipt)
    with pytest.raises(ContextInvalidError):
        _verify(record)


def test_context_is_not_a_receipt() -> None:
    with pytest.raises(SignedObjectError):
        verify_object(
            _token(),
            domain=Domain.OCR_RECEIPT,
            public_keys=KEYS,
            model=OcrReceiptPayload,
        )


# --- audience and clock ------------------------------------------------------


@pytest.mark.parametrize(
    "aud",
    ["ai-gateway/1f2e3d4c-5b6a-4978-8a9b-0c1d2e3f4a5b", "ai-gateway/staging", ""],
)
def test_wrong_audience_is_invalid(aud: str) -> None:
    with pytest.raises(ContextInvalidError):
        _verify(_token(), aud=aud)


def test_nbf_and_iat_may_lead_by_the_skew_only() -> None:
    lead = {"iat": NOW + 5, "nbf": NOW + 5, "exp": NOW + 60}
    assert _verify(_token(**lead), now=NOW).nbf == NOW + 5
    with pytest.raises(ContextInvalidError):
        _verify(_token(iat=NOW + 6, nbf=NOW + 6, exp=NOW + 60), now=NOW)
    with pytest.raises(ContextInvalidError):
        _verify(_token(iat=NOW, nbf=NOW + 6, exp=NOW + 60), now=NOW)


def test_expiry_has_no_leeway() -> None:
    token = _token(exp=NOW + 60)
    assert _verify(token, now=NOW + 59).exp == NOW + 60
    for now in (NOW + 60, NOW + 61):
        with pytest.raises(ContextExpiredError) as caught:
            _verify(token, now=now)
        assert caught.value.code is AiErrorCode.CONTEXT_EXPIRED


def test_ttl_over_the_cap_is_invalid() -> None:
    assert _verify(_token(exp=NOW + 900)).exp == NOW + 900
    with pytest.raises(ContextInvalidError):
        _verify(_token(exp=NOW + 901))


def test_dispatch_ttl_has_its_own_cap() -> None:
    claims = {**OCR_CLAIMS, "phase": "dispatch", "spool_id": SPOOL_ID}
    exp = NOW + DEFAULT_DISPATCH_MAX_TTL_SECONDS
    assert _verify(_token(**claims, exp=exp)).phase is JobContextPhase.DISPATCH
    with pytest.raises(ContextInvalidError):
        _verify(_token(**claims, exp=exp + 1))
    spool = _token(**OCR_CLAIMS, phase="spool", exp=exp + 1)
    assert _verify(spool).phase is JobContextPhase.SPOOL


@pytest.mark.parametrize(
    "kwargs", [{"max_ttl": 0}, {"skew": -1}, {"max_dispatch_ttl": 0}]
)
def test_verify_refuses_nonsense_limits(kwargs: dict[str, int]) -> None:
    params: dict[str, int] = {"max_ttl": 900, "skew": 5, **kwargs}
    with pytest.raises(ValueError, match="max_ttl"):
        verify(_token(), public_keys=KEYS, aud=AUD, now=NOW, **params)


# --- closed claim model ------------------------------------------------------


@pytest.mark.parametrize(
    "claims",
    [
        {"max_uses": 2},
        {"max_uses": True},
        {"v": 2},
        {"extra": "x"},
        {"user_id": None},
        {"capability": "chat"},
        {"capability": "unknown"},
        {"iat": NOW + 1},
        {"exp": NOW},
        {"allowed_boundaries": []},
        {"allowed_boundaries": ["local", "local"]},
        {"allowed_boundaries": ["remote"]},
        {"jti": "5D1E0C4A-3B7F-4A29-8E61-0C9F2B7D4A10"},
        {"jti": "5d1e0c4a-3b7f-1a29-8e61-0c9f2b7d4a10"},
        {"attempt": 0},
        {"attempt": "1"},
        {"aud": "gateway"},
        {"iss": ""},
        {"phase": "spool"},
        {"spool_id": SPOOL_ID},
        {"input_bytes": 10},
        {**OCR_CLAIMS},
        {**OCR_CLAIMS, "phase": "dispatch"},
        {**OCR_CLAIMS, "phase": "spool", "spool_id": SPOOL_ID},
        {**OCR_CLAIMS, "phase": "unknown"},
        {**OCR_CLAIMS, "phase": "spool", "input_sha256": "A" * 64},
    ],
)
def test_claim_model_refuses(claims: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _payload(**claims)
    token = sign_object(context_claims(**claims), domain=Domain.JOB_CONTEXT, seed=SEED)
    with pytest.raises(ContextInvalidError):
        _verify(token)


def test_typ_defaults_are_the_domain_tags() -> None:
    assert JobContextPayload.model_fields["typ"].default == Domain.JOB_CONTEXT.value
    assert OcrReceiptPayload.model_fields["typ"].default == Domain.OCR_RECEIPT.value


def test_signing_with_a_seed_that_is_not_the_kids_is_refused() -> None:
    with pytest.raises(PayloadInvalidError, match="kid"):
        sign(_payload(), seed=seed_of("ocr_receipt"))


# --- receipts ----------------------------------------------------------------


def test_receipt_round_trip() -> None:
    seed = seed_of("ocr_receipt")
    payload = OcrReceiptPayload.model_validate(receipt_claims())
    token = sign_object(payload, domain=Domain.OCR_RECEIPT, seed=seed)
    public = public_key_from_seed(seed)
    verified = verify_object(
        token,
        domain=Domain.OCR_RECEIPT,
        public_keys={derive_kid(public): public},
        model=OcrReceiptPayload,
    )
    assert verified == payload


@pytest.mark.parametrize(
    "claims",
    [
        {"capability": "embedding"},
        {"iss": "media-service"},
        {"result_sha256": "d" * 63},
        {"execution_identity": "c" * 64},
        {"produced_at": -1},
        {"job_ref": None},
    ],
)
def test_receipt_model_refuses(claims: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        OcrReceiptPayload.model_validate({**receipt_claims(), **claims})


# --- redaction ---------------------------------------------------------------


def test_token_repr_redacts_the_signature() -> None:
    token = _token()
    payload, signature = token.split(".")
    assert isinstance(token, str)
    assert signature not in repr(token)
    assert repr(token) == f"JobContextToken('{payload}.<redacted>')"
    assert str(token) == f"{payload}.{signature}"


def test_rejections_never_echo_the_token() -> None:
    token = _token()
    calls: tuple[Callable[[], object], ...] = (
        lambda: _verify(token, aud="ai-gateway/other"),
        lambda: _verify(token + "x"),
        lambda: _verify(token, now=NOW + 10_000),
    )
    for call in calls:
        with pytest.raises((ContextInvalidError, ContextExpiredError)) as caught:
            call()
        assert str(caught.value) in {"context_invalid", "context_expired"}
        assert caught.value.__cause__ is None
        assert token not in repr(caught.value)
