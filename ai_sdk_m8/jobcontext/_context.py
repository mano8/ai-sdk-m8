"""
Signing and stateless verification of job contexts (C-03, S-04).

:func:`verify` covers everything a single token proves by itself: the
signed-object rule under ``m8.ai.job-context.v1``, the closed claim model,
the audience, the clock rule and the TTL caps. The gateway adds what needs
its state: ``iss`` is a registered client with ``job-context:issue`` that
owns ``kid``, the presenting client equals ``azp`` and holds
``execute:<capability>``, the request's capability and profile equal the
claims, and the atomic ``(iss, jti)`` redemption on the database clock.
"""

from collections.abc import Mapping
from typing import ClassVar, Final

from ai_sdk_m8.jobcontext._payloads import JobContextPayload, JobContextPhase
from ai_sdk_m8.schemas.errors import AiErrorCode
from ai_sdk_m8.signed import Domain, SignedObjectError, sign_object, verify_object

#: Default D-44 ceiling on a dispatch context's ``exp - iat``.
DEFAULT_DISPATCH_MAX_TTL_SECONDS: Final = 30


class JobContextToken(str):
    """A compact job context; its ``repr`` never shows the signature."""

    __slots__ = ()

    def __repr__(self) -> str:
        payload, _, _ = self.partition(".")
        return f"JobContextToken('{payload}.<redacted>')"


class JobContextError(ValueError):
    """A refused job context; ``code`` is the gateway's typed rejection."""

    code: ClassVar[AiErrorCode]

    def __init__(self) -> None:
        super().__init__(self.code.value)


class ContextInvalidError(JobContextError):
    """Malformed, unsigned, mis-addressed, not yet valid or over its TTL."""

    code = AiErrorCode.CONTEXT_INVALID


class ContextExpiredError(JobContextError):
    """Otherwise valid, but ``now >= exp`` (no leeway on ``exp``)."""

    code = AiErrorCode.CONTEXT_EXPIRED


def sign(payload: JobContextPayload, *, seed: bytes) -> JobContextToken:
    """Sign ``payload``; its ``kid`` must be the one ``seed`` derives."""
    return JobContextToken(sign_object(payload, domain=Domain.JOB_CONTEXT, seed=seed))


def _check_clock(
    payload: JobContextPayload, now: int, max_ttl: int, skew: int, dispatch_ttl: int
) -> None:
    if payload.iat > now + skew or payload.nbf > now + skew:
        raise ContextInvalidError
    if payload.exp - payload.iat > max_ttl:
        raise ContextInvalidError
    if (
        payload.phase is JobContextPhase.DISPATCH
        and payload.exp - payload.iat > dispatch_ttl
    ):
        raise ContextInvalidError
    if now >= payload.exp:
        raise ContextExpiredError


def verify(
    token: str,
    *,
    public_keys: Mapping[str, bytes],
    aud: str,
    now: int,
    max_ttl: int,
    skew: int,
    max_dispatch_ttl: int = DEFAULT_DISPATCH_MAX_TTL_SECONDS,
) -> JobContextPayload:
    """
    Verify ``token`` for this installation at ``now`` (integer epoch seconds).

    ``aud`` is ``ai-gateway/<deployment_id>``. ``iat`` and ``nbf`` may lead
    ``now`` by at most ``skew``; ``exp`` gets no leeway. Raises
    :class:`ContextInvalidError` or :class:`ContextExpiredError`, never with
    the token in the message.
    """
    if max_ttl < 1 or max_dispatch_ttl < 1 or skew < 0:
        raise ValueError("max_ttl and max_dispatch_ttl must be >= 1, skew >= 0")
    if not isinstance(token, str):
        raise ContextInvalidError
    try:
        payload = verify_object(
            token,
            domain=Domain.JOB_CONTEXT,
            public_keys=public_keys,
            model=JobContextPayload,
        )
    except SignedObjectError:
        raise ContextInvalidError from None
    if payload.aud != aud:
        raise ContextInvalidError
    _check_clock(payload, now, max_ttl, skew, max_dispatch_ttl)
    return payload


__all__ = [
    "DEFAULT_DISPATCH_MAX_TTL_SECONDS",
    "ContextExpiredError",
    "ContextInvalidError",
    "JobContextError",
    "JobContextToken",
    "sign",
    "verify",
]
