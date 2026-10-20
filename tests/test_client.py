"""The sync and async gateway clients against a stub transport (T13)."""

import asyncio
import gc
import inspect
import io
import json
import re
import subprocess
import sys
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import httpx
import pytest
from client_samples import (
    BINDING_ID,
    CREDENTIAL_ID,
    MODEL_ID,
    PROVIDER_ID,
    TENANT_ID,
    USER_ID,
    binding_public,
    credential_public,
    credential_validation,
    embed_response,
    gateway_meta,
    model_admin,
    ocr_response,
    profile_admin,
    profile_public,
    profile_revision,
    provider_admin,
    remote_artifact,
    rerank_response,
    spool_result,
    structured_output_response,
)
from schema_samples import EXECUTION_ID

from ai_sdk_m8.client import (
    AiGatewayClient,
    AiGatewayHTTPError,
    AiGatewayRedirectError,
    AiGatewayResponseError,
    AsyncAiGatewayClient,
    BearerJwt,
    IncompatibleGatewayError,
    ServiceClient,
    routes,
)
from ai_sdk_m8.headers import (
    INTERNAL_CLIENT_HEADER,
    INTERNAL_TOKEN_HEADER,
    JOB_CONTEXT_HEADER,
)
from ai_sdk_m8.jobcontext import JobContextToken
from ai_sdk_m8.schemas import (
    AiErrorCode,
    AiGatewayError,
    EmbedRequest,
    OcrOptions,
    OcrRequest,
    RerankRequest,
    StructuredOutputRequest,
)
from ai_sdk_m8.schemas.management import (
    BindingCreate,
    BindingUpdate,
    CredentialCreate,
    CredentialRotate,
    CredentialUpdate,
    ModelCreate,
    ModelUpdate,
    ProfileCreate,
    ProfileUpdate,
    ProviderCreate,
    ProviderUpdate,
)

BASE = "http://ai-gateway:8000/ai"
SECRET = "service-secret-canary-" + "s" * 40
JWT = "header.payload-canary.signature"
TOKEN_A = JobContextToken("eyJjb250ZXh0IjoiQSJ9.c2lnLUE")
TOKEN_B = JobContextToken("eyJjb250ZXh0IjoiQiJ9.c2lnLUI")
SERVICE = ServiceClient("media-service", SECRET)
USER = BearerJwt(JWT)

Handler = Callable[[httpx.Request], httpx.Response]


class Recorder:
    """A stub gateway: records requests and answers with a fixed response."""

    def __init__(self, status: int = 200, body: object = None) -> None:
        self.status = status
        self.body = body
        self.requests: list[httpx.Request] = []
        self.contents: list[bytes] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.contents.append(request.read())
        self.requests.append(request)
        if self.body is None:
            return httpx.Response(self.status)
        return httpx.Response(self.status, json=self.body)

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]


def sync_client(handler: Handler, auth: Any = SERVICE) -> AiGatewayClient:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return AiGatewayClient(BASE, auth, http_client=http)


def async_client(handler: Handler, auth: Any = SERVICE) -> AsyncAiGatewayClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return AsyncAiGatewayClient(BASE, auth, http_client=http)


def run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


# --- auth strategies ---------------------------------------------------------


def test_auth_strategies_redact_their_secrets() -> None:
    assert SECRET not in repr(SERVICE)
    assert (
        repr(SERVICE) == "ServiceClient(client_id='media-service', secret=<redacted>)"
    )
    assert JWT not in repr(USER)
    assert repr(USER) == "BearerJwt(token=<redacted>)"
    client = AiGatewayClient(BASE, SERVICE)
    assert SECRET not in repr(client)
    client.close()


def test_auth_strategy_headers() -> None:
    assert SERVICE.headers() == {
        INTERNAL_CLIENT_HEADER: "media-service",
        INTERNAL_TOKEN_HEADER: SECRET,
    }
    assert SERVICE.client_id == "media-service"
    assert USER.headers() == {"Authorization": f"Bearer {JWT}"}


@pytest.mark.parametrize(
    ("client_id", "secret"),
    [
        ("", "x"),
        ("a b", "x"),
        ("é", "x"),
        ("a" * 129, "x"),
        (7, "x"),
        ("ok", ""),
        ("ok", "line\nbreak"),
        ("ok", 5),
    ],
)
def test_service_client_refuses_bad_values(client_id: Any, secret: Any) -> None:
    with pytest.raises(ValueError):
        ServiceClient(client_id, secret)


