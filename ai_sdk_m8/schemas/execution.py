"""
Execution accounting shared by every capability response.

``units`` are the admission units the gateway fixed and reserved before
dispatch; ``provider_usage`` is what the provider reported, recorded
separately and never used to settle the charge (D-24).
"""

from typing import Self

from pydantic import UUID4, model_validator

from ai_sdk_m8.schemas._base import (
    AiModel,
    CompactSignedObject,
    NonNegativeInt,
    PositiveInt,
    ProfileKey,
    Revision,
)
from ai_sdk_m8.schemas.enums import V1_CAPABILITIES, Capability, IdentityAssurance


class ProviderUsage(AiModel):
    """Provider-reported usage; informational only."""

    input_tokens: NonNegativeInt | None = None
    output_tokens: NonNegativeInt | None = None
    pages_processed: NonNegativeInt | None = None


class ProviderExecution(AiModel):
    """
    The model identity an execution actually resolved.

    ``embedding_space_id`` is present exactly on embedding executions and is
    the resolved binding's space, never the profile's published one.
    """

    profile_key: ProfileKey
    profile_revision: PositiveInt
    execution_identity: Revision
    embedding_space_id: Revision | None = None
    identity_assurance: IdentityAssurance


class ExecutionReceipt(AiModel):
    """
    Accounting record of one execution.

    ``receipt`` is the detached signed OCR provenance receipt (C-01, domain
    ``m8.ai.ocr-receipt.v1``): present on every ``ocr`` execution and on no
    other capability. It is verified by its consumer, not here.
    """

    execution_id: UUID4
    capability: Capability
    units: NonNegativeInt
    provider_usage: ProviderUsage | None = None
    provider_execution: ProviderExecution
    receipt: CompactSignedObject | None = None

    @model_validator(mode="after")
    def _capability_shape(self) -> Self:
        if self.capability not in V1_CAPABILITIES:
            raise ValueError(f"capability {self.capability.value!r} has no V1 route")
        if (self.capability is Capability.OCR) != (self.receipt is not None):
            raise ValueError("receipt is required for ocr and forbidden otherwise")
        has_space = self.provider_execution.embedding_space_id is not None
        if (self.capability is Capability.EMBEDDING) != has_space:
            raise ValueError(
                "embedding_space_id is required for embedding and forbidden otherwise"
            )
        return self


def require_capability(execution: ExecutionReceipt, expected: Capability) -> None:
    """Raise ``ValueError`` unless ``execution`` is for ``expected``."""
    if execution.capability is not expected:
        raise ValueError(
            f"execution capability {execution.capability.value!r} "
            f"does not match {expected.value!r}"
        )


__all__ = ["ExecutionReceipt", "ProviderExecution", "ProviderUsage"]
