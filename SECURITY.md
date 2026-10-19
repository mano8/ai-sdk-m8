# Security

`ai-sdk-m8` is a client SDK and signing primitive. It holds no provider
credentials, reads no settings or environment variables, and makes no
decision on behalf of the gateway: provider and data-class policy is enforced
by `ai-gateway-m8`.

## Signed objects

- One composition, Ed25519 over `domain_tag || 0x00 || JCS(payload)`, serves
  every signature purpose. Each purpose has its own key, and the verifier
  always names the domain it expects.
- Untrusted input is size-capped and strictly parsed before any signature
  work. Errors and `repr` never contain a token, a seed or a signature.
- Seed files are created `0600` with `O_EXCL`; `keygen` never prints a seed.
- The shipped vector seeds are public test values and must never sign
  anything in a deployment.

## Gateway clients

- A job context is passed to the one call it authorises and is never stored
  on the client.
- Redirects are refused on every request, so `X-Internal-Token` and
  `X-AI-Job-Context` can never be forwarded to another origin.
- An SDK-built `httpx` client ignores proxy environment variables.
- Errors and `repr` never contain a service secret, a user token or a job
  context.
- OCR documents are sent under a fixed file name, so the original file name
  never leaves the caller.

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