def test_bearer_accepts_secret_str_and_refuses_empty() -> None:
    from pydantic import SecretStr

    assert BearerJwt(SecretStr("t")).headers() == {"Authorization": "Bearer t"}
    with pytest.raises(ValueError):
        BearerJwt("")


@pytest.mark.parametrize(
    "target",
    [ServiceClient, BearerJwt, AiGatewayClient, AsyncAiGatewayClient],
)
def test_no_constructor_accepts_a_job_context(target: type) -> None:
    assert "job_context" not in inspect.signature(target).parameters


# --- base url and parameters -------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "ftp://x/ai",
        "http:///ai",
        "http://u:p@host/ai",
        "http://host/ai?x=1",
        "http://host/ai#f",
        "/relative",
    ],
)
def test_base_url_refused(url: str) -> None:
    with pytest.raises(ValueError):
        AiGatewayClient(url, SERVICE)


def test_base_url_must_be_a_string() -> None:
    with pytest.raises(TypeError):
        AiGatewayClient(b"http://host", SERVICE)  # type: ignore[arg-type]


def test_trailing_slash_is_normalised() -> None:
    rec = Recorder(body=gateway_meta())
    http = httpx.Client(transport=httpx.MockTransport(rec))
    AiGatewayClient(BASE + "/", None, http_client=http).meta()
    assert str(rec.last.url) == f"{BASE}/meta"


@pytest.mark.parametrize("key", ["Bad", "-x", "a/b", "", "a" * 65])
def test_profile_key_parameter_validated(key: str) -> None:
    with pytest.raises(ValueError, match="profile key"):
        sync_client(Recorder()).get_profile(key)


def test_uuid_parameters_validated() -> None:
    client = sync_client(Recorder(), USER)
    with pytest.raises(ValueError, match="provider_id must be a UUID"):
        client.admin.providers.get("../etc")
    with pytest.raises(ValueError, match="tenant_id must be a UUID"):
        client.admin.tenant("x")


# --- execution ---------------------------------------------------------------


def _assert_execution_headers(request: httpx.Request, token: str) -> None:
    assert request.headers[INTERNAL_CLIENT_HEADER] == "media-service"
    assert request.headers[INTERNAL_TOKEN_HEADER] == SECRET
    assert request.headers[JOB_CONTEXT_HEADER] == token
    assert "authorization" not in request.headers


EXECUTIONS: list[tuple[str, str, Callable[[Any], Any], object]] = [
    (
        "embed",
        "v1/execute/embed",
        lambda c: c.embed(
            EmbedRequest(profile_key="embed.small", inputs=("a",)), job_context=TOKEN_A
        ),
        embed_response(),
    ),
    (
        "rerank",
        "v1/execute/rerank",
        lambda c: c.rerank(
            RerankRequest(profile_key="rr", query="q", documents=("d",)),
            job_context=TOKEN_A,
        ),
        rerank_response(),
    ),
    (
        "structured_output",
        "v1/execute/structured-output",
        lambda c: c.structured_output(
            StructuredOutputRequest(
                profile_key="so", input="x", schema_name="S", json_schema={}
            ),
            job_context=TOKEN_A,
        ),
        structured_output_response(),
    ),
    (
        "ocr_dispatch",
        f"v1/execute/ocr/{EXECUTION_ID}:dispatch",
        lambda c: c.ocr_dispatch(EXECUTION_ID, job_context=TOKEN_A),
        ocr_response(),
    ),
]


@pytest.mark.parametrize(
    ("name", "path", "call", "answer"), EXECUTIONS, ids=[e[0] for e in EXECUTIONS]
)
def test_execution_methods(
    name: str, path: str, call: Callable[[Any], Any], answer: object
) -> None:
    rec = Recorder(body=answer)
    result = call(sync_client(rec))
    assert rec.last.method == "POST"
    assert str(rec.last.url) == f"{BASE}/{path}"
    _assert_execution_headers(rec.last, TOKEN_A)
    assert result.model_dump(mode="json") == answer


@pytest.mark.parametrize(
    ("name", "path", "call", "answer"), EXECUTIONS, ids=[e[0] for e in EXECUTIONS]
)
def test_async_execution_methods(
    name: str, path: str, call: Callable[[Any], Any], answer: object
) -> None:
    rec = Recorder(body=answer)
    result = run(call(async_client(rec)))
    assert str(rec.last.url) == f"{BASE}/{path}"
    _assert_execution_headers(rec.last, TOKEN_A)
    assert result.model_dump(mode="json") == answer


