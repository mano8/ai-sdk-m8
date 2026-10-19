"""
The synchronous and asynchronous gateway clients.

Configuration is explicit — a base URL, an auth strategy and optionally an
``httpx`` client — and never read from the environment. A client the SDK
builds itself ignores proxy variables (``trust_env=False``). Every request
is sent with redirects refused, nothing is retried, and a job context is
taken per call, sent once and not kept.
"""

from types import TracebackType
from typing import IO, Self, TypeVar
from uuid import UUID

import httpx

from ai_sdk_m8.client import _ops
from ai_sdk_m8.client._admin import Admin, AsyncAdmin
from ai_sdk_m8.client._auth import Auth
from ai_sdk_m8.client._core import (
    DEFAULT_TIMEOUT_SECONDS,
    Call,
    JobContext,
    build_request,
    normalise_base_url,
    parse_response,
)
from ai_sdk_m8.compatibility import check_gateway_meta
from ai_sdk_m8.schemas.embedding import EmbedRequest, EmbedResponse
from ai_sdk_m8.schemas.meta import GatewayMeta
from ai_sdk_m8.schemas.ocr import OcrRequest, OcrResponse, OcrSpoolResult
from ai_sdk_m8.schemas.profiles import ProfilePublic
from ai_sdk_m8.schemas.rerank import RerankRequest, RerankResponse
from ai_sdk_m8.schemas.structured_output import (
    StructuredOutputRequest,
    StructuredOutputResponse,
)

T = TypeVar("T")


class AiGatewayClient:
    """
    Synchronous client of the AI gateway.

    ``base_url`` includes the gateway's ``API_PREFIX`` (for example
    ``http://ai-gateway:8000/ai``). Use a :class:`ServiceClient` for the
    execution routes and a :class:`BearerJwt` for ``admin``.
    """

    def __init__(
        self,
        base_url: str,
        auth: Auth | None = None,
        *,
        http_client: httpx.Client | None = None,
        timeout: float | httpx.Timeout = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = normalise_base_url(base_url)
        self._auth = auth
        self._owns_http = http_client is None
        self._http = http_client or httpx.Client(
            timeout=timeout, follow_redirects=False, trust_env=False
        )
        self.admin = Admin(self._send)

    def __repr__(self) -> str:
        return f"AiGatewayClient(base_url={self._base_url!r}, auth={self._auth!r})"

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the ``httpx`` client if this client built it."""
        if self._owns_http:
            self._http.close()

    def _send(self, call: Call[T]) -> T:
        request = build_request(self._http, self._base_url, self._auth, call)
        response = self._http.send(request, follow_redirects=False)
        try:
            return parse_response(call, response)
        finally:
            response.close()

    # --- meta and profiles ---------------------------------------------------

    def meta(self) -> GatewayMeta:
        """The gateway's ``/meta``."""
        return self._send(_ops.meta())

    def check_compatibility(self) -> GatewayMeta:
        """Read ``/meta`` and raise ``IncompatibleGatewayError`` if unsupported."""
        meta = self.meta()
        check_gateway_meta(meta)
        return meta

    def list_profiles(self) -> tuple[ProfilePublic, ...]:
        """Every published profile."""
        return self._send(_ops.list_profiles())

    def get_profile(self, profile_key: str) -> ProfilePublic:
        """One published profile."""
        return self._send(_ops.get_profile(profile_key))

    # --- execution -----------------------------------------------------------

    def ocr_spool(
        self, document: IO[bytes], options: OcrRequest, *, job_context: JobContext
    ) -> OcrSpoolResult:
        """
        OCR phase 1: stream ``document`` to the gateway's spool.

        ``job_context`` must be a ``phase = spool`` context. No provider is
        called; dispatch the returned ``spool_id`` with :meth:`ocr_dispatch`.
        """
        return self._send(_ops.ocr_spool(document, options, job_context))

    def ocr_dispatch(
        self, spool_id: UUID | str, *, job_context: JobContext
    ) -> OcrResponse:
        """OCR phase 2: dispatch a spool under a fresh ``phase = dispatch`` context."""
        return self._send(_ops.ocr_dispatch(spool_id, job_context))

    def embed(self, request: EmbedRequest, *, job_context: JobContext) -> EmbedResponse:
        """Embed texts."""
        return self._send(_ops.embed(request, job_context))

    def rerank(
        self, request: RerankRequest, *, job_context: JobContext
    ) -> RerankResponse:
        """Rerank candidate excerpts (always a ``local`` provider)."""
        return self._send(_ops.rerank(request, job_context))

    def structured_output(
        self, request: StructuredOutputRequest, *, job_context: JobContext
    ) -> StructuredOutputResponse:
        """Extract a JSON object that satisfies the request's schema."""
        return self._send(_ops.structured_output(request, job_context))


class AsyncAiGatewayClient:
    """Asynchronous client of the AI gateway; see :class:`AiGatewayClient`."""

    def __init__(
        self,
        base_url: str,
        auth: Auth | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float | httpx.Timeout = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = normalise_base_url(base_url)
        self._auth = auth
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(
            timeout=timeout, follow_redirects=False, trust_env=False
        )
        self.admin = AsyncAdmin(self._send)

    def __repr__(self) -> str:
        return f"AsyncAiGatewayClient(base_url={self._base_url!r}, auth={self._auth!r})"

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the ``httpx`` client if this client built it."""
        if self._owns_http:
            await self._http.aclose()

    async def _send(self, call: Call[T]) -> T:
        request = build_request(self._http, self._base_url, self._auth, call)
        response = await self._http.send(request, follow_redirects=False)
        try:
            return parse_response(call, response)
        finally:
            await response.aclose()

    # --- meta and profiles ---------------------------------------------------

    async def meta(self) -> GatewayMeta:
        """The gateway's ``/meta``."""
        return await self._send(_ops.meta())

    async def check_compatibility(self) -> GatewayMeta:
        """Read ``/meta`` and raise ``IncompatibleGatewayError`` if unsupported."""
        meta = await self.meta()
        check_gateway_meta(meta)
        return meta

    async def list_profiles(self) -> tuple[ProfilePublic, ...]:
        """Every published profile."""
        return await self._send(_ops.list_profiles())

    async def get_profile(self, profile_key: str) -> ProfilePublic:
        """One published profile."""
        return await self._send(_ops.get_profile(profile_key))

    # --- execution -----------------------------------------------------------

    async def ocr_spool(
        self, document: IO[bytes], options: OcrRequest, *, job_context: JobContext
    ) -> OcrSpoolResult:
        """OCR phase 1; see :meth:`AiGatewayClient.ocr_spool`."""
        return await self._send(_ops.ocr_spool(document, options, job_context))

    async def ocr_dispatch(
        self, spool_id: UUID | str, *, job_context: JobContext
    ) -> OcrResponse:
        """OCR phase 2; see :meth:`AiGatewayClient.ocr_dispatch`."""
        return await self._send(_ops.ocr_dispatch(spool_id, job_context))

    async def embed(
        self, request: EmbedRequest, *, job_context: JobContext
    ) -> EmbedResponse:
        """Embed texts."""
        return await self._send(_ops.embed(request, job_context))

    async def rerank(
        self, request: RerankRequest, *, job_context: JobContext
    ) -> RerankResponse:
        """Rerank candidate excerpts (always a ``local`` provider)."""
        return await self._send(_ops.rerank(request, job_context))

    async def structured_output(
        self, request: StructuredOutputRequest, *, job_context: JobContext
    ) -> StructuredOutputResponse:
        """Extract a JSON object that satisfies the request's schema."""
        return await self._send(_ops.structured_output(request, job_context))
