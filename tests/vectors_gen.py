"""
Generator of ``ai_sdk_m8/testing/vectors.json``.

Ed25519 signatures are deterministic, so the same seeds and payloads always
produce the same file; ``test_vectors`` regenerates it and byte-compares.
Run ``python tests/vectors_gen.py`` to rewrite the shipped file.
"""

import hashlib
import json
from pathlib import Path

from ai_sdk_m8.signed import (
    Domain,
    b64url_encode,
    canonicalize,
    derive_kid,
    encode_public_key,
    public_key_from_seed,
    sign_object,
    sign_record,
    signing_input,
)
from ai_sdk_m8.signed._keys import sign_bytes

OUT = Path(__file__).resolve().parents[1] / "ai_sdk_m8" / "testing" / "vectors.json"

DEPLOYMENT = "0b6f3c1e-5a2d-4e8f-9c71-2d4a6b8e0f13"
AUD = f"ai-gateway/{DEPLOYMENT}"
NOW = 1_800_000_000

KEYS = {
    "job_context": "ai-sdk-m8 test vector seed: job-context",
    "ocr_receipt": "ai-sdk-m8 test vector seed: ocr-receipt",
    "sandbox_attestation": "ai-sdk-m8 test vector seed: sandbox-attestation",
    "unregistered": "ai-sdk-m8 test vector seed: unregistered",
}
DOMAINS = {
    "job_context": Domain.JOB_CONTEXT,
    "ocr_receipt": Domain.OCR_RECEIPT,
    "sandbox_attestation": Domain.SANDBOX_ATTESTATION,
}


def seed_of(name: str) -> bytes:
    return hashlib.sha256(KEYS[name].encode("utf-8")).digest()


def kid_of(name: str) -> str:
    return derive_kid(public_key_from_seed(seed_of(name)))


def context_claims(**claims: object) -> dict[str, object]:
    base: dict[str, object] = {
        "v": 1,
        "typ": Domain.JOB_CONTEXT.value,
        "kid": kid_of("job_context"),
        "iss": "media-service",
        "aud": AUD,
        "azp": "media-worker",
        "tenant_id": "tenant-01",
        "data_class": "internal",
        "capability": "embedding",
        "profile_key": "embed-default",
        "job_ref": "run-7d2c",
        "attempt": 1,
        "jti": "5d1e0c4a-3b7f-4a29-8e61-0c9f2b7d4a10",
        "iat": NOW,
        "nbf": NOW,
        "exp": NOW + 600,
        "max_uses": 1,
    }
    base.update(claims)
    return base


OCR_CLAIMS = {
    "capability": "ocr",
    "profile_key": "ocr-default",
    "input_sha256": "a" * 64,
    "input_bytes": 182_044,
    "ocr_options_hash": "b" * 64,
    "allowed_boundaries": ["local", "external"],
}


def receipt_claims() -> dict[str, object]:
    return {
        "v": 1,
        "typ": Domain.OCR_RECEIPT.value,
        "kid": kid_of("ocr_receipt"),
        "iss": AUD,
        "execution_id": "9a4e2f71-6c3b-4d58-a0e9-1b7c5d3f8e26",
        "capability": "ocr",
        "job_ref": "run-7d2c",
        "attempt": 1,
        "azp": "media-worker",
        "profile_key": "ocr-default",
        "input_sha256": "a" * 64,
        "ocr_options_hash": "b" * 64,
        "execution_identity": "c" * 32,
        "result_sha256": "d" * 64,
        "produced_at": NOW + 42,
    }


