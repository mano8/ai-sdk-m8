"""The shipped known-answer vectors: reproducible, and they mean what they say."""

import hashlib
from collections.abc import Mapping
from importlib import resources
from typing import cast

import pytest
import vectors_gen
from pydantic import BaseModel, ConfigDict, JsonValue

from ai_sdk_m8.jobcontext import (
    ContextInvalidError,
    JobContextPayload,
    OcrReceiptPayload,
    verify,
)
from ai_sdk_m8.signed import (
    Domain,
    MalformedSignedObjectError,
    PayloadInvalidError,
    SignatureInvalidError,
    SignedObjectError,
    UnknownKeyError,
    canonicalize,
    decode_public_key,
    derive_kid,
    public_key_from_seed,
    signing_input,
    verify_object,
)
from ai_sdk_m8.testing import VECTORS_RESOURCE, load_vectors


class Attestation(BaseModel):
    """Stand-in for C-10's record model, which ``media-sdk-m8`` owns."""

    model_config = ConfigDict(extra="allow", frozen=True)


VECTORS = load_vectors()
MODELS: dict[str, type[BaseModel]] = {
    Domain.JOB_CONTEXT.value: JobContextPayload,
    Domain.OCR_RECEIPT.value: OcrReceiptPayload,
    Domain.SANDBOX_ATTESTATION.value: Attestation,
}
ERRORS: dict[str, type[SignedObjectError]] = {
    "malformed": MalformedSignedObjectError,
    "unknown_key": UnknownKeyError,
    "signature": SignatureInvalidError,
    "payload": PayloadInvalidError,
}


def _cases(section: str) -> list[dict[str, JsonValue]]:
    cases = VECTORS[section]
    assert isinstance(cases, list)
    return [case for case in cases if isinstance(case, dict)]


def _registered_keys() -> dict[str, bytes]:
    keys = VECTORS["keys"]
    assert isinstance(keys, dict)
    out: dict[str, bytes] = {}
    for name, key in keys.items():
        assert isinstance(key, dict)
        if name != "unregistered":
            out[str(key["kid"])] = decode_public_key(str(key["public_key"]))
    return out


def test_shipped_file_is_reproducible() -> None:
    shipped = resources.files("ai_sdk_m8.testing").joinpath(VECTORS_RESOURCE)
    assert shipped.read_text("utf-8") == vectors_gen.build()


def test_every_domain_has_a_valid_vector() -> None:
    assert {case["domain"] for case in _cases("valid")} == {d.value for d in Domain}


def test_keys_derive_from_their_labels() -> None:
    keys = VECTORS["keys"]
    assert isinstance(keys, dict)
    for key in keys.values():
        assert isinstance(key, dict)
        seed = hashlib.sha256(str(key["seed_label"]).encode()).digest()
        public = public_key_from_seed(seed)
        assert decode_public_key(str(key["public_key"])) == public
        assert key["kid"] == derive_kid(public)


@pytest.mark.parametrize("case", _cases("valid"), ids=lambda c: str(c["name"]))
def test_valid_vector_verifies_under_its_own_domain_only(
    case: dict[str, JsonValue],
) -> None:
    domain = str(case["domain"])
    assert isinstance(case["signed"], str | dict)
    signed = cast("str | Mapping[str, object]", case["signed"])
    payload = case["payload"]
    digest = hashlib.sha256(signing_input(domain, canonicalize(payload))).hexdigest()
    assert case["signing_input_sha256"] == digest
    keys = _registered_keys()
    verified = verify_object(
        signed, domain=domain, public_keys=keys, model=MODELS[domain]
    )
    assert verified.model_dump(mode="json", exclude_none=True) == payload
    for other in Domain:
        if other.value != domain:
            with pytest.raises(SignedObjectError):
                verify_object(signed, domain=other, public_keys=keys, model=Attestation)


def test_context_vectors_pass_the_job_context_verifier() -> None:
    for case in _cases("valid"):
        if case["domain"] == Domain.JOB_CONTEXT.value:
            now = VECTORS["now"]
            assert isinstance(now, int)
            verify(
                str(case["signed"]),
                public_keys=_registered_keys(),
                aud=str(VECTORS["audience"]),
                now=now,
                max_ttl=900,
                skew=5,
            )


@pytest.mark.parametrize("case", _cases("invalid"), ids=lambda c: str(c["name"]))
def test_invalid_vector_fails_at_its_stage(case: dict[str, JsonValue]) -> None:
    keys = _registered_keys()
    with pytest.raises(ERRORS[str(case["error"])]):
        verify_object(
            str(case["signed"]),
            domain=str(case["domain"]),
            public_keys=keys,
            model=JobContextPayload,
        )
    now = VECTORS["now"]
    assert isinstance(now, int)
    with pytest.raises(ContextInvalidError):
        verify(
            str(case["signed"]),
            public_keys=keys,
            aud=str(VECTORS["audience"]),
            now=now,
            max_ttl=900,
            skew=5,
        )
