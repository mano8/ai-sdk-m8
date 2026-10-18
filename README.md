# ai-sdk-m8

Typed client SDK for the m8 AI gateway (`ai-gateway-m8`) and the single
implementation of the Ed25519 signed-object rule with its job-context
primitive.

> Status: scaffold. The package imports and exposes `__version__` only; the
> client and job-context API land in later releases.

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