def attestation_claims() -> dict[str, object]:
    return {
        "v": 1,
        "typ": Domain.SANDBOX_ATTESTATION.value,
        "kid": kid_of("sandbox_attestation"),
        "parent": {"type": "document_run", "id": "run-7d2c", "attempt": 1},
        "invocation_id": "3c8b1d2e-7f4a-4b6c-9d0e-5a1f2b3c4d5e",
        "ordinal": 1,
        "kind": "parse",
        "inputs": [{"name": "in.pdf", "size_bytes": 182_044, "sha256": "a" * 64}],
        "outputs": [
            {"name": "document.v1.json.gz", "size_bytes": 9_310, "sha256": "e" * 64}
        ],
        "claimed_at": NOW,
        "completed_at": NOW + 7,
        "produced_at": NOW,
    }


def _valid() -> list[dict[str, object]]:
    contexts = {
        "job_context_embedding": context_claims(),
        "job_context_ocr_spool": context_claims(**OCR_CLAIMS, phase="spool"),
        "job_context_ocr_dispatch": context_claims(
            **OCR_CLAIMS,
            phase="dispatch",
            spool_id="7e2a9c41-0d5b-4f63-8a17-c4e9b2d06f58",
            jti="2f9a7c13-8e4d-4b05-9a6f-3d1c7e8b0a24",
            exp=NOW + 30,
        ),
    }
    vectors: list[dict[str, object]] = []
    for name, payload in contexts.items():
        vectors.append(_compact(name, "job_context", payload))
    vectors.append(_compact("ocr_receipt", "ocr_receipt", receipt_claims()))
    record = sign_record(
        attestation_claims(),
        domain=Domain.SANDBOX_ATTESTATION,
        seed=seed_of("sandbox_attestation"),
    )
    vectors.append(
        {
            "name": "sandbox_attestation",
            "key": "sandbox_attestation",
            "domain": Domain.SANDBOX_ATTESTATION.value,
            "form": "record",
            "payload": attestation_claims(),
            "signing_input_sha256": _input_digest(
                Domain.SANDBOX_ATTESTATION, attestation_claims()
            ),
            "signed": record,
        }
    )
    return vectors


def _input_digest(domain: Domain, payload: dict[str, object]) -> str:
    return hashlib.sha256(signing_input(domain, canonicalize(payload))).hexdigest()


def _compact(name: str, key: str, payload: dict[str, object]) -> dict[str, object]:
    domain = DOMAINS[key]
    return {
        "name": name,
        "key": key,
        "domain": domain.value,
        "form": "compact",
        "payload": payload,
        "signing_input_sha256": _input_digest(domain, payload),
        "signed": sign_object(payload, domain=domain, seed=seed_of(key)),
    }


def raw_token(raw_payload: bytes, *, key: str = "job_context") -> str:
    """A token over arbitrary payload bytes, validly signed."""
    signature = sign_bytes(seed_of(key), signing_input(Domain.JOB_CONTEXT, raw_payload))
    return b64url_encode(raw_payload) + "." + b64url_encode(signature)


def _flip_last(segment: str) -> str:
    return segment[:-1] + ("A" if segment[-1] != "A" else "B")


