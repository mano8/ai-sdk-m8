"""Structured-output request and result (C-01)."""

from typing import Annotated, Self

from pydantic import Field, JsonValue, StringConstraints, model_validator

from ai_sdk_m8.schemas._base import AiModel, ProfileKey, SafeStr
from ai_sdk_m8.schemas.enums import Capability
from ai_sdk_m8.schemas.execution import ExecutionReceipt, require_capability


class StructuredOutputRequest(AiModel):
    """
    Input text and the JSON Schema the output must satisfy.

    Size and depth caps on ``json_schema`` are the gateway's
    (``AI_MAX_SCHEMA_BYTES``, ``AI_MAX_SCHEMA_DEPTH``).
    """

    profile_key: ProfileKey
    input: Annotated[SafeStr, Field(min_length=1)]
    schema_name: Annotated[
        str, StringConstraints(strict=True, pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    ]
    json_schema: dict[str, JsonValue]


class StructuredOutputResult(AiModel):
    """The JSON object the model produced."""

    output: dict[str, JsonValue]


class StructuredOutputResponse(AiModel):
    """Structured-output answer."""

    result: StructuredOutputResult
    execution: ExecutionReceipt

    @model_validator(mode="after")
    def _is_structured_output(self) -> Self:
        require_capability(self.execution, Capability.STRUCTURED_OUTPUT)
        return self


__all__ = [
    "StructuredOutputRequest",
    "StructuredOutputResponse",
    "StructuredOutputResult",
]
