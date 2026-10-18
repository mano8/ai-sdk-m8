"""
C-01 schemas of the AI gateway: frozen Pydantic v2 models, no I/O at import.

Every model is closed (``extra="forbid"``) and immutable; NaN and infinity
are refused everywhere.
"""

from ai_sdk_m8.schemas.embedding import EmbedRequest, EmbedResponse, EmbedResult
from ai_sdk_m8.schemas.enums import (
    RESERVED_CAPABILITIES,
    V1_CAPABILITIES,
    Capability,
    DataClass,
    IdentityAssurance,
    ProviderBoundary,
)
from ai_sdk_m8.schemas.errors import (
    AiError,
    AiErrorCode,
    AiGatewayError,
    ProviderStatusClass,
)
from ai_sdk_m8.schemas.execution import (
    ExecutionReceipt,
    ProviderExecution,
    ProviderUsage,
)
from ai_sdk_m8.schemas.ocr import (
    OcrImage,
    OcrOptions,
    OcrPage,
    OcrRequest,
    OcrResponse,
    OcrResult,
    OcrSpoolResult,
    PixelBox,
)
from ai_sdk_m8.schemas.profiles import ProfilePublic
from ai_sdk_m8.schemas.rerank import (
    RerankHit,
    RerankRequest,
    RerankResponse,
    RerankResult,
)
from ai_sdk_m8.schemas.structured_output import (
    StructuredOutputRequest,
    StructuredOutputResponse,
    StructuredOutputResult,
)

__all__ = [
    "RESERVED_CAPABILITIES",
    "V1_CAPABILITIES",
    "AiError",
    "AiErrorCode",
    "AiGatewayError",
    "Capability",
    "DataClass",
    "EmbedRequest",
    "EmbedResponse",
    "EmbedResult",
    "ExecutionReceipt",
    "IdentityAssurance",
    "OcrImage",
    "OcrOptions",
    "OcrPage",
    "OcrRequest",
    "OcrResponse",
    "OcrResult",
    "OcrSpoolResult",
    "PixelBox",
    "ProfilePublic",
    "ProviderBoundary",
    "ProviderExecution",
    "ProviderStatusClass",
    "ProviderUsage",
    "RerankHit",
    "RerankRequest",
    "RerankResponse",
    "RerankResult",
    "StructuredOutputRequest",
    "StructuredOutputResponse",
    "StructuredOutputResult",
]
