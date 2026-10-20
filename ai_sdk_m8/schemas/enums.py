"""Closed vocabularies of the C-01 schemas."""

from enum import StrEnum
from typing import Final


class Capability(StrEnum):
    """Execution capability; ``chat`` and ``vision`` are reserved (no V1 route)."""

    EMBEDDING = "embedding"
    OCR = "ocr"
    STRUCTURED_OUTPUT = "structured_output"
    RERANK = "rerank"
    CHAT = "chat"
    VISION = "vision"


#: Capabilities the V1 gateway executes.
V1_CAPABILITIES: Final = frozenset(
    {
        Capability.EMBEDDING,
        Capability.OCR,
        Capability.STRUCTURED_OUTPUT,
        Capability.RERANK,
    }
)

#: Capabilities reserved in the schemas, with no gateway route.
RESERVED_CAPABILITIES: Final = frozenset({Capability.CHAT, Capability.VISION})


class DataClass(StrEnum):
    """Data class signed into every job context (D-08)."""

    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"


class ProviderBoundary(StrEnum):
    """Whether a provider runs inside the deployment or outside it (D-08)."""

    LOCAL = "local"
    EXTERNAL = "external"


class IdentityAssurance(StrEnum):
    """How far a model identity is provider-verified rather than operator-asserted."""

    PROVIDER_DIGEST = "provider_digest"
    PINNED_SNAPSHOT = "pinned_snapshot"
    OPERATOR_DECLARED = "operator_declared"


__all__ = [
    "RESERVED_CAPABILITIES",
    "V1_CAPABILITIES",
    "Capability",
    "DataClass",
    "IdentityAssurance",
    "ProviderBoundary",
]
