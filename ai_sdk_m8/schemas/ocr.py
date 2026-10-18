"""
OCR request and result (C-01, D-31, D-44).

:class:`OcrResult` is float-free — coordinates in integer pixels,
confidences in integer basis points — and carries no receipt or signature,
so ``JCS(OcrResult)`` is defined under the integer-only rule and
``result_sha256 = SHA-256(JCS(OcrResult))`` is computed over exactly this
body. The document itself travels as a multipart part, never in JSON.
"""

from itertools import pairwise
from typing import Annotated, Self

from pydantic import UUID4, AwareDatetime, Field, model_validator

from ai_sdk_m8.schemas._base import (
    AiModel,
    BasisPoints,
    NonNegativeInt,
    PositiveInt,
    ProfileKey,
    Revision,
    SafeStr,
)
from ai_sdk_m8.schemas.enums import Capability
from ai_sdk_m8.schemas.execution import ExecutionReceipt, require_capability


def _strictly_increasing(values: tuple[int, ...], what: str) -> None:
    if any(a >= b for a, b in pairwise(values)):
        raise ValueError(f"{what} must be unique and strictly increasing")


class OcrOptions(AiModel):
    """
    Options hashed into the signed ``ocr_options_hash``.

    ``pages`` (zero-based) limits the pages the provider processes and the
    admission units charged; the whole document is still transmitted (Q12).
    """

    pages: Annotated[tuple[NonNegativeInt, ...], Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def _pages_ordered(self) -> Self:
        if self.pages is not None:
            _strictly_increasing(self.pages, "pages")
        return self


class OcrRequest(AiModel):
    """
    JSON part of the phase-1 (spool) OCR call.

    ``expected_execution_identity`` pins the identity returned by the first
    successful call; the gateway refuses ``execution_identity_changed`` when
    the resolved identity differs.
    """

    profile_key: ProfileKey
    options: OcrOptions = OcrOptions()
    expected_execution_identity: Revision | None = None


class OcrSpoolResult(AiModel):
    """Phase-1 answer: the spool to dispatch, no provider call made."""

    spool_id: UUID4
    expires_at: AwareDatetime


class PixelBox(AiModel):
    """Axis-aligned box in integer pixels, ``(x0, y0)`` top-left inclusive."""

    x0: NonNegativeInt
    y0: NonNegativeInt
    x1: NonNegativeInt
    y1: NonNegativeInt

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.x0 > self.x1 or self.y0 > self.y1:
            raise ValueError("box corners are out of order")
        return self


class OcrImage(AiModel):
    """An image region the provider located; its bytes are never returned."""

    image_id: Annotated[SafeStr, Field(min_length=1, max_length=128)]
    bbox: PixelBox


class OcrPage(AiModel):
    """One processed page."""

    index: NonNegativeInt
    width_px: PositiveInt
    height_px: PositiveInt
    dpi: PositiveInt | None = None
    markdown: SafeStr
    images: tuple[OcrImage, ...] = ()
    confidence_bp: BasisPoints | None = None

    @model_validator(mode="after")
    def _images_inside_page(self) -> Self:
        for image in self.images:
            if image.bbox.x1 > self.width_px or image.bbox.y1 > self.height_px:
                raise ValueError(f"image {image.image_id!r} lies outside the page")
        return self


class OcrResult(AiModel):
    """The unsigned OCR body whose JCS bytes the provenance receipt covers."""

    pages: Annotated[tuple[OcrPage, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _pages_ordered(self) -> Self:
        _strictly_increasing(tuple(page.index for page in self.pages), "page indexes")
        return self


class OcrResponse(AiModel):
    """Phase-2 (dispatch) answer: the result and its signed receipt."""

    result: OcrResult
    execution: ExecutionReceipt

    @model_validator(mode="after")
    def _is_ocr(self) -> Self:
        require_capability(self.execution, Capability.OCR)
        return self


__all__ = [
    "OcrImage",
    "OcrOptions",
    "OcrPage",
    "OcrRequest",
    "OcrResponse",
    "OcrResult",
    "OcrSpoolResult",
    "PixelBox",
]
