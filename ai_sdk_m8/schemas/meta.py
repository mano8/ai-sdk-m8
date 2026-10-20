"""
The gateway's ``{API_PREFIX}/meta`` answer (D-03, D-08, D-23, T15).

The first four fields are the fleet's ``ServiceMeta`` shape, served by every
m8 service. ``gateway`` adds the non-secret values a caller or an operator
checks against the ratified configuration. Unknown fields are ignored here,
unlike the execution models: ``/meta`` is read before anything else, so a
newer gateway that reports more must still be readable by an older SDK.
"""

from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictBool,
    StrictStr,
    StringConstraints,
)

from ai_sdk_m8.schemas._base import PositiveInt
from ai_sdk_m8.schemas.enums import Capability

_NonEmpty = Annotated[StrictStr, StringConstraints(min_length=1, max_length=256)]


class _OpenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class ServiceContract(_OpenModel):
    """Identity of the contract a service implements."""

    name: _NonEmpty
    version: _NonEmpty
    range: _NonEmpty


class GatewayMetaValues(_OpenModel):
    """
    Ratified-configuration values the gateway reports.

    ``data_class_policy_sha256`` is the SHA-256 of the effective
    ``AI_DATA_CLASS_POLICY`` in canonical form, so a widened deployment is
    visible. The key versions are this replica's active generations.
    """

    deployment_id: _NonEmpty
    user_byok_enabled: StrictBool
    job_context_max_ttl_seconds: PositiveInt
    dispatch_context_ttl_seconds: PositiveInt
    data_class_policy_sha256: Annotated[
        StrictStr, StringConstraints(pattern=r"^[0-9a-f]{64}$")
    ]
    capabilities_enabled: tuple[Capability, ...]
    credential_storage_backend: _NonEmpty
    kek_key_version: _NonEmpty | None = None
    fingerprint_key_version: _NonEmpty | None = None


class GatewayMeta(_OpenModel):
    """The fleet ``ServiceMeta`` fields plus the gateway's own values."""

    service: _NonEmpty
    version: _NonEmpty
    api_version: _NonEmpty
    contract: ServiceContract
    gateway: GatewayMetaValues


__all__ = ["GatewayMeta", "GatewayMetaValues", "ServiceContract"]
