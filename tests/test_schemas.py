"""C-01 schemas: round trips, closure, immutability and per-model rules."""

import json
import re
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError
from schema_samples import (
    EXECUTION_ID,
    IDENTITY,
    RECEIPT,
    SPACE,
    all_samples,
    execution,
    ocr_result,
    provider_execution,
)

from ai_sdk_m8 import schemas
from ai_sdk_m8.schemas import (
    RESERVED_CAPABILITIES,
    V1_CAPABILITIES,
    AiError,
    AiErrorCode,
    AiGatewayError,
    Capability,
    DataClass,
    EmbedRequest,
    EmbedResponse,
    EmbedResult,
    ExecutionReceipt,
    IdentityAssurance,
    OcrOptions,
    OcrPage,
    OcrRequest,
    OcrResponse,
    OcrResult,
    PixelBox,
    ProfilePublic,
    ProviderBoundary,
    RerankHit,
    RerankRequest,
    RerankResult,
    StructuredOutputRequest,
)
from ai_sdk_m8.schemas.errors import (
    PROVIDER_METADATA_MAX_BYTES,
    PROVIDER_METADATA_MAX_ITEMS,
)

PACKAGE = Path(__file__).resolve().parents[1] / "ai_sdk_m8"
SAMPLES = all_samples()


def _id(sample: object) -> str:
    return type(sample).__name__


# --- every model -----------------------------------------------------------


@pytest.mark.parametrize("sample", SAMPLES, ids=_id)
def test_json_round_trip(sample: BaseModel) -> None:
    again = type(sample).model_validate_json(sample.model_dump_json())
    assert again == sample


@pytest.mark.parametrize("sample", SAMPLES, ids=_id)
def test_python_json_mode_round_trip(sample: BaseModel) -> None:
    data = json.loads(sample.model_dump_json())
    assert type(sample).model_validate(data) == sample


@pytest.mark.parametrize("sample", SAMPLES, ids=_id)
def test_unknown_field_refused(sample: BaseModel) -> None:
    data = json.loads(sample.model_dump_json())
    data["unexpected"] = 1
    with pytest.raises(ValidationError, match="extra_forbidden|Extra inputs"):
        type(sample).model_validate(data)


@pytest.mark.parametrize("sample", SAMPLES, ids=_id)
def test_models_are_frozen(sample: BaseModel) -> None:
    name = next(iter(type(sample).model_fields))
    with pytest.raises(ValidationError, match="frozen"):
        setattr(sample, name, None)


def test_every_exported_model_has_a_sample() -> None:
    exported = {
        name
        for name in schemas.__all__
        if isinstance(getattr(schemas, name), type)
        and issubclass(getattr(schemas, name), BaseModel)
    }
    assert exported == {type(s).__name__ for s in SAMPLES} | {
        "OcrImage",
        "OcrPage",
        "PixelBox",
        "RerankHit",
    }


def test_no_any_in_package_source() -> None:
    for path in PACKAGE.rglob("*.py"):
        assert not re.search(r"\bAny\b", path.read_text(encoding="utf-8")), path


# --- enums -----------------------------------------------------------------


def test_error_codes_are_exactly_the_contract_set() -> None:
    assert {c.value for c in AiErrorCode} == {
        "unauthorized",
        "forbidden_scope",
        "context_missing",
        "context_invalid",
        "context_expired",
        "context_replayed",
        "data_class_denied",
        "profile_unknown",
        "capability_unsupported",
        "credential_unavailable",
        "provider_unreachable",
        "provider_rejected",
        "request_too_large",
        "response_too_large",
        "timeout",
        "quota_exceeded",
        "rate_limited",
        "breaker_open",
        "boundary_denied",
        "execution_identity_changed",
    }


def test_capability_vocabularies() -> None:
    assert V1_CAPABILITIES | RESERVED_CAPABILITIES == set(Capability)
    assert not V1_CAPABILITIES & RESERVED_CAPABILITIES
    assert {c.value for c in RESERVED_CAPABILITIES} == {"chat", "vision"}
    assert [d.value for d in DataClass] == ["public", "internal", "restricted"]
    assert [b.value for b in ProviderBoundary] == ["local", "external"]
    assert {a.value for a in IdentityAssurance} == {
        "provider_digest",
        "pinned_snapshot",
        "operator_declared",
    }


def test_unknown_error_code_refused() -> None:
    with pytest.raises(ValidationError):
        AiError.model_validate({"code": "teapot", "request_id": "r"})


# --- AiError and provider_metadata ------------------------------------------


def test_gateway_error_message_carries_code_and_request_id_only() -> None:
    error = AiError(
        code=AiErrorCode.PROVIDER_REJECTED,
        request_id="req-9",
        provider_metadata={"detail_code": "bad_model"},
    )
    exc = AiGatewayError(error)
    assert str(exc) == "provider_rejected (request_id=req-9)"
    assert exc.error is error