def test_execution_bodies_are_the_request_models() -> None:
    rec = Recorder(body=embed_response())
    sync_client(rec).embed(
        EmbedRequest(profile_key="embed.small", inputs=("a", "b")), job_context=TOKEN_A
    )
    assert json.loads(rec.contents[-1]) == {
        "profile_key": "embed.small",
        "inputs": ["a", "b"],
    }
    rec = Recorder(body=ocr_response())
    sync_client(rec).ocr_dispatch(str(EXECUTION_ID), job_context=TOKEN_A)
    assert rec.contents[-1] == b""


class ChunkRecorder(io.RawIOBase):
    """A document that records every read size and never returns it all at once."""

    def __init__(self, size: int) -> None:
        self._data = io.BytesIO(bytes(i % 251 for i in range(size)))
        self.reads: list[int] = []

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        self.reads.append(size)
        return self._data.read(size)

    def readinto(self, buffer: Any) -> int:  # pragma: no cover - unused by httpx
        raise AssertionError("readinto is not expected")


def _multipart_parts(
    request: httpx.Request, content: bytes
) -> list[tuple[bytes, bytes]]:
    boundary = request.headers["content-type"].split("boundary=")[1].encode()
    parts = content.split(b"--" + boundary)[1:-1]
    out = []
    for part in parts:
        head, _, body = part.partition(b"\r\n\r\n")
        out.append((head.strip(), body[:-2]))
    return out


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_ocr_spool_streams_two_ordered_parts(mode: str) -> None:
    rec = Recorder(body=spool_result())
    document = ChunkRecorder(300 * 1024)
    request = OcrRequest(profile_key="ocr", options=OcrOptions(pages=(0, 1)))
    if mode == "sync":
        result = sync_client(rec).ocr_spool(document, request, job_context=TOKEN_B)
    else:
        result = run(
            async_client(rec).ocr_spool(document, request, job_context=TOKEN_B)
        )
    assert str(result.spool_id) == str(EXECUTION_ID)
    _assert_execution_headers(rec.last, TOKEN_B)
    assert str(rec.last.url) == f"{BASE}/v1/execute/ocr"
    # streamed in bounded chunks, never read whole
    assert len(document.reads) > 2
    assert all(0 < size <= 64 * 1024 for size in document.reads)
    parts = _multipart_parts(rec.last, rec.contents[-1])
    assert [re.search(rb'name="([a-z]+)"', p[0]).group(1) for p in parts] == [  # type: ignore[union-attr]
        b"options",
        b"document",
    ]
    options_head, options_body = parts[0]
    assert b"filename" not in options_head
    assert json.loads(options_body) == json.loads(request.model_dump_json())
    document_head, document_body = parts[1]
    assert b'filename="document"' in document_head
    assert document_body == bytes(i % 251 for i in range(300 * 1024))


def test_ocr_spool_requires_an_ocr_request() -> None:
    with pytest.raises(TypeError, match="OcrRequest"):
        sync_client(Recorder()).ocr_spool(
            io.BytesIO(b"x"),
            {"profile_key": "ocr"},
            job_context=TOKEN_A,  # type: ignore[arg-type]
        )


# --- the job context ---------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda c, t: c.embed(
            EmbedRequest(profile_key="e", inputs=("a",)), job_context=t
        ),
        lambda c, t: c.ocr_dispatch(EXECUTION_ID, job_context=t),
        lambda c, t: c.ocr_spool(
            io.BytesIO(b"x"), OcrRequest(profile_key="o"), job_context=t
        ),
        lambda c, t: c.rerank(
            RerankRequest(profile_key="r", query="q", documents=("d",)), job_context=t
        ),
        lambda c, t: c.structured_output(
            StructuredOutputRequest(
                profile_key="s", input="i", schema_name="S", json_schema={}
            ),
            job_context=t,
        ),
    ],
)
@pytest.mark.parametrize(
    "bad", [None, "", 7, "no-dot", "a.b.c", "a." + "b" * 4100, "a b.c"]
)
def test_execution_without_a_valid_context_is_refused(
    call: Callable[[Any, Any], Any], bad: Any
) -> None:
    rec = Recorder()
    with pytest.raises(ValueError) as excinfo:
        call(sync_client(rec), bad)
    assert rec.requests == []
    if isinstance(bad, str) and bad:
        assert bad not in str(excinfo.value)


