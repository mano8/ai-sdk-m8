# ai-sdk-m8

Typed client SDK for the m8 AI gateway (`ai-gateway-m8`) and the single
implementation of the Ed25519 signed-object rule with its job-context
primitive.

> Status: pre-release. The gateway schemas and header names are in place; the
> job-context primitive and the clients land in later releases.

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

## Install

```bash
pip install ai-sdk-m8
# signing and verification of job contexts
pip install "ai-sdk-m8[jobcontext]"
```

Core dependencies are limited to Pydantic v2 and `httpx`; `cryptography` is
only installed with the `jobcontext` extra. The SDK holds no provider
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