@pytest.mark.parametrize(
    "metadata",
    [
        {"nested": {"deeper": {"x": 1}}},
        {"value": 1.5},
        {"value": [1, 2]},
        {"Upper": 1},
        {"value": "x" * 257},
        {"value": 2**53},
    ],
    ids=["depth-3", "float", "list", "key-charset", "long-string", "jcs-range"],
)
def test_provider_metadata_shape_refused(metadata: object) -> None:
    with pytest.raises(ValidationError):
        AiError.model_validate(
            {"code": "timeout", "request_id": "r", "provider_metadata": metadata}
        )


def test_provider_metadata_item_cap_counts_both_levels() -> None:
    nested = {f"k{i}": i for i in range(PROVIDER_METADATA_MAX_ITEMS - 1)}
    AiError(code=AiErrorCode.TIMEOUT, request_id="r", provider_metadata={"n": nested})
    nested["extra"] = 0
    with pytest.raises(ValidationError, match="items"):
        AiError(
            code=AiErrorCode.TIMEOUT, request_id="r", provider_metadata={"n": nested}
        )


def test_provider_metadata_byte_cap() -> None:
    big = {f"k{i}": "é" * 128 for i in range(PROVIDER_METADATA_MAX_ITEMS)}
    assert len(json.dumps(big).encode()) > PROVIDER_METADATA_MAX_BYTES
    with pytest.raises(ValidationError, match="bytes"):
        AiError(code=AiErrorCode.TIMEOUT, request_id="r", provider_metadata=big)


@pytest.mark.parametrize("request_id", ["", "a b", "x" * 65, "id\n"])
def test_request_id_is_opaque_token(request_id: str) -> None:
    with pytest.raises(ValidationError):
        AiError(code=AiErrorCode.TIMEOUT, request_id=request_id)


# --- profiles --------------------------------------------------------------


@pytest.mark.parametrize(
    ("capability", "fields"),
    [
        (Capability.EMBEDDING, {"dimensions": 4}),
        (Capability.EMBEDDING, {"embedding_space_id": SPACE}),
        (Capability.RERANK, {"dimensions": 4, "embedding_space_id": SPACE}),
        (Capability.OCR, {}),
        (Capability.RERANK, {"ocr_execution_identity": IDENTITY}),
    ],
)
def test_profile_capability_shape(capability: Capability, fields: object) -> None:
    with pytest.raises(ValidationError):
        ProfilePublic.model_validate(
            {
                "profile_key": "p",
                "capability": capability,
                "revision": 1,
                "enabled": True,
                "identity_assurance": "operator_declared",
                **fields,  # type: ignore[dict-item]
            }
        )


@pytest.mark.parametrize("key", ["", "-a", "a-", "A", "a b", "a" * 65, "a\n"])
def test_profile_key_charset(key: str) -> None:
    with pytest.raises(ValidationError):
        OcrRequest(profile_key=key)


# --- execution receipt -----------------------------------------------------


def _receipt(**changes: object) -> dict[str, object]:
    data: dict[str, object] = json.loads(execution(Capability.RERANK).model_dump_json())
    data.update(changes)
    return data


