"""
Transport-independent core of the sync and async clients.

An operation is described once as a :class:`Call`; the two clients only
differ in how they send it. Every request is sent with redirects refused,
whatever the injected ``httpx`` client was configured with, because httpx
strips ``Authorization`` on a cross-origin redirect but not
``X-Internal-Token`` or ``X-AI-Job-Context``.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import IO, Final
from urllib.parse import quote, urlsplit
from uuid import UUID

import httpx
from pydantic import BaseModel, TypeAdapter, ValidationError

from ai_sdk_m8._client_errors import (
    AiGatewayHTTPError,
    AiGatewayRedirectError,
    AiGatewayResponseError,
)
from ai_sdk_m8.client._auth import Auth, BearerJwt, ServiceClient
from ai_sdk_m8.client.routes import Route
from ai_sdk_m8.headers import JOB_CONTEXT_HEADER
from ai_sdk_m8.jobcontext import JobContextToken
from ai_sdk_m8.schemas.errors import AiError, AiGatewayError

#: The type of the per-call ``job_context`` argument.
JobContext = JobContextToken

#: Largest job context the gateway accepts (C-03).
JOB_CONTEXT_MAX_BYTES: Final = 4096

_COMPACT: Final = re.compile(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
_PROFILE_KEY: Final = re.compile(r"[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?")

#: Default timeout of a client the SDK builds itself, in seconds.
DEFAULT_TIMEOUT_SECONDS: Final = 30.0


class AuthKind(Enum):
    """Which strategy an operation accepts."""

    NONE = "none"
    SERVICE = "service"
    JWT = "jwt"
    SERVICE_OR_JWT = "service_or_jwt"


@dataclass(frozen=True)
class Call[T]:
    """One operation: route, path values, body and how to read the answer."""

    route: Route
    auth: AuthKind
    parse: Callable[[bytes], T]
    params: Mapping[str, str] = field(default_factory=dict)
    json: object | None = None
    files: list[tuple[str, tuple[str | None, object, str]]] | None = None
    query: Mapping[str, str] | None = None
    job_context: JobContextToken | None = field(default=None, repr=False)


def normalise_base_url(base_url: str) -> str:
    """Return ``base_url`` without a trailing slash, refusing unsafe forms."""
    if not isinstance(base_url, str):
        raise TypeError("base_url must be a string")
    parts = urlsplit(base_url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("base_url must be an absolute http or https URL")
    if parts.username is not None or parts.password is not None:
        raise ValueError("base_url must not carry credentials")
    if parts.query or parts.fragment:
        raise ValueError("base_url must not carry a query or a fragment")
    return base_url.rstrip("/")


def require_job_context(job_context: object) -> JobContextToken:
    """
    Return ``job_context`` as a token, or raise ``ValueError``.

    The message never contains the value.
    """
    if not isinstance(job_context, str) or not job_context:
        raise ValueError("job_context is required for every execution call")
    if len(job_context) > JOB_CONTEXT_MAX_BYTES or not _COMPACT.fullmatch(job_context):
        raise ValueError("job_context is not a compact signed object")
    if isinstance(job_context, JobContextToken):
        return job_context
    return JobContextToken(job_context)


def uuid_param(value: UUID | str, what: str) -> str:
    """A path parameter that must be a UUID."""
    try:
        return str(value if isinstance(value, UUID) else UUID(str(value)))
    except ValueError:
        raise ValueError(f"{what} must be a UUID") from None


def profile_key_param(value: str) -> str:
    """A path parameter that must be a profile key."""
    if not isinstance(value, str) or not _PROFILE_KEY.fullmatch(value):
        raise ValueError("profile_key is not a valid profile key")
    return value


def model_parser[M: BaseModel](model: type[M]) -> Callable[[bytes], M]:
    """Parse a JSON body into ``model``."""

    def parse(content: bytes) -> M:
        return model.model_validate_json(content)

    return parse


def list_parser[T](model: type[T]) -> Callable[[bytes], tuple[T, ...]]:
    """Parse a JSON array body into a tuple of ``model``."""
    adapter = TypeAdapter(tuple[model, ...])  # type: ignore[valid-type]

    def parse(content: bytes) -> tuple[T, ...]:
        parsed: tuple[T, ...] = adapter.validate_json(content)
        return parsed

    return parse


def no_content(_content: bytes) -> None:
    """Accept any body of a 2xx answer that carries no model."""
    return None


def _auth_headers(auth: Auth | None, kind: AuthKind) -> dict[str, str]:
    if kind is AuthKind.NONE:
        return {}
    if kind is AuthKind.SERVICE and not isinstance(auth, ServiceClient):
        raise TypeError("execution routes accept a ServiceClient only")
    if kind is AuthKind.JWT and not isinstance(auth, BearerJwt):
        raise TypeError("management routes accept a BearerJwt only")
    if auth is None:
        raise TypeError("this route needs a BearerJwt or a ServiceClient")
    return auth.headers()


def build_request(
    client: httpx.Client | httpx.AsyncClient,
    base_url: str,
    auth: Auth | None,
    call: Call[object],
) -> httpx.Request:
    """Build the ``httpx.Request`` of ``call``."""
    path = call.route.path.format_map(
        {key: quote(value, safe="") for key, value in call.params.items()}
    )
    headers = {"Accept": "application/json"}
    headers |= _auth_headers(auth, call.auth)
    if call.job_context is not None:
        headers[JOB_CONTEXT_HEADER] = str(call.job_context)
    return client.build_request(
        call.route.method,
        f"{base_url}/{path}",
        headers=headers,
        json=call.json,
        files=call.files,  # type: ignore[arg-type]
        params=call.query,
    )


def parse_response[T](call: Call[T], response: httpx.Response) -> T:
    """Read ``response`` as the answer to ``call`` or raise a typed error."""
    status = response.status_code
    if 300 <= status < 400:
        raise AiGatewayRedirectError(status)
    if not 200 <= status < 300:
        try:
            error = AiError.model_validate_json(response.content)
        except ValidationError:
            raise AiGatewayHTTPError(status) from None
        raise AiGatewayError(error)
    try:
        return call.parse(response.content)
    except ValidationError:
        raise AiGatewayResponseError from None


def multipart_document(
    options_json: bytes, document: IO[bytes]
) -> list[tuple[str, tuple[str | None, object, str]]]:
    """
    The two OCR parts in their required order: ``options`` then ``document``.

    The file name is fixed, so the original one never leaves the caller, and
    httpx reads ``document`` in chunks while sending.
    """
    return [
        ("options", (None, options_json, "application/json")),
        ("document", ("document", document, "application/octet-stream")),
    ]


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "JOB_CONTEXT_MAX_BYTES",
    "AuthKind",
    "Call",
    "JobContext",
    "build_request",
    "list_parser",
    "model_parser",
    "multipart_document",
    "no_content",
    "normalise_base_url",
    "parse_response",
    "profile_key_param",
    "require_job_context",
    "uuid_param",
]
