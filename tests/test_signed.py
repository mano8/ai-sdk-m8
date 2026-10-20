"""The C-03 signed-object rule: encodings, keys, signing and verification."""

import hashlib
import json
import stat
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict
from vectors_gen import (
    attestation_claims,
    context_claims,
    kid_of,
    raw_token,
    seed_of,
)

from ai_sdk_m8.signed import (
    MAX_ENCODED_BYTES,
    Domain,
    MalformedSignedObjectError,
    PayloadInvalidError,
    SignatureInvalidError,
    SignedObjectError,
    UnknownKeyError,
    b64url_decode,
    b64url_encode,
    canonicalize,
    decode_public_key,
    derive_kid,
    encode_public_key,
    generate_seed,
    load_seed_file,
    parse_strict,
    public_key_from_seed,
    sign_object,
    sign_record,
    signing_input,
    verify_object,
    write_seed_file,
)
from ai_sdk_m8.signed._keys import sign_bytes, verify_bytes

SEED = seed_of("job_context")
PUBLIC = public_key_from_seed(SEED)
KID = derive_kid(PUBLIC)
KEYS = {KID: PUBLIC}


class Open(BaseModel):
    """A permissive model: these tests exercise the rule, not a payload."""

    model_config = ConfigDict(extra="allow", frozen=True)


def _verify(token: object, domain: Domain = Domain.JOB_CONTEXT) -> Open:
    return verify_object(
        token,  # type: ignore[arg-type]
        domain=domain,
        public_keys=KEYS,
        model=Open,
    )


def _signed_raw(payload: object, domain: Domain = Domain.JOB_CONTEXT) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    signature = sign_bytes(SEED, signing_input(domain, raw))
    return b64url_encode(raw) + "." + b64url_encode(signature)


# --- base64url ---------------------------------------------------------------


@pytest.mark.parametrize("data", [b"", b"\x00", b"ab", b"abc", bytes(range(256))])
def test_b64url_round_trip(data: bytes) -> None:
    encoded = b64url_encode(data)
    assert "=" not in encoded
    if data:
        assert b64url_decode(encoded) == data


@pytest.mark.parametrize(
    "text",
    ["", "QQ==", "QQ=", "Q", "QR", "a+b/", "a b", "QUJD\n", "QUJDé"],
)
def test_b64url_refuses_non_canonical(text: str) -> None:
    with pytest.raises(MalformedSignedObjectError):
        b64url_decode(text)


# --- JCS ---------------------------------------------------------------------


def test_canonicalize_sorts_keys_by_utf16_code_units() -> None:
    # U+1F600 is the surrogate pair D83D DE00, which sorts before U+FB01 in
    # UTF-16 although it is the larger code point.
    value = {"ﬁ": 1, "\U0001f600": 2, "b": 3, "a": [True, False, None]}
    assert canonicalize(value) == (
        '{"a":[true,false,null],"b":3,"\U0001f600":2,"ﬁ":1}'.encode()
    )


def test_canonicalize_escapes_like_jcs() -> None:
    assert canonicalize('"\\\b\f\n\r\t\x01\x7f é') == (
        '"\\"\\\\\\b\\f\\n\\r\\t\\u0001\x7f é"'.encode()
    )


@pytest.mark.parametrize(
    "value",
    [
        1.0,
        float("nan"),
        2**53,
        -(2**53),
        b"bytes",
        {1: "non-string key"},
        {"\ud800": 1},
        "\udfff",
        {"a": {"b": {"c": {"d": {}}}}},
        [[[[[]]]]],
        {1, 2},
    ],
)
def test_canonicalize_refuses(value: object) -> None:
    with pytest.raises(MalformedSignedObjectError):
        canonicalize(value)


def test_canonicalize_accepts_depth_four_and_range_edges() -> None:
    assert canonicalize({"a": {"b": {"c": [2**53 - 1, -(2**53 - 1)]}}}) == (
        b'{"a":{"b":{"c":[9007199254740991,-9007199254740991]}}}'
    )


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1,"a":1}',
        b'{"a":1.5}',
        b'{"a":1e3}',
        b'{"a":NaN}',
        b'{"a":-Infinity}',
        b'{"a":' + b"9" * 400 + b"}",
        b'{"a":9007199254740992}',
        b'{"a":"\\ud800"}',
        b'{"a":' + b"[" * 5000 + b"]" * 5000 + b"}",
        b'{"a":[[[[1]]]]}',
        b"\xff",
        b"\xef\xbb\xbf{}",
        b"{",
    ],
)
def test_parse_strict_refuses(raw: bytes) -> None:
    with pytest.raises(MalformedSignedObjectError):
        parse_strict(raw)