@pytest.mark.parametrize(
    "changes",
    [
        {"receipt": RECEIPT},
        {"capability": "ocr"},
        {"capability": "chat"},
        {"capability": "embedding"},
        {
            "provider_execution": json.loads(
                provider_execution(space=SPACE).model_dump_json()
            )
        },
        {"units": -1},
        {"units": 1.0},
        {"units": True},
        {"execution_id": "00000000-0000-1000-8000-000000000000"},
    ],
    ids=[
        "receipt-on-rerank",
        "ocr-without-receipt",
        "reserved-capability",
        "embedding-without-space",
        "space-on-rerank",
        "negative-units",
        "float-units",
        "bool-units",
        "uuid1",
    ],
)
def test_execution_receipt_shape(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ExecutionReceipt.model_validate(_receipt(**changes))


@pytest.mark.parametrize(
    "receipt",
    ["nodot", "a.b.c", "a=.b", "a.b=", "a .b", "a." + "b" * 4095],
)
def test_receipt_is_compact_and_bounded(receipt: str) -> None:
    data = json.loads(execution(Capability.OCR).model_dump_json())
    data["receipt"] = receipt
    with pytest.raises(ValidationError):
        ExecutionReceipt.model_validate(data)


@pytest.mark.parametrize(
    ("response", "wrong"),
    [
        (OcrResponse, Capability.RERANK),
        (EmbedResponse, Capability.OCR),
    ],
)
def test_response_capability_must_match(
    response: type[BaseModel], wrong: Capability
) -> None:
    result = (
        ocr_result()
        if response is OcrResponse
        else EmbedResult(dimensions=1, vectors=((0.0,),))
    )
    with pytest.raises(ValidationError, match="does not match"):
        response.model_validate({"result": result, "execution": execution(wrong)})


# --- OCR -------------------------------------------------------------------


def test_ocr_result_is_float_free_and_canonicalizable() -> None:
    def walk(value: object) -> None:
        assert not isinstance(value, float)
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    data = ocr_result().model_dump(mode="json")
    walk(data)
    canonical = json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert OcrResult.model_validate_json(canonical) == ocr_result()


@pytest.mark.parametrize(
    "page",
    [
        {"confidence_bp": 0.97},
        {"confidence_bp": 10_001},
        {"width_px": 1240.0},
        {"width_px": 0},
        {"index": -1},
        {"markdown": "\ud800"},
        {
            "images": [
                {"image_id": "i", "bbox": {"x0": 0, "y0": 0, "x1": 2000, "y1": 1}}
            ]
        },
        {
            "images": [
                {"image_id": "i", "bbox": {"x0": 0, "y0": 0, "x1": 1, "y1": 2000}}
            ]
        },
        {"images": [{"image_id": "", "bbox": {"x0": 0, "y0": 0, "x1": 1, "y1": 1}}]},
    ],
    ids=[
        "float-confidence",
        "confidence-range",
        "float-pixels",
        "zero-width",
        "negative-index",
        "lone-surrogate",
        "image-right-of-page",
        "image-below-page",
        "empty-image-id",
    ],
)
def test_ocr_page_rules(page: dict[str, object]) -> None:
    data = {"index": 0, "width_px": 1240, "height_px": 1754, "markdown": "", **page}
    with pytest.raises(ValidationError):
        OcrPage.model_validate(data)


@pytest.mark.parametrize(
    "box", [(5, 0, 4, 0), (0, 5, 0, 4)], ids=["x-reversed", "y-reversed"]
)
def test_pixel_box_corners_ordered(box: tuple[int, int, int, int]) -> None:
    with pytest.raises(ValidationError, match="out of order"):
        PixelBox(x0=box[0], y0=box[1], x1=box[2], y1=box[3])


@pytest.mark.parametrize("indexes", [[], [1, 0], [0, 0]])
def test_ocr_result_pages_ordered_and_non_empty(indexes: list[int]) -> None:
    pages = [
        {"index": i, "width_px": 1, "height_px": 1, "markdown": ""} for i in indexes
    ]
    with pytest.raises(ValidationError):
        OcrResult.model_validate({"pages": pages})


@pytest.mark.parametrize("pages", [[], [3, 1], [1, 1], [True]])
def test_ocr_options_pages(pages: list[int]) -> None:
    with pytest.raises(ValidationError):
        OcrOptions.model_validate({"pages": pages})


def test_ocr_request_defaults() -> None:
    request = OcrRequest(profile_key="ocr")
    assert request.options == OcrOptions()
    assert request.model_dump(mode="json") == {
        "profile_key": "ocr",
        "options": {"pages": None},
        "expected_execution_identity": None,
    }


def test_ocr_spool_expiry_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError):
        schemas.OcrSpoolResult.model_validate(
            {"spool_id": str(EXECUTION_ID), "expires_at": "2026-10-18T12:00:00"}
        )


# --- embedding, rerank, structured output ----------------------------------


@pytest.mark.parametrize(
    "vectors",
    [[[0.1]], [[0.1, float("nan")]], [[0.1, float("inf")]], [[True, 0.0]], []],
    ids=["short", "nan", "inf", "bool", "empty"],
)
def test_embed_result_vectors(vectors: list[list[float]]) -> None:
    with pytest.raises(ValidationError):
        EmbedResult.model_validate({"dimensions": 2, "vectors": vectors})


@pytest.mark.parametrize("inputs", [[], [""]], ids=["no-inputs", "empty-input"])
def test_embed_request_inputs(inputs: list[str]) -> None:
    with pytest.raises(ValidationError):
        EmbedRequest.model_validate({"profile_key": "e", "inputs": inputs})


def test_rerank_rules() -> None:
    with pytest.raises(ValidationError, match="more than once"):
        RerankResult(
            hits=(
                RerankHit(index=0, relevance_score=1),
                RerankHit(index=0, relevance_score=0.5),
            )
        )
    with pytest.raises(ValidationError):
        RerankHit.model_validate({"index": 0, "relevance_score": float("nan")})
    with pytest.raises(ValidationError):
        RerankRequest.model_validate(
            {"profile_key": "r", "query": "q", "documents": [], "top_n": 1}
        )
    with pytest.raises(ValidationError):
        RerankRequest.model_validate(
            {"profile_key": "r", "query": "q", "documents": ["d"], "top_n": 0}
        )


@pytest.mark.parametrize("name", ["", "1abc", "a b", "a" * 65])
def test_structured_output_schema_name(name: str) -> None:
    with pytest.raises(ValidationError):
        StructuredOutputRequest(
            profile_key="s", input="x", schema_name=name, json_schema={}
        )
