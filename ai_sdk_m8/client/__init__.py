"""
Typed clients of the AI gateway (sync and async).

Service identity is client state; a job context never is. Every execution
method takes a required keyword ``job_context`` for that one call::

    from ai_sdk_m8.client import AiGatewayClient, ServiceClient

    with AiGatewayClient(base_url, ServiceClient("media-service", secret)) as gw:
        answer = gw.embed(request, job_context=token)

Management routes use :class:`BearerJwt` and the ``client.admin`` namespace.
Redirects are never followed and nothing is retried.
"""

from ai_sdk_m8._client_errors import (
    AiGatewayClientError,
    AiGatewayHTTPError,
    AiGatewayRedirectError,
    AiGatewayResponseError,
    IncompatibleGatewayError,
)
from ai_sdk_m8.client._admin import Admin, AsyncAdmin
from ai_sdk_m8.client._auth import Auth, BearerJwt, ServiceClient
from ai_sdk_m8.client._clients import AiGatewayClient, AsyncAiGatewayClient
from ai_sdk_m8.client._core import JOB_CONTEXT_MAX_BYTES, JobContext

__all__ = [
    "JOB_CONTEXT_MAX_BYTES",
    "Admin",
    "AiGatewayClient",
    "AiGatewayClientError",
    "AiGatewayHTTPError",
    "AiGatewayRedirectError",
    "AiGatewayResponseError",
    "AsyncAdmin",
    "AsyncAiGatewayClient",
    "Auth",
    "BearerJwt",
    "IncompatibleGatewayError",
    "JobContext",
    "ServiceClient",
]
