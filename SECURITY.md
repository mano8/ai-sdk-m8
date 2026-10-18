# Security

`ai-sdk-m8` is a client SDK and signing primitive. It holds no provider
credentials, reads no settings or environment variables, and makes no
decision on behalf of the gateway: provider and data-class policy is enforced
by `ai-gateway-m8`.

## Supply chain

- Releases are published to PyPI only through Trusted Publishing (OIDC); no
  upload token is stored anywhere.
- Every release attaches a Software Package Data Exchange (SPDX) JSON software
  bill of materials (SBOM) to its GitHub Release.
- CI actions are pinned by full Secure Hash Algorithm (SHA) commit hash and
  run with read-only default permissions.
- `pip-audit` and `bandit` run on every pull request.

## Reporting a vulnerability

Report security vulnerabilities privately through GitHub's **Security** tab on
this repository — **"Report a vulnerability"** — which opens a private
security advisory visible only to the maintainers. Do not open a public GitHub
issue for vulnerabilities. Expected response within 48 h.
