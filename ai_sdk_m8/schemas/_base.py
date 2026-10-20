"""
Shared base model and constrained field types of the C-01 schemas.

Every integer that may enter a signed or hashed body stays inside the JSON
Canonicalization Scheme (JCS) integer-only range of ±(2**53 - 1), and every
string must encode as UTF-8 (no lone surrogates), so ``JCS(model)`` is
defined for the float-free models.
"""

from typing import Annotated, Final

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    StringConstraints,
)

#: Largest magnitude an integer may have under the integer-only JCS rule.
JCS_INT_MAX: Final = 2**53 - 1


def _utf8_only(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("string is not valid UTF-8 (lone surrogate)") from exc
    return value


class AiModel(BaseModel):
    """Frozen, closed base: unknown fields, NaN and infinity are refused."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
        validate_default=True,
    )


#: A string that encodes as UTF-8.
SafeStr = Annotated[StrictStr, AfterValidator(_utf8_only)]

#: An integer inside the JCS integer range.
JcsInt = Annotated[StrictInt, Field(ge=-JCS_INT_MAX, le=JCS_INT_MAX)]

#: A non-negative integer inside the JCS integer range.
NonNegativeInt = Annotated[StrictInt, Field(ge=0, le=JCS_INT_MAX)]

#: A positive integer inside the JCS integer range.
PositiveInt = Annotated[StrictInt, Field(ge=1, le=JCS_INT_MAX)]

#: A ratio in integer basis points (0 = 0 %, 10 000 = 100 %).
BasisPoints = Annotated[StrictInt, Field(ge=0, le=10_000)]

#: 32-hex identity prefix (``execution_identity``, ``embedding_space_id``).
Revision = Annotated[StrictStr, StringConstraints(pattern=r"^[0-9a-f]{32}$")]

#: Profile key: lower-case, 1-64 characters, no leading or trailing separator.
ProfileKey = Annotated[
    StrictStr,
    StringConstraints(pattern=r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$"),
]

#: Opaque gateway request id.
RequestId = Annotated[StrictStr, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,64}$")]

#: Compact signed object ``b64url(payload) "." b64url(sig)``, at most 4 KiB.
CompactSignedObject = Annotated[
    StrictStr,
    StringConstraints(max_length=4096, pattern=r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$"),
]