def test_parse_strict_accepts_plain_json() -> None:
    assert parse_strict(b'{"a":[1,"x",null,true]}') == {"a": [1, "x", None, True]}


# --- keys --------------------------------------------------------------------


def test_kid_is_truncated_sha256_of_the_raw_public_key() -> None:
    expected = b64url_encode(hashlib.sha256(PUBLIC).digest()[:16])
    assert KID == expected
    assert len(KID) == 22


def test_public_key_encoding_round_trips() -> None:
    assert decode_public_key(encode_public_key(PUBLIC)) == PUBLIC


@pytest.mark.parametrize("text", ["", "AAAA", encode_public_key(PUBLIC) + "=", "!"])
def test_decode_public_key_refuses(text: str) -> None:
    with pytest.raises(ValueError, match="public key"):
        decode_public_key(text)


@pytest.mark.parametrize("bad", [b"", b"\x00" * 31, b"\x00" * 33])
def test_key_lengths_are_exact(bad: bytes) -> None:
    for call in (derive_kid, encode_public_key, public_key_from_seed):
        with pytest.raises(ValueError, match="exactly"):
            call(bad)
    with pytest.raises(ValueError, match="exactly"):
        sign_bytes(bad, b"m")


def test_generated_seeds_are_fresh() -> None:
    first, second = generate_seed(), generate_seed()
    assert len(first) == 32
    assert first != second


def test_seed_file_round_trip_is_0600_and_exclusive(tmp_path: Path) -> None:
    path = tmp_path / "seed"
    write_seed_file(path, SEED)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert load_seed_file(path) == SEED
    with pytest.raises(FileExistsError):
        write_seed_file(path, SEED)
    with pytest.raises(ValueError, match="exactly"):
        write_seed_file(tmp_path / "short", b"short")