def test_a_plain_string_context_is_accepted_and_wrapped() -> None:
    rec = Recorder(body=embed_response())
    sync_client(rec).embed(
        EmbedRequest(profile_key="e", inputs=("a",)),
        job_context=str(TOKEN_A),  # type: ignore[arg-type]
    )
    assert rec.last.headers[JOB_CONTEXT_HEADER] == TOKEN_A


def test_each_call_sends_only_its_own_context() -> None:
    rec = Recorder(body=embed_response())
    client = sync_client(rec)
    request = EmbedRequest(profile_key="e", inputs=("a",))
    client.embed(request, job_context=TOKEN_A)
    client.embed(request, job_context=TOKEN_B)
    assert [r.headers[JOB_CONTEXT_HEADER] for r in rec.requests] == [TOKEN_A, TOKEN_B]
    client.list_profiles  # noqa: B018 - a non-execution call sends no context
    rec.body = [profile_public()]
    client.list_profiles()
    assert JOB_CONTEXT_HEADER not in rec.last.headers


def _reachable(root: object) -> list[object]:
    seen: dict[int, object] = {}
    stack = [root]
    while stack:
        obj = stack.pop()
        if id(obj) in seen or isinstance(obj, type | type(sys)):
            continue
        seen[id(obj)] = obj
        stack.extend(gc.get_referents(obj))
    return list(seen.values())


def test_the_client_keeps_no_reference_to_a_context() -> None:
    rec = Recorder(body=embed_response())
    client = sync_client(rec)
    token = JobContextToken("eyJ1bmlxdWUiOiJ6In0.dW5pcXVlLXNpZw")
    client.embed(EmbedRequest(profile_key="e", inputs=("a",)), job_context=token)
    rec.requests.clear()
    gc.collect()
    assert not any(obj is token for obj in _reachable(client))
    assert not any(
        isinstance(obj, str) and str(token) in obj for obj in _reachable(client)
    )


# --- auth per route ----------------------------------------------------------


def test_execution_refuses_a_jwt_client() -> None:
    rec = Recorder()
    with pytest.raises(TypeError, match="ServiceClient"):
        sync_client(rec, USER).embed(
            EmbedRequest(profile_key="e", inputs=("a",)), job_context=TOKEN_A
        )
    assert rec.requests == []


def test_management_refuses_a_service_client() -> None:
    rec = Recorder()
    with pytest.raises(TypeError, match="BearerJwt"):
        sync_client(rec, SERVICE).admin.providers.list()
    assert rec.requests == []


def test_profiles_need_some_auth() -> None:
    with pytest.raises(TypeError, match="BearerJwt or a ServiceClient"):
        sync_client(Recorder(), None).list_profiles()


@pytest.mark.parametrize("auth", [SERVICE, USER])
def test_profiles_accept_either_strategy(auth: Any) -> None:
    rec = Recorder(body=[profile_public()])
    profiles = sync_client(rec, auth).list_profiles()
    assert profiles[0].profile_key == "embed.small"
    assert str(rec.last.url) == f"{BASE}/v1/profiles"
    rec.body = profile_public()
    assert sync_client(rec, auth).get_profile("embed.small").revision == 1
    assert str(rec.last.url) == f"{BASE}/v1/profiles/embed.small"


def test_async_profiles() -> None:
    rec = Recorder(body=[profile_public()])
    assert len(run(async_client(rec).list_profiles())) == 1
    rec.body = profile_public()
    assert run(async_client(rec).get_profile("embed.small")).enabled


def test_meta_is_sent_without_credentials() -> None:
    rec = Recorder(body=gateway_meta())
    meta = sync_client(rec).meta()
    assert meta.gateway.user_byok_enabled is True
    assert INTERNAL_TOKEN_HEADER not in rec.last.headers
    assert "authorization" not in rec.last.headers


# --- errors ------------------------------------------------------------------


