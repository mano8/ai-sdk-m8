# Security

`ai-sdk-m8` is a client SDK and signing primitive. It holds no provider
credentials, reads no settings or environment variables, and makes no
decision on behalf of the gateway: provider and data-class policy is enforced
by `ai-gateway-m8`.

## Signed objects

- One composition, Ed25519 over `domain_tag || 0x00 || JCS(payload)`, serves
  every signature purpose. Each purpose has its own key, and the domain
  comes from the verifier's argument, not from the signed object.
- Untrusted input is size-capped and strictly parsed before any signature
  work. Errors and `repr` contain no token, seed or signature.
- Seed files are created `0600` with `O_EXCL`; `keygen` prints the `kid` and
  the public key, not the seed.
- The shipped vector seeds are public test values. Signing with them in a
  deployment is a misconfiguration.

## Gateway clients

- A job context is passed to the one call it authorises; the client keeps no
  reference to it.
- Redirects are refused on every request, so `X-Internal-Token` and
  `X-AI-Job-Context` are not forwarded to another origin.
- An SDK-built `httpx` client ignores proxy environment variables.
- Errors and `repr` contain no service secret, user token or job context.
- Optical character recognition (OCR) documents are sent under a fixed file
  name, so the original file name stays with the caller.

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
