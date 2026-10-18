"""
Wire header names of the gateway's execution routes (contract C-02).

The two service-client names are owned by ``auth-sdk-m8``
(``INTERNAL_CLIENT_HEADER`` / ``INTERNAL_TOKEN_HEADER``), which the gateway
reaches through ``fastapi-m8``. This package does not depend on either; it
mirrors the two values, and a parity test fails if either fleet value
changes. There are no on-behalf-of headers.
"""

from typing import Final

#: Service-client identifier, mirrored from ``auth-sdk-m8``.
INTERNAL_CLIENT_HEADER: Final = "X-Internal-Client"

#: Service-client secret, mirrored from ``auth-sdk-m8``.
INTERNAL_TOKEN_HEADER: Final = "X-Internal-Token"

#: Compact signed job context, one per execution call.
JOB_CONTEXT_HEADER: Final = "X-AI-Job-Context"

__all__ = ["INTERNAL_CLIENT_HEADER", "INTERNAL_TOKEN_HEADER", "JOB_CONTEXT_HEADER"]