@pytest.mark.parametrize("code", list(AiErrorCode))
@pytest.mark.parametrize("mode", ["sync", "async"])
def test_every_gateway_error_code_maps_to_a_typed_error(
    code: AiErrorCode, mode: str
) -> None:
    rec = Recorder(status=503, body={"code": code.value, "request_id": "req-1"})
    request = EmbedRequest(profile_key="e", inputs=("a",))
    with pytest.raises(AiGatewayError) as excinfo:
        if mode == "sync":
            sync_client(rec).embed(request, job_context=TOKEN_A)
        else:
            run(async_client(rec).embed(request, job_context=TOKEN_A))
    assert excinfo.value.error.code is code
    assert str(excinfo.value) == f"{code.value} (request_id=req-1)"


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422, 500, 502])
@pytest.mark.parametrize("body", [None, {"detail": "Unauthorized"}, {"code": "nope"}])
def test_other_errors_are_http_errors(status: int, body: object) -> None:
    rec = Recorder(status=status, body=body)
    with pytest.raises(AiGatewayHTTPError) as excinfo:
        sync_client(rec).embed(
            EmbedRequest(profile_key="e", inputs=("a",)), job_context=TOKEN_A
        )
    assert excinfo.value.status_code == status
    assert str(excinfo.value) == f"gateway answered HTTP {status}"
    assert not isinstance(excinfo.value, AiGatewayRedirectError)


def test_a_bad_success_body_is_a_response_error() -> None:
    rec = Recorder(body={"result": "not this"})
    with pytest.raises(AiGatewayResponseError):
        sync_client(rec).embed(
            EmbedRequest(profile_key="e", inputs=("a",)), job_context=TOKEN_A
        )


def test_errors_never_carry_secrets() -> None:
    rec = Recorder(status=401, body={"detail": SECRET})
    with pytest.raises(AiGatewayHTTPError) as excinfo:
        sync_client(rec).embed(
            EmbedRequest(profile_key="e", inputs=("a",)), job_context=TOKEN_A
        )
    rendered = repr(excinfo.value) + str(excinfo.value) + repr(excinfo.value.args)
    for secret in (SECRET, TOKEN_A):
        assert secret not in rendered


def test_nothing_is_retried() -> None:
    rec = Recorder(status=503, body={"code": "timeout", "request_id": "r"})
    with pytest.raises(AiGatewayError):
        sync_client(rec).embed(
            EmbedRequest(profile_key="e", inputs=("a",)), job_context=TOKEN_A
        )
    assert len(rec.requests) == 1


# --- redirects ---------------------------------------------------------------


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirects_are_never_followed_even_when_the_client_would(status: int) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.host == "ai-gateway":
            return httpx.Response(status, headers={"location": "http://evil.example/x"})
        return httpx.Response(200, json=embed_response())

    http = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    client = AiGatewayClient(BASE, SERVICE, http_client=http)
    with pytest.raises(AiGatewayRedirectError) as excinfo:
        client.embed(EmbedRequest(profile_key="e", inputs=("a",)), job_context=TOKEN_A)
    assert excinfo.value.status_code == status
    assert seen == [f"{BASE}/v1/execute/embed"]


def test_async_redirect_is_not_followed() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return httpx.Response(307, headers={"location": "http://evil.example/x"})

    http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    )
    client = AsyncAiGatewayClient(BASE, SERVICE, http_client=http)
    with pytest.raises(AiGatewayRedirectError):
        run(client.ocr_dispatch(EXECUTION_ID, job_context=TOKEN_A))
    assert seen == ["ai-gateway"]


# --- compatibility -----------------------------------------------------------


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_compatible_gateway(mode: str) -> None:
    rec = Recorder(body=gateway_meta())
    if mode == "sync":
        meta = sync_client(rec).check_compatibility()
    else:
        meta = run(async_client(rec).check_compatibility())
    assert meta.version == "0.2.0"


def test_meta_ignores_fields_it_does_not_know() -> None:
    rec = Recorder(body=gateway_meta(build="later"))
    assert sync_client(rec).meta().service == "ai-gateway-m8"


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (
            {"contract": {"name": "other", "version": "1.0", "range": "x"}},
            "contract is not",
        ),
        (
            {"contract": {"name": "ai-gateway-m8", "version": "2.0", "range": "x"}},
            "major",
        ),
        (
            {"contract": {"name": "ai-gateway-m8", "version": "one", "range": "x"}},
            "major",
        ),
        ({"version": "0.1.9"}, "below"),
        ({"version": "1.0"}, "below"),
        ({"version": "dev"}, "below"),
    ],
)
def test_incompatible_gateway(changes: dict[str, object], message: str) -> None:
    rec = Recorder(body=gateway_meta(**changes))
    with pytest.raises(IncompatibleGatewayError, match=message):
        sync_client(rec).check_compatibility()


def test_newer_gateway_is_compatible() -> None:
    rec = Recorder(body=gateway_meta(version="1.4.2"))
    sync_client(rec).check_compatibility()


