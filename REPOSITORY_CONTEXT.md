# ai-sdk-m8

## Layer

Platform (AI SDK).

## Purpose

Provide the small typed client SDK for the AI gateway (`ai-gateway-m8`) and
the one implementation of the Ed25519 signed-object rule with its job-context
primitive. Services and document tools that call the gateway, or that sign or
verify job contexts, depend on this package instead of re-implementing either.

The package is published to PyPI as `ai-sdk-m8` and imported as `ai_sdk_m8`.

## Repository boundaries

- Core dependencies are limited to Pydantic v2 and `httpx`. Signing and
  verification live behind the `jobcontext` extra, which adds `cryptography`.
- This is the only implementation of the signed-object rule. Consumers call
  it; they do not carry their own copy.
- Do not add Vault, SQLAlchemy, provider SDKs, or `auth-sdk-m8` dependencies.
- The SDK holds no provider credentials and reads no settings or environment
  variables; callers pass explicit configuration.
- CI, tests, and documentation work from a lone clone: no sibling checkout,
  workspace path, or parent-only tool is referenced.

These are repository architecture constraints. If a requested change appears to
break one, record the decision in the workspace context when that optional
enhancement is available and confirm the exception before proceeding.

## Standalone authority

This file, `pyproject.toml`, repository documentation, and existing CI are the
authoritative local context. A verified nearest workspace may optionally add
launcher-selected policies and tasks; its absence is a successful standalone
condition and does not make a parent workspace necessary.
