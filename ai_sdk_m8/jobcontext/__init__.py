"""
Single-use job contexts and OCR receipt payloads on the C-03 signed-object rule.

A job context authorises exactly one gateway execution call
(``max_uses = 1``). It is signed by the authorising service immediately
before the call, travels in ``X-AI-Job-Context`` and is never queued.

Importing this module needs no extra; :func:`sign`, :func:`verify` and
``python -m ai_sdk_m8.jobcontext keygen --out <seed-file>`` need the
``jobcontext`` extra.
"""

from ai_sdk_m8.jobcontext._context import (
    DEFAULT_DISPATCH_MAX_TTL_SECONDS,
    ContextExpiredError,
    ContextInvalidError,
    JobContextError,
    JobContextToken,
    sign,
    verify,
)
from ai_sdk_m8.jobcontext._payloads import (
    JobContextPayload,
    JobContextPhase,
    OcrReceiptPayload,
)

__all__ = [
    "DEFAULT_DISPATCH_MAX_TTL_SECONDS",
    "ContextExpiredError",
    "ContextInvalidError",
    "JobContextError",
    "JobContextPayload",
    "JobContextPhase",
    "JobContextToken",
    "OcrReceiptPayload",
    "sign",
    "verify",
]