def test_compatibility_is_never_checked_implicitly() -> None:
    rec = Recorder(body=embed_response())
    sync_client(rec).embed(
        EmbedRequest(profile_key="e", inputs=("a",)), job_context=TOKEN_A
    )
    assert all(not str(r.url).endswith("/meta") for r in rec.requests)


# --- lifecycle ---------------------------------------------------------------


def test_owned_http_client_is_closed_and_injected_one_is_not() -> None:
    with AiGatewayClient(BASE, SERVICE) as owned:
        http = owned._http
        assert http.follow_redirects is False
        assert http.trust_env is False
    assert http.is_closed
    injected = httpx.Client(transport=httpx.MockTransport(Recorder()))
    with AiGatewayClient(BASE, SERVICE, http_client=injected):
        pass
    assert not injected.is_closed


def test_async_lifecycle() -> None:
    async def scenario() -> None:
        async with AsyncAiGatewayClient(BASE, SERVICE) as owned:
            http = owned._http
            assert http.trust_env is False
            assert SECRET not in repr(owned)
        assert http.is_closed
        injected = httpx.AsyncClient(transport=httpx.MockTransport(Recorder()))
        async with AsyncAiGatewayClient(BASE, SERVICE, http_client=injected):
            pass
        assert not injected.is_closed
        await injected.aclose()

    run(scenario())


# --- the admin namespace -----------------------------------------------------

TENANT = str(TENANT_ID)
CRED = str(CREDENTIAL_ID)
BIND = str(BINDING_ID)
SCOPES = [
    ("global", lambda a: a, "v1/admin"),
    ("tenant", lambda a: a.tenant(TENANT_ID), f"v1/tenants/{TENANT}"),
    ("me", lambda a: a.me, "v1/me"),
]
PROVIDER_CREATE = ProviderCreate(
    name="p",
    provider_type="ollama",
    base_url="http://ollama:11434",
    auth_type="none",
    boundary="local",
)
MODEL_CREATE = ModelCreate(
    provider_id=PROVIDER_ID,
    external_model_id="m",
    capabilities=("rerank",),
    model_version_label="v1",
)
CREDENTIAL_CREATE = CredentialCreate(provider_id=PROVIDER_ID, name="k", secret=SECRET)


