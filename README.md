# ai-sdk-m8

Typed client SDK for the m8 AI gateway (`ai-gateway-m8`) and the single
implementation of the Ed25519 signed-object rule with its job-context
primitive.

> Status: pre-release. The gateway schemas, header names, the signed-object
> rule and the job-context primitive are in place; the clients land in a later
> release.

## Schemas

`ai_sdk_m8.schemas` holds the gateway's request, result and error models:
frozen Pydantic v2 models that refuse unknown fields, NaN and infinity, and
perform no I/O at import.

- `Capability`, `DataClass`, `ProviderBoundary`, `IdentityAssurance`.
- `ProfilePublic` — a profile as readers see it, never credentials or
  `base_url`.
- `OcrRequest` / `OcrSpoolResult` / `OcrResult` / `OcrResponse`,
  `EmbedRequest` / `EmbedResult` / `EmbedResponse`,
  `RerankRequest` / `RerankResult` / `RerankResponse`,
  `StructuredOutputRequest` / `StructuredOutputResult` /
  `StructuredOutputResponse`.
- `ExecutionReceipt` — admission `units`, provider-reported usage, the
  resolved model identity and, for OCR only, the signed provenance
  `receipt`.
- `AiError` (closed `AiErrorCode`, opaque `request_id`, provider status class,
  bounded `provider_metadata`) and the `AiGatewayError` exception.

`OcrResult` is float-free (integer pixels, integer basis points), so its
canonical JSON is defined under the integer-only rule that the provenance
receipt's `result_sha256` covers.

`ai_sdk_m8.headers` names the wire headers: `INTERNAL_CLIENT_HEADER`,
`INTERNAL_TOKEN_HEADER` (the fleet's service-client names) and
`JOB_CONTEXT_HEADER`.

## Signed objects and job contexts

Behind the `jobcontext` extra. Importing either module needs no extra; using
a key without it raises `MissingExtraError`.

`ai_sdk_m8.signed` is the one implementation of the signed-object rule that
job contexts, OCR execution receipts and sandbox attestations share:

- signed bytes are `UTF-8(domain_tag) || 0x00 || JCS(payload)`, signed with
  Ed25519. JCS is RFC 8785 restricted to integers;
- the verifier names the one `Domain` it expects. A receipt or attestation
  presented as a job context fails, and so does every other pairing;
- the compact form is `b64url(JCS(payload)) "." b64url(sig)` (headers and
  receipts). The structured form is `{record, kid, sig}` (attestations);
- parsing runs before any trust is placed in the object. It checks:
  - the size cap: 4 KiB for contexts and receipts, 32 KiB for attestations;
  - strict unpadded base64url;
  - JSON without duplicate keys, floats, integers beyond ±(2⁵³−1), lone
    surrogates or nesting deeper than 4;
  - that the payload is byte-identical to its re-canonicalised form.

  The signature is checked next, and the closed payload model last;
- `kid` is the unpadded base64url of the first 16 bytes of SHA-256 over the
  raw 32-byte public key.

```python
from ai_sdk_m8.signed import Domain, sign_object, verify_object

token = sign_object(payload, domain=Domain.OCR_RECEIPT, seed=seed)
receipt = verify_object(
    token, domain=Domain.OCR_RECEIPT, public_keys=keys, model=OcrReceiptPayload
)
```

`ai_sdk_m8.jobcontext` builds the single-use job context on top of it:

- `JobContextPayload` is the closed claim model. `max_uses` is always 1. For
  `capability = ocr`, `phase` and the input claims are mandatory, and
  `spool_id` is present exactly in the `dispatch` phase;
- `sign(payload, *, seed)` returns a `JobContextToken`, a `str` whose `repr`
  redacts the signature;
- `verify(token, *, public_keys, aud, now, max_ttl, skew)` checks the rule,
  the model, `aud`, the clock and the TTL caps. `iat` and `nbf` may lead
  `now` by `skew`; `exp` gets no leeway; a `dispatch` context is capped at
  30 s by default. A refusal raises `ContextInvalidError` or
  `ContextExpiredError`, whose `code` is the gateway's error code and whose
  message never contains the token. The gateway still checks the issuer,
  the presenter, the scopes and the request binding, and redeems `jti`;
- `OcrReceiptPayload` is the gateway's signed OCR provenance receipt.

Generate a key with:

```bash
python -m ai_sdk_m8.jobcontext keygen --out ./job-context.seed
```

This creates the file with mode `0600` and never overwrites an existing
one. It holds the raw 32-byte seed. The command prints `kid=` and
`public_key=` (unpadded base64url) and never prints the seed.

`ai_sdk_m8.testing.load_vectors()` returns the shipped known-answer vectors
for all three domains: the valid objects and an invalid case for each
refusal stage. Consumers test against the installed package. The vector
seeds are public test values.

## Install

```bash
pip install ai-sdk-m8
# signing and verification of job contexts
pip install "ai-sdk-m8[jobcontext]"
```

Core dependencies are limited to Pydantic v2 and `httpx`; `cryptography` is
only installed with the `jobcontext` extra, and the core package imports
without it. The SDK holds no provider
credentials and reads no environment variables.

## Development

```bash
pip install -e ".[dev,jobcontext]"
ruff format --check . && ruff check .
mypy ai_sdk_m8
bandit -r ai_sdk_m8 --severity-level medium
pytest --cov-fail-under=100
```

## License

MIT — see [LICENSE](LICENSE).