@pytest.mark.parametrize("content", [b"", b"x" * 31, b"x" * 33])
def test_load_seed_file_refuses_wrong_size(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "seed"
    path.write_bytes(content)
    with pytest.raises(ValueError, match="exactly 32"):
        load_seed_file(path)


def test_verify_bytes_refuses_bad_signatures() -> None:
    signature = sign_bytes(SEED, b"message")
    assert verify_bytes(PUBLIC, signature, b"message")
    assert not verify_bytes(PUBLIC, signature, b"other")
    assert not verify_bytes(PUBLIC, b"\x00" * 64, b"message")
    assert not verify_bytes(PUBLIC, signature[:10], b"message")


# --- signing -----------------------------------------------------------------


def test_signing_input_is_domain_nul_payload() -> None:
    assert signing_input(Domain.OCR_RECEIPT, b"{}") == b"m8.ai.ocr-receipt.v1\x00{}"
    with pytest.raises(ValueError, match="unknown signed-object domain"):
        signing_input("m8.other.v1", b"{}")


def test_compact_round_trip() -> None:
    token = sign_object(context_claims(), domain=Domain.JOB_CONTEXT, seed=SEED)
    payload_segment, _ = token.split(".")
    assert b64url_decode(payload_segment) == canonicalize(context_claims())
    assert _verify(token).model_dump() == context_claims()


def test_sign_object_accepts_a_model() -> None:
    model = Open.model_validate(context_claims())
    token = sign_object(model, domain="m8.ai.job-context.v1", seed=SEED)
    assert token == sign_object(context_claims(), domain=Domain.JOB_CONTEXT, seed=SEED)


@pytest.mark.parametrize(
    "claims",
    [
        {"v": None},
        {"v": True},
        {"v": "1"},
        {"typ": Domain.OCR_RECEIPT.value},
        {"kid": kid_of("ocr_receipt")},
        {"attempt": 1.5},
    ],
)
def test_sign_object_refuses_bad_payloads(claims: dict[str, object]) -> None:
    payload = context_claims(**claims)
    with pytest.raises(PayloadInvalidError):
        sign_object(payload, domain=Domain.JOB_CONTEXT, seed=SEED)


def test_sign_refuses_oversize_objects() -> None:
    big = context_claims(pad="x" * MAX_ENCODED_BYTES[Domain.JOB_CONTEXT])
    with pytest.raises(PayloadInvalidError, match="size cap"):
        sign_object(big, domain=Domain.JOB_CONTEXT, seed=SEED)
    with pytest.raises(PayloadInvalidError, match="size cap"):
        sign_record(big, domain=Domain.JOB_CONTEXT, seed=SEED)


def test_sign_refuses_an_unknown_domain() -> None:
    with pytest.raises(ValueError, match="unknown signed-object domain"):
        sign_object(context_claims(), domain="m8.other.v1", seed=SEED)


# --- verification ------------------------------------------------------------


def _record(**overrides: object) -> dict[str, object]:
    seed = seed_of("sandbox_attestation")
    record = sign_record(
        attestation_claims(), domain=Domain.SANDBOX_ATTESTATION, seed=seed
    )
    record.update(overrides)
    return record


def _verify_record(record: object) -> Open:
    public = public_key_from_seed(seed_of("sandbox_attestation"))
    return verify_object(
        record,  # type: ignore[arg-type]
        domain=Domain.SANDBOX_ATTESTATION,
        public_keys={derive_kid(public): public},
        model=Open,
    )


def test_record_round_trip() -> None:
    assert _verify_record(_record()).model_dump() == attestation_claims()


@pytest.mark.parametrize(
    "overrides",
    [
        {"extra": 1},
        {"record": ["not", "an", "object"]},
        {"sig": 7},
        {"kid": kid_of("job_context")},
        {"sig": "AA=="},
        {"record": {**attestation_claims(), "f": 1.5}},
        {"record": {**attestation_claims(), "pad": "x" * 33_000}},
    ],
)
def test_record_form_is_strict(overrides: dict[str, object]) -> None:
    with pytest.raises(MalformedSignedObjectError):
        _verify_record(_record(**overrides))


def test_record_form_refuses_a_missing_member() -> None:
    record = _record()
    del record["kid"]
    with pytest.raises(MalformedSignedObjectError):
        _verify_record(record)


def test_record_form_refuses_a_tampered_record() -> None:
    record = _record()
    record["record"] = {**attestation_claims(), "ordinal": 2}
    with pytest.raises(SignatureInvalidError):
        _verify_record(record)


@pytest.mark.parametrize("token", [None, 7, b"bytes", ["a", "b"]])
def test_verify_refuses_other_types(token: object) -> None:
    with pytest.raises(MalformedSignedObjectError):
        _verify(token)


def test_verify_refuses_a_non_object_payload() -> None:
    with pytest.raises(MalformedSignedObjectError, match="object"):
        _verify(_signed_raw([1, 2]))


def test_verify_refuses_a_short_signature() -> None:
    payload, _ = sign_object(
        context_claims(), domain=Domain.JOB_CONTEXT, seed=SEED
    ).split(".")
    with pytest.raises(MalformedSignedObjectError, match="64 bytes"):
        _verify(payload + "." + b64url_encode(b"\x00" * 32))


@pytest.mark.parametrize("kid", [None, 7, "unknown-kid-0000000000"])
def test_verify_refuses_a_missing_or_unknown_kid(kid: object) -> None:
    with pytest.raises(UnknownKeyError):
        _verify(_signed_raw(context_claims(kid=kid)))


def test_verify_ignores_a_key_that_does_not_derive_its_kid() -> None:
    token = sign_object(context_claims(), domain=Domain.JOB_CONTEXT, seed=SEED)
    other = public_key_from_seed(seed_of("ocr_receipt"))
    for keys in ({KID: other}, {KID: b"short"}):
        with pytest.raises(UnknownKeyError):
            verify_object(
                token, domain=Domain.JOB_CONTEXT, public_keys=keys, model=Open
            )


@pytest.mark.parametrize(
    "claims",
    [{"typ": Domain.OCR_RECEIPT.value}, {"typ": None}, {"v": None}],
)
def test_verify_requires_this_domains_typ_and_v(claims: dict[str, object]) -> None:
    payload = {k: v for k, v in context_claims(**claims).items() if v is not None}
    with pytest.raises(PayloadInvalidError, match="typ"):
        _verify(_signed_raw(payload))


def test_verify_refuses_a_cross_domain_signature() -> None:
    token = sign_object(context_claims(), domain=Domain.JOB_CONTEXT, seed=SEED)
    with pytest.raises(SignatureInvalidError):
        _verify(token, Domain.OCR_RECEIPT)


def test_oversize_is_refused_before_decoding() -> None:
    token = "!" * (MAX_ENCODED_BYTES[Domain.JOB_CONTEXT] + 1)
    with pytest.raises(MalformedSignedObjectError, match="size cap"):
        _verify(token)


@pytest.mark.parametrize(
    "raw", [b'{"a":1.5}', b'{"a":"x"', b'{"a":"' + b"[" * 3000 + b'"}']
)
def test_errors_never_carry_the_token(raw: bytes) -> None:
    token = raw_token(raw)
    with pytest.raises(SignedObjectError) as caught:
        _verify(token)
    error: BaseException | None = caught.value
    while error is not None:
        assert token not in str(error)
        assert raw.decode() not in str(error)
        error = None if error.__suppress_context__ else error.__context__