def _admin_cases() -> list[tuple[str, Callable[[Any], Any], str, str, object, object]]:
    cases: list[tuple[str, Callable[[Any], Any], str, str, object, object]] = [
        (
            "providers.list",
            lambda a: a.providers.list(),
            "GET",
            "v1/admin/providers",
            None,
            [provider_admin()],
        ),
        (
            "providers.create",
            lambda a: a.providers.create(PROVIDER_CREATE),
            "POST",
            "v1/admin/providers",
            {
                "name": "p",
                "provider_type": "ollama",
                "base_url": "http://ollama:11434",
                "auth_type": "none",
                "boundary": "local",
            },
            provider_admin(),
        ),
        (
            "providers.get",
            lambda a: a.providers.get(PROVIDER_ID),
            "GET",
            f"v1/admin/providers/{PROVIDER_ID}",
            None,
            provider_admin(),
        ),
        (
            "providers.update",
            lambda a: a.providers.update(PROVIDER_ID, ProviderUpdate(enabled=False)),
            "PATCH",
            f"v1/admin/providers/{PROVIDER_ID}",
            {"enabled": False},
            provider_admin(),
        ),
        (
            "models.list",
            lambda a: a.models.list(),
            "GET",
            "v1/admin/models",
            None,
            [model_admin()],
        ),
        (
            "models.create",
            lambda a: a.models.create(MODEL_CREATE),
            "POST",
            "v1/admin/models",
            {
                "provider_id": str(PROVIDER_ID),
                "external_model_id": "m",
                "capabilities": ["rerank"],
                "model_version_label": "v1",
            },
            model_admin(),
        ),
        (
            "models.get",
            lambda a: a.models.get(MODEL_ID),
            "GET",
            f"v1/admin/models/{MODEL_ID}",
            None,
            model_admin(),
        ),
        (
            "models.update",
            lambda a: a.models.update(MODEL_ID, ModelUpdate(model_revision=None)),
            "PATCH",
            f"v1/admin/models/{MODEL_ID}",
            {"model_revision": None},
            model_admin(),
        ),
        (
            "profiles.list",
            lambda a: a.profiles.list(),
            "GET",
            "v1/admin/profiles",
            None,
            [profile_admin()],
        ),
        (
            "profiles.create",
            lambda a: a.profiles.create(
                ProfileCreate(profile_key="p", capability="rerank")
            ),
            "POST",
            "v1/admin/profiles",
            {"profile_key": "p", "capability": "rerank"},
            profile_admin(),
        ),
        (
            "profiles.get",
            lambda a: a.profiles.get("p"),
            "GET",
            "v1/admin/profiles/p",
            None,
            profile_admin(),
        ),
        (
            "profiles.update",
            lambda a: a.profiles.update("p", ProfileUpdate(execution_config={"k": 1})),
            "PATCH",
            "v1/admin/profiles/p",
            {"execution_config": {"k": 1}},
            profile_admin(),
        ),
        (
            "profiles.revisions",
            lambda a: a.profiles.revisions("p"),
            "GET",
            "v1/admin/profiles/p/revisions",
            None,
            [profile_revision()],
        ),
        (
            "user_credentials.list",
            lambda a: a.user_credentials.list(USER_ID),
            "GET",
            f"v1/admin/user-credentials?owner_user_id={USER_ID}",
            None,
            [credential_public()],
        ),
        (
            "user_credentials.disable",
            lambda a: a.user_credentials.disable(CREDENTIAL_ID),
            "POST",
            f"v1/admin/user-credentials/{CRED}:disable",
            None,
            credential_public(),
        ),
        (
            "user_credentials.delete",
            lambda a: a.user_credentials.delete(CREDENTIAL_ID),
            "DELETE",
            f"v1/admin/user-credentials/{CRED}",
            None,
            None,
        ),
    ]
    for scope_name, scope, base in SCOPES:
        cases += [
            (
                f"{scope_name}.credentials.list",
                lambda a, s=scope: s(a).credentials.list(),
                "GET",
                f"{base}/credentials",
                None,
                [credential_public()],
            ),
            (
                f"{scope_name}.credentials.create",
                lambda a, s=scope: s(a).credentials.create(CREDENTIAL_CREATE),
                "POST",
                f"{base}/credentials",
                {"provider_id": str(PROVIDER_ID), "name": "k", "secret": SECRET},
                credential_public(),
            ),
            (
                f"{scope_name}.credentials.get",
                lambda a, s=scope: s(a).credentials.get(CREDENTIAL_ID),
                "GET",
                f"{base}/credentials/{CRED}",
                None,
                credential_public(),
            ),
            (
                f"{scope_name}.credentials.update",
                lambda a, s=scope: s(a).credentials.update(
                    CREDENTIAL_ID, CredentialUpdate(incident_listing_consent=True)
                ),
                "PATCH",
                f"{base}/credentials/{CRED}",
                {"incident_listing_consent": True},
                credential_public(),
            ),
            (
                f"{scope_name}.credentials.delete",
                lambda a, s=scope: s(a).credentials.delete(CREDENTIAL_ID),
                "DELETE",
                f"{base}/credentials/{CRED}",
                None,
                None,
            ),
            (
                f"{scope_name}.credentials.rotate",
                lambda a, s=scope: s(a).credentials.rotate(
                    CREDENTIAL_ID, CredentialRotate(secret=SECRET)
                ),
                "POST",
                f"{base}/credentials/{CRED}:rotate",
                {"secret": SECRET},
                credential_public(),
            ),
            (
                f"{scope_name}.credentials.validate",
                lambda a, s=scope: s(a).credentials.validate(CREDENTIAL_ID),
                "POST",
                f"{base}/credentials/{CRED}:validate",
                None,
                credential_validation(),
            ),
            (
                f"{scope_name}.credentials.disable",
                lambda a, s=scope: s(a).credentials.disable(CREDENTIAL_ID),
                "POST",
                f"{base}/credentials/{CRED}:disable",
                None,
                credential_public(),
            ),
            (
                f"{scope_name}.credentials.enable",
                lambda a, s=scope: s(a).credentials.enable(CREDENTIAL_ID),
                "POST",
                f"{base}/credentials/{CRED}:enable",
                None,
                credential_public(),
            ),
            (
                f"{scope_name}.credentials.reconfirm",
                lambda a, s=scope: s(a).credentials.reconfirm(CREDENTIAL_ID),
                "POST",
                f"{base}/credentials/{CRED}:reconfirm",
                None,
                credential_public(),
            ),
            (
                f"{scope_name}.credentials.remote_artifacts",
                lambda a, s=scope: s(a).credentials.remote_artifacts(CREDENTIAL_ID),
                "GET",
                f"{base}/credentials/{CRED}/remote-artifacts",
                None,
                [remote_artifact()],
            ),
            (
                f"{scope_name}.bindings.list",
                lambda a, s=scope: s(a).bindings.list(),
                "GET",
                f"{base}/bindings",
                None,
                [binding_public()],
            ),
            (
                f"{scope_name}.bindings.create",
                lambda a, s=scope: s(a).bindings.create(
                    BindingCreate(profile_key="p", model_id=MODEL_ID)
                ),
                "POST",
                f"{base}/bindings",
                {"profile_key": "p", "model_id": str(MODEL_ID)},
                binding_public(),
            ),
            (
                f"{scope_name}.bindings.get",
                lambda a, s=scope: s(a).bindings.get(BINDING_ID),
                "GET",
                f"{base}/bindings/{BIND}",
                None,
                binding_public(),
            ),
            (
                f"{scope_name}.bindings.update",
                lambda a, s=scope: s(a).bindings.update(
                    BINDING_ID, BindingUpdate(credential_id=None)
                ),
                "PATCH",
                f"{base}/bindings/{BIND}",
                {"credential_id": None},
                binding_public(),
            ),
            (
                f"{scope_name}.bindings.delete",
                lambda a, s=scope: s(a).bindings.delete(BINDING_ID),
                "DELETE",
                f"{base}/bindings/{BIND}",
                None,
                None,
            ),
        ]
    return cases


