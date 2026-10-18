"""Valid sample instances of every C-01 model, shared by the schema tests."""

from datetime import UTC, datetime
from uuid import UUID

from ai_sdk_m8.schemas import (
    AiError,
    AiErrorCode,
    Capability,
    EmbedRequest,
    EmbedResponse,
    EmbedResult,
    ExecutionReceipt,
    IdentityAssurance,
    OcrImage,
    OcrOptions,
    OcrPage,
    OcrRequest,
    OcrResponse,
    OcrResult,
    OcrSpoolResult,
    PixelBox,
    ProfilePublic,
    ProviderExecution,
    ProviderStatusClass,
    ProviderUsage,
    RerankHit,
    RerankRequest,
    RerankResponse,
    RerankResult,
    StructuredOutputRequest,
    StructuredOutputResponse,
    StructuredOutputResult,
)

IDENTITY = "0123456789abcdef0123456789abcdef"
SPACE = "fedcba9876543210fedcba9876543210"
EXECUTION_ID = UUID("7d3c0e1a-5b2f-4c8e-9a61-2f0d4b8e1c37")
RECEIPT = "eyJ2IjoxfQ.c2lnbmF0dXJl"


def provider_execution(*, space: str | None = None) -> ProviderExecution:
    return ProviderExecution(
        profile_key="default-profile",
        profile_revision=3,
        execution_identity=IDENTITY,
        embedding_space_id=space,
        identity_assurance=IdentityAssurance.PINNED_SNAPSHOT,
    )


def execution(capability: Capability) -> ExecutionReceipt:
    return ExecutionReceipt(
        execution_id=EXECUTION_ID,
        capability=capability,
        units=12,
        provider_usage=ProviderUsage(input_tokens=10, output_tokens=2),
        provider_execution=provider_execution(
            space=SPACE if capability is Capability.EMBEDDING else None
        ),
        receipt=RECEIPT if capability is Capability.OCR else None,
    )


def ocr_result() -> OcrResult:
    return OcrResult(
        pages=(
            OcrPage(
                index=0,
                width_px=1240,
                height_px=1754,
                dpi=150,
                markdown="# Título\n\nTexto ✓",
                images=(
                    OcrImage(
                        image_id="img-0.jpeg",
                        bbox=PixelBox(x0=10, y0=20, x1=1240, y1=1754),
                    ),
                ),
                confidence_bp=9_712,
            ),
            OcrPage(index=2, width_px=1240, height_px=1754, markdown=""),
        )
    )


def all_samples() -> list[object]:
    """One valid instance of every public model."""
    return [
        AiError(
            code=AiErrorCode.RATE_LIMITED,
            request_id="req_01H",
            provider_status_class=ProviderStatusClass.CLIENT_ERROR,
            retry_after_seconds=30,
            provider_metadata={"model_status": "ok", "limits": {"rpm": 60}},
        ),
        ProfilePublic(
            profile_key="embed.small",
            capability=Capability.EMBEDDING,
            revision=1,
            enabled=True,
            identity_assurance=IdentityAssurance.PROVIDER_DIGEST,
            dimensions=768,
            embedding_space_id=SPACE,
        ),
        ProfilePublic(
            profile_key="ocr",
            capability=Capability.OCR,
            revision=2,
            enabled=False,
            identity_assurance=IdentityAssurance.OPERATOR_DECLARED,
            ocr_execution_identity=IDENTITY,
        ),
        ProviderUsage(pages_processed=4),
        provider_execution(),
        execution(Capability.OCR),
        OcrOptions(pages=(0, 2, 5)),
        OcrRequest(profile_key="ocr", expected_execution_identity=IDENTITY),
        OcrSpoolResult(
            spool_id=EXECUTION_ID, expires_at=datetime(2026, 10, 18, 12, tzinfo=UTC)
        ),
        ocr_result(),
        OcrResponse(result=ocr_result(), execution=execution(Capability.OCR)),
        EmbedRequest(profile_key="embed.small", inputs=("a", "b")),
        EmbedResult(dimensions=3, vectors=((0.1, -0.2, 0), (1, 0.5, -1.25))),
        EmbedResponse(
            result=EmbedResult(dimensions=2, vectors=((0.5, 0.25),)),
            execution=execution(Capability.EMBEDDING),
        ),
        RerankRequest(profile_key="rr", query="q", documents=("x", "y"), top_n=1),
        RerankResult(hits=(RerankHit(index=1, relevance_score=0.9),)),
        RerankResponse(
            result=RerankResult(hits=()), execution=execution(Capability.RERANK)
        ),
        StructuredOutputRequest(
            profile_key="so",
            input="extract",
            schema_name="Invoice",
            json_schema={"type": "object", "properties": {"n": {"type": "integer"}}},
        ),
        StructuredOutputResult(output={"n": 1, "tags": ["a"], "x": None}),
        StructuredOutputResponse(
            result=StructuredOutputResult(output={}),
            execution=execution(Capability.STRUCTURED_OUTPUT),
        ),
    ]
