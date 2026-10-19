"""
Closed payload models signed under the C-03 rule.

* :class:`JobContextPayload` — the single-use job context (domain
  ``m8.ai.job-context.v1``), one per provider call.
* :class:`OcrReceiptPayload` — the gateway's OCR provenance receipt (domain
  ``m8.ai.ocr-receipt.v1``, C-01), verified by its consumer.

Every field is a JSON string or an integer inside the JCS range, so a
payload's canonical form is defined. An absent optional claim is omitted,
never ``null``: an explicit ``null`` is refused, so each payload has one
encoding.
"""

from enum import StrEnum
from typing import Annotated, Final, Literal, Self

from pydantic import Field, StrictInt, StrictStr, StringConstraints, model_validator

from ai_sdk_m8.schemas._base import (
    AiModel,
    NonNegativeInt,
    PositiveInt,
    ProfileKey,
    Revision,
)
from ai_sdk_m8.schemas.enums import (
    V1_CAPABILITIES,
    Capability,
    DataClass,
    ProviderBoundary,
)


def _pattern(regex: str) -> StringConstraints:
    return StringConstraints(pattern=regex)


_UUID: Final = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

#: Lower-case canonical UUID version 4 (``jti``, ``spool_id``, ``execution_id``).
Uuid4Str = Annotated[
    StrictStr,
    _pattern(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"),
]

#: Lower-case hex SHA-256 digest.
Sha256Hex = Annotated[StrictStr, _pattern(r"^[0-9a-f]{64}$")]

#: ``kid``: unpadded base64url of 16 bytes.
Kid = Annotated[StrictStr, _pattern(r"^[A-Za-z0-9_-]{22}$")]

#: A registered service-client id (the ``X-Internal-Client`` value).
ClientId = Annotated[StrictStr, _pattern(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]

#: An opaque identifier: tenant, user or job reference.
OpaqueId = Annotated[StrictStr, _pattern(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$")]

#: A gateway installation, ``ai-gateway/<deployment_id>``.
InstallationRef = Annotated[StrictStr, _pattern(rf"^ai-gateway/{_UUID}$")]

#: The constant ``1`` — ``v`` and ``max_uses``; ``True`` is not ``1`` here.
One = Annotated[StrictInt, Field(ge=1, le=1)]


class JobContextPhase(StrEnum):
    """OCR phase a context authorises (D-44)."""

    SPOOL = "spool"
    DISPATCH = "dispatch"


class SignedPayload(AiModel):
    """Common shape: ``v = 1``, ``kid``, and no explicit ``null`` claim."""

    v: One = 1
    kid: Kid

    @model_validator(mode="before")
    @classmethod
    def _no_null_claims(cls, data: object) -> object:
        if isinstance(data, dict) and any(value is None for value in data.values()):
            raise ValueError("an absent claim is omitted, never null")
        return data


_OCR_ONLY: Final = ("phase", "input_sha256", "input_bytes", "ocr_options_hash")


class JobContextPayload(SignedPayload):
    """
    The C-03 job-context claims; the shape rules hold whatever the clock.

    For ``capability = ocr`` the three input claims and ``phase`` are
    mandatory, and ``spool_id`` is present exactly in the ``dispatch``
    phase. No other capability carries an OCR claim.
    """

    typ: Literal["m8.ai.job-context.v1"] = "m8.ai.job-context.v1"
    iss: ClientId
    aud: InstallationRef
    azp: ClientId
    tenant_id: OpaqueId | None = None
    user_id: OpaqueId | None = None
    data_class: DataClass
    capability: Capability
    profile_key: ProfileKey
    job_ref: OpaqueId
    attempt: PositiveInt
    phase: JobContextPhase | None = None
    spool_id: Uuid4Str | None = None
    input_sha256: Sha256Hex | None = None
    input_bytes: PositiveInt | None = None
    ocr_options_hash: Sha256Hex | None = None
    allowed_boundaries: (
        Annotated[tuple[ProviderBoundary, ...], Field(min_length=1)] | None
    ) = None
    jti: Uuid4Str
    iat: NonNegativeInt
    nbf: NonNegativeInt
    exp: NonNegativeInt
    max_uses: One = 1

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if self.capability not in V1_CAPABILITIES:
            raise ValueError("capability has no V1 route")
        if not self.iat <= self.nbf < self.exp:
            raise ValueError("claims must satisfy iat <= nbf < exp")
        if self.allowed_boundaries is not None and len(
            set(self.allowed_boundaries)
        ) != len(self.allowed_boundaries):
            raise ValueError("allowed_boundaries repeats a boundary")
        ocr_claims = [getattr(self, name) for name in _OCR_ONLY]
        if self.capability is not Capability.OCR:
            if any(claim is not None for claim in [*ocr_claims, self.spool_id]):
                raise ValueError("OCR claims are forbidden outside ocr")
            return self
        if any(claim is None for claim in ocr_claims):
            raise ValueError("ocr needs phase, input_sha256, input_bytes and the hash")
        if (self.phase is JobContextPhase.DISPATCH) != (self.spool_id is not None):
            raise ValueError(
                "spool_id is required for dispatch and forbidden for spool"
            )
        return self


class OcrReceiptPayload(SignedPayload):
    """
    The C-01 signed OCR provenance receipt.

    ``result_sha256`` = SHA-256(JCS(``OcrResult``)) over the unsigned body;
    ``produced_at`` is the gateway's clock in integer seconds since the epoch.
    """

    typ: Literal["m8.ai.ocr-receipt.v1"] = "m8.ai.ocr-receipt.v1"
    iss: InstallationRef
    execution_id: Uuid4Str
    capability: Literal["ocr"] = "ocr"
    job_ref: OpaqueId
    attempt: PositiveInt
    azp: ClientId
    profile_key: ProfileKey
    input_sha256: Sha256Hex
    ocr_options_hash: Sha256Hex
    execution_identity: Revision
    result_sha256: Sha256Hex
    produced_at: NonNegativeInt


__all__ = [
    "ClientId",
    "InstallationRef",
    "JobContextPayload",
    "JobContextPhase",
    "Kid",
    "OcrReceiptPayload",
    "OpaqueId",
    "Sha256Hex",
    "SignedPayload",
    "Uuid4Str",
]
