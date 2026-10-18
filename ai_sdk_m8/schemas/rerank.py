"""
Rerank request and result (C-01).

The gateway refuses every rerank destination whose provider boundary is not
``local`` (``boundary_denied``, D-08); nothing in these models widens that.
"""

from typing import Annotated, Self

from pydantic import Field, StrictFloat, StrictInt, model_validator

from ai_sdk_m8.schemas._base import (
    AiModel,
    NonNegativeInt,
    PositiveInt,
    ProfileKey,
    SafeStr,
)
from ai_sdk_m8.schemas.enums import Capability
from ai_sdk_m8.schemas.execution import ExecutionReceipt, require_capability

_NonEmptyStr = Annotated[SafeStr, Field(min_length=1)]


class RerankRequest(AiModel):
    """A query and its candidate excerpts, referenced by position."""

    profile_key: ProfileKey
    query: _NonEmptyStr
    documents: Annotated[tuple[_NonEmptyStr, ...], Field(min_length=1)]
    top_n: PositiveInt | None = None


class RerankHit(AiModel):
    """A candidate position and its relevance score, as the provider ranked it."""

    index: NonNegativeInt
    relevance_score: StrictFloat | StrictInt


class RerankResult(AiModel):
    """Hits in descending relevance; each candidate position at most once."""

    hits: tuple[RerankHit, ...]

    @model_validator(mode="after")
    def _unique_indexes(self) -> Self:
        indexes = [hit.index for hit in self.hits]
        if len(set(indexes)) != len(indexes):
            raise ValueError("a candidate index appears more than once")
        return self


class RerankResponse(AiModel):
    """Rerank answer."""

    result: RerankResult
    execution: ExecutionReceipt

    @model_validator(mode="after")
    def _is_rerank(self) -> Self:
        require_capability(self.execution, Capability.RERANK)
        return self


__all__ = ["RerankHit", "RerankRequest", "RerankResponse", "RerankResult"]
