"""
Closed, typed gateway errors (D-41).

An :class:`AiError` carries only a closed ``code``, an opaque gateway
``request_id``, the provider HTTP status class and allowlisted typed fields —
never a provider body, excerpt, header, filename, query or exception text.
"""

import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Final

from pydantic import AfterValidator, StrictBool, StringConstraints

from ai_sdk_m8.schemas._base import AiModel, JcsInt, NonNegativeInt, RequestId, SafeStr


class AiErrorCode(StrEnum):
    """Every error code the gateway may answer; nothing else is valid."""

    UNAUTHORIZED = "unauthorized"
    FORBIDDEN_SCOPE = "forbidden_scope"
    CONTEXT_MISSING = "context_missing"
    CONTEXT_INVALID = "context_invalid"
    CONTEXT_EXPIRED = "context_expired"
    CONTEXT_REPLAYED = "context_replayed"
    DATA_CLASS_DENIED = "data_class_denied"
    PROFILE_UNKNOWN = "profile_unknown"
    CAPABILITY_UNSUPPORTED = "capability_unsupported"
    CREDENTIAL_UNAVAILABLE = "credential_unavailable"
    PROVIDER_UNREACHABLE = "provider_unreachable"
    PROVIDER_REJECTED = "provider_rejected"
    REQUEST_TOO_LARGE = "request_too_large"
    RESPONSE_TOO_LARGE = "response_too_large"
    TIMEOUT = "timeout"
    QUOTA_EXCEEDED = "quota_exceeded"
    RATE_LIMITED = "rate_limited"
    BREAKER_OPEN = "breaker_open"
    BOUNDARY_DENIED = "boundary_denied"
    EXECUTION_IDENTITY_CHANGED = "execution_identity_changed"


class ProviderStatusClass(StrEnum):
    """HTTP status class of the provider answer, never the status itself."""

    SUCCESS = "2xx"
    REDIRECT = "3xx"
    CLIENT_ERROR = "4xx"
    SERVER_ERROR = "5xx"


#: Most keys, counted across both levels, a metadata map may carry.
PROVIDER_METADATA_MAX_ITEMS: Final = 32

#: Largest compact-JSON size of a metadata map, in bytes.
PROVIDER_METADATA_MAX_BYTES: Final = 4096

#: Longest string value a metadata map may carry.
PROVIDER_METADATA_MAX_STR: Final = 256

MetadataKey = Annotated[
    str, StringConstraints(strict=True, pattern=r"^[a-z][a-z0-9_]{0,63}$")
]
MetadataScalar = (
    StrictBool
    | JcsInt
    | Annotated[SafeStr, StringConstraints(max_length=PROVIDER_METADATA_MAX_STR)]
    | None
)
MetadataValue = MetadataScalar | dict[MetadataKey, MetadataScalar]


def _bounded_metadata(
    value: dict[str, MetadataValue],
) -> dict[str, MetadataValue]:
    items = sum(1 + len(v) if isinstance(v, Mapping) else 1 for v in value.values())
    if items > PROVIDER_METADATA_MAX_ITEMS:
        raise ValueError(
            f"provider_metadata exceeds {PROVIDER_METADATA_MAX_ITEMS} items"
        )
    size = len(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode())
    if size > PROVIDER_METADATA_MAX_BYTES:
        raise ValueError(
            f"provider_metadata exceeds {PROVIDER_METADATA_MAX_BYTES} bytes"
        )
    return value


#: Adapter-chosen scalars, at most two levels deep, 32 items and 4 KiB.
ProviderMetadata = Annotated[
    dict[MetadataKey, MetadataValue], AfterValidator(_bounded_metadata)
]


class AiError(AiModel):
    """The one public error shape of the gateway."""

    code: AiErrorCode
    request_id: RequestId
    provider_status_class: ProviderStatusClass | None = None
    retry_after_seconds: NonNegativeInt | None = None
    provider_metadata: ProviderMetadata | None = None


class AiGatewayError(Exception):
    """Raised with a gateway :class:`AiError`; its message is code and id only."""

    def __init__(self, error: AiError) -> None:
        self.error = error
        super().__init__(f"{error.code.value} (request_id={error.request_id})")


__all__ = [
    "PROVIDER_METADATA_MAX_BYTES",
    "PROVIDER_METADATA_MAX_ITEMS",
    "PROVIDER_METADATA_MAX_STR",
    "AiError",
    "AiErrorCode",
    "AiGatewayError",
    "ProviderMetadata",
    "ProviderStatusClass",
]
