"""Reader view of a gateway profile — never credentials or ``base_url``."""

from typing import Self

from pydantic import StrictBool, model_validator

from ai_sdk_m8.schemas._base import AiModel, PositiveInt, ProfileKey, Revision
from ai_sdk_m8.schemas.enums import Capability, IdentityAssurance


class ProfilePublic(AiModel):
    """
    A profile as readers and ``profiles:read`` service clients see it.

    Embedding profiles carry ``dimensions`` and ``embedding_space_id``; OCR
    profiles carry the current ``ocr_execution_identity``. Neither appears on
    any other capability.
    """

    profile_key: ProfileKey
    capability: Capability
    revision: PositiveInt
    enabled: StrictBool
    identity_assurance: IdentityAssurance
    dimensions: PositiveInt | None = None
    embedding_space_id: Revision | None = None
    ocr_execution_identity: Revision | None = None

    @model_validator(mode="after")
    def _capability_shape(self) -> Self:
        embedding = self.capability is Capability.EMBEDDING
        if embedding != (self.dimensions is not None) or embedding != (
            self.embedding_space_id is not None
        ):
            raise ValueError(
                "dimensions and embedding_space_id are required for embedding "
                "profiles and forbidden otherwise"
            )
        if (self.capability is Capability.OCR) != (
            self.ocr_execution_identity is not None
        ):
            raise ValueError(
                "ocr_execution_identity is required for ocr profiles "
                "and forbidden otherwise"
            )
        return self


__all__ = ["ProfilePublic"]