ADMIN_CASES = _admin_cases()


@pytest.mark.parametrize(
    ("name", "call", "method", "path", "body", "answer"),
    ADMIN_CASES,
    ids=[c[0] for c in ADMIN_CASES],
)
@pytest.mark.parametrize("mode", ["sync", "async"])
def test_admin_namespace(
    mode: str,
    name: str,
    call: Callable[[Any], Any],
    method: str,
    path: str,
    body: object,
    answer: object,
) -> None:
    status = 204 if answer is None else (201 if name.endswith("create") else 200)
    rec = Recorder(status=status, body=answer)
    if mode == "sync":
        result = call(sync_client(rec, USER).admin)
    else:
        result = run(call(async_client(rec, USER).admin))
    request = rec.last
    assert request.method == method
    assert str(request.url) == f"{BASE}/{path}"
    assert request.headers["authorization"] == f"Bearer {JWT}"
    assert INTERNAL_TOKEN_HEADER not in request.headers
    assert JOB_CONTEXT_HEADER not in request.headers
    if body is None:
        assert rec.contents[-1] == b""
    else:
        assert json.loads(rec.contents[-1]) == body
    if answer is None:
        assert result is None
    elif isinstance(answer, list):
        assert [r.model_dump(mode="json") for r in result] == answer
    else:
        assert result.model_dump(mode="json") == answer


def _template_regex(path: str) -> "re.Pattern[str]":
    return re.compile(re.sub(r"\\\{[a-z_]+\\\}", "[^/]+", re.escape(path)))


def test_every_route_the_client_calls_is_in_the_route_table_and_back() -> None:
    table = routes.all_routes()
    assert len(set(table)) == len(table)
    compiled = [(route, _template_regex(route.path)) for route in table]
    called = [(case[2], case[3].split("?")[0]) for case in ADMIN_CASES]
    called += [("POST", e[1]) for e in EXECUTIONS]
    called += [
        ("POST", "v1/execute/ocr"),
        ("GET", "meta"),
        ("GET", "v1/profiles"),
        ("GET", "v1/profiles/embed.small"),
    ]
    matched = set()
    for method, path in called:
        hits = [r for r, rx in compiled if r.method == method and rx.fullmatch(path)]
        assert len(hits) == 1, (method, path, hits)
        matched.add(hits[0])
    assert matched == set(table)


# --- static typing -----------------------------------------------------------

_TYPING_PROBE = """
from ai_sdk_m8.client import AiGatewayClient, ServiceClient
from ai_sdk_m8.schemas import EmbedRequest

client = AiGatewayClient("http://gw/ai", ServiceClient("c", "s"))
client.embed(EmbedRequest(profile_key="e", inputs=("a",)))
"""


def test_an_execution_call_without_a_context_is_a_type_error(tmp_path: Path) -> None:
    probe = tmp_path / "probe.py"
    probe.write_text(_TYPING_PROBE)
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", str(probe)],
        capture_output=True,
        text=True,
        check=False,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert result.returncode == 1, result.stdout
    assert 'Missing named argument "job_context"' in result.stdout
