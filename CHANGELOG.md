# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-10-18

### Added

- `ai_sdk_m8.schemas`: the gateway's frozen, closed Pydantic v2 models —
  capability, data-class, boundary and identity-assurance vocabularies;
  `ProfilePublic`; OCR, embedding, rerank and structured-output requests,
  results and responses; `ExecutionReceipt` with the OCR-only signed
  `receipt`; `AiError` with a closed `AiErrorCode` and bounded
  `provider_metadata`; `AiGatewayError`.
- `ai_sdk_m8.headers`: `INTERNAL_CLIENT_HEADER`, `INTERNAL_TOKEN_HEADER` and
  `JOB_CONTEXT_HEADER`, with a parity test against the fleet values.

## [0.1.0] - 2026-10-18

### Added

- Repository scaffold: hatchling packaging, empty `ai_sdk_m8` package with
  `__version__`, ruff / mypy strict / bandit / pip-audit / pytest (100%
  coverage) CI, PyPI Trusted Publishing release workflow with an SPDX SBOM
  attached to the GitHub Release, Dependabot, Codacy and gitleaks
  configuration.