def _invalid() -> list[dict[str, object]]:
    good = sign_object(
        context_claims(), domain=Domain.JOB_CONTEXT, seed=seed_of("job_context")
    )
    payload_seg, sig_seg = good.split(".")
    canonical = json.dumps(context_claims(), sort_keys=True, separators=(",", ":"))
    deep = context_claims(job_ref={"a": {"b": {"c": {"d": 1}}}})
    cases: list[tuple[str, str, str]] = [
        ("padded_base64url", good + "==", "malformed"),
        ("non_alphabet_character", payload_seg + "+." + sig_seg, "malformed"),
        ("three_segments", good + ".AA", "malformed"),
        (
            "signature_nonzero_trailing_bits",
            payload_seg + "." + sig_seg[:-1] + "x",
            "malformed",
        ),
        ("oversize_5kib", raw_token(b'{"pad":"' + b"x" * 5000 + b'"}'), "malformed"),
        (
            "non_canonical_whitespace",
            raw_token(json.dumps(context_claims(), sort_keys=True).encode()),
            "malformed",
        ),
        (
            "non_canonical_key_order",
            raw_token(json.dumps(context_claims(), separators=(",", ":")).encode()),
            "malformed",
        ),
        (
            "non_canonical_escape",
            raw_token(canonical.replace('"run-7d2c"', '"\\u0072un-7d2c"').encode()),
            "malformed",
        ),
        (
            "duplicate_key",
            raw_token(canonical.replace('"aud":', '"attempt":2,"aud":', 1).encode()),
            "malformed",
        ),
        (
            "float",
            raw_token(canonical.replace('"attempt":1', '"attempt":1.0').encode()),
            "malformed",
        ),
        (
            "integer_out_of_range",
            raw_token(
                canonical.replace('"attempt":1', '"attempt":9007199254740992').encode()
            ),
            "malformed",
        ),
        (
            "lone_surrogate",
            raw_token(canonical.replace('"run-7d2c"', '"\\ud800"').encode()),
            "malformed",
        ),
        (
            "depth_5",
            raw_token(json.dumps(deep, sort_keys=True, separators=(",", ":")).encode()),
            "malformed",
        ),
        (
            "tampered_payload",
            b64url_encode(canonical.replace("run-7d2c", "run-7d2d").encode())
            + "."
            + sig_seg,
            "signature",
        ),
        (
            "tampered_signature",
            payload_seg
            + "."
            + sig_seg[:20]
            + _flip_last(sig_seg[20:22])
            + sig_seg[22:],
            "signature",
        ),
        (
            "unknown_kid",
            sign_object(
                context_claims(kid=kid_of("unregistered")),
                domain=Domain.JOB_CONTEXT,
                seed=seed_of("unregistered"),
            ),
            "unknown_key",
        ),
        (
            "kid_of_other_key",
            raw_token(canonical.encode(), key="ocr_receipt"),
            "signature",
        ),
        (
            "max_uses_2",
            sign_object(
                context_claims(max_uses=2),
                domain=Domain.JOB_CONTEXT,
                seed=seed_of("job_context"),
            ),
            "payload",
        ),
        (
            "unknown_claim",
            sign_object(
                context_claims(extra="x"),
                domain=Domain.JOB_CONTEXT,
                seed=seed_of("job_context"),
            ),
            "payload",
        ),
        (
            "unknown_version",
            sign_object(
                context_claims(v=2),
                domain=Domain.JOB_CONTEXT,
                seed=seed_of("job_context"),
            ),
            "payload",
        ),
        (
            "null_claim",
            sign_object(
                context_claims(user_id=None),
                domain=Domain.JOB_CONTEXT,
                seed=seed_of("job_context"),
            ),
            "payload",
        ),
    ]
    return [
        {
            "name": name,
            "key": "job_context",
            "domain": Domain.JOB_CONTEXT.value,
            "form": "compact",
            "signed": token,
            "error": error,
        }
        for name, token, error in cases
    ]


def build() -> str:
    keys = {
        name: {
            "seed_label": label,
            "public_key": encode_public_key(public_key_from_seed(seed_of(name))),
            "kid": kid_of(name),
        }
        for name, label in KEYS.items()
    }
    document = {
        "format": 1,
        "description": (
            "C-03 signed-object known-answer vectors. seed = "
            "SHA-256(UTF-8(seed_label)); public test values that authorise "
            "nothing. Valid vectors verify only under their own domain; every "
            "cross-domain substitution must fail. Each invalid vector names "
            "the stage that refuses it under the job-context domain: "
            "malformed (before any signature work), unknown_key, signature, "
            "payload (closed model)."
        ),
        "audience": AUD,
        "now": NOW,
        "domains": {name: domain.value for name, domain in DOMAINS.items()},
        "keys": keys,
        "valid": _valid(),
        "invalid": _invalid(),
    }
    return json.dumps(document, indent=2, ensure_ascii=True) + "\n"


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8", newline="\n")
