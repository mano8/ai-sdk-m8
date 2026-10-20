"""C-02 header names and their parity with the fleet values."""

import importlib.util

import pytest

from ai_sdk_m8.headers import (
    INTERNAL_CLIENT_HEADER,
    INTERNAL_TOKEN_HEADER,
    JOB_CONTEXT_HEADER,
)

#: The fleet values owned by ``auth-sdk-m8``; a change there must fail here.
FLEET_CLIENT_HEADER = "X-Internal-Client"
FLEET_TOKEN_HEADER = "X-Internal-Token"  # nosec B105 — header name


def test_service_client_headers_mirror_fleet_values() -> None:
    assert INTERNAL_CLIENT_HEADER == FLEET_CLIENT_HEADER
    assert INTERNAL_TOKEN_HEADER == FLEET_TOKEN_HEADER


def test_job_context_header() -> None:
    assert JOB_CONTEXT_HEADER == "X-AI-Job-Context"


@pytest.mark.skipif(
    importlib.util.find_spec("auth_sdk_m8") is None,
    reason="auth-sdk-m8 is not installed; the literal parity above still applies",
)
def test_parity_with_installed_auth_sdk() -> None:
    from auth_sdk_m8.security.consumer_auth import (  # type: ignore[import-not-found]
        INTERNAL_CLIENT_HEADER as AUTH_CLIENT,
    )
    from auth_sdk_m8.security.consumer_auth import (
        INTERNAL_TOKEN_HEADER as AUTH_TOKEN,
    )

    assert (AUTH_CLIENT, AUTH_TOKEN) == (INTERNAL_CLIENT_HEADER, INTERNAL_TOKEN_HEADER)
