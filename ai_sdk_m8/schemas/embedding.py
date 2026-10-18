"""Embedding request and result (C-01)."""

from typing import Annotated, Self

from pydantic import Field, StrictFloat, StrictInt, model_validator

from ai_sdk_m8.schemas._base import AiModel, PositiveInt, ProfileKey, SafeStr
from ai_sdk_m8.schemas.enums import Capability
from ai_sdk_m8.schemas.execution import ExecutionReceipt, require_capability


class EmbedRequest(AiModel):
    """Texts to embed; the count cap is the gateway's ``AI_MAX_EMBED_INPUTS``."""

    profile_key: ProfileKey
    inputs: Annotated[
        tuple[Annotated[SafeStr, Field(min_length=1)], ...], Field(min_length=1)
    ]


class EmbedResult(AiModel):
    """One finite vector per input, in input order, all of ``dimensions``."""

    dimensions: PositiveInt
    vectors: Annotated[
        tuple[tuple[StrictFloat | StrictInt, ...], ...], Field(min_length=1)
    ]

    @model_validator(mode="after")
    def _dimensions_match(self) -> Self:
        if any(len(vector) != self.dimensions for vector in self.vectors):
            raise ValueError("every vector must have exactly `dimensions` components")
        return self


class EmbedResponse(AiModel):
    """
    Embedding answer.

    ``execution.provider_execution.embedding_space_id`` is the space of the
    binding actually resolved — the value to assert before ingesting.
    """

    result: EmbedResult
    execution: ExecutionReceipt

    @model_validator(mode="after")
    def _is_embedding(self) -> Self:
        require_capability(self.execution, Capability.EMBEDDING)
        return self


__all__ = ["EmbedRequest", "EmbedResponse", "EmbedResult"]
