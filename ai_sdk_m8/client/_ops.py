"""
Every gateway operation, described once as a :class:`Call`.

The sync and async clients and their management namespaces call these
builders and only differ in how the resulting call is sent.
"""

from typing import IO
from uuid import UUID

from ai_sdk_m8.client import routes
from ai_sdk_m8.client._core import (
    AuthKind,
    Call,
    list_parser,
    model_parser,
    multipart_document,
    no_content,
    profile_key_param,
    require_job_context,
    uuid_param,
)
from ai_sdk_m8.schemas.embedding import EmbedRequest, EmbedResponse
from ai_sdk_m8.schemas.management import (
    BindingCreate,
    BindingPublic,
    BindingUpdate,
    CredentialCreate,
    CredentialPublic,
    CredentialRotate,
    CredentialUpdate,
    CredentialValidation,
    ModelAdmin,
    ModelCreate,
    ModelUpdate,
    ProfileAdmin,
    ProfileCreate,
    ProfileRevisionAdmin,
    ProfileUpdate,
    ProviderAdmin,
    ProviderCreate,
    ProviderUpdate,
    RemoteArtifactPublic,
    dump_body,
)
from ai_sdk_m8.schemas.meta import GatewayMeta
from ai_sdk_m8.schemas.ocr import OcrRequest, OcrResponse, OcrSpoolResult
from ai_sdk_m8.schemas.profiles import ProfilePublic
from ai_sdk_m8.schemas.rerank import RerankRequest, RerankResponse
from ai_sdk_m8.schemas.structured_output import (
    StructuredOutputRequest,
    StructuredOutputResponse,
)

# --- meta and profiles -------------------------------------------------------


def meta() -> Call[GatewayMeta]:
    """``GET /meta`` (unauthenticated)."""
    return Call(routes.META, AuthKind.NONE, model_parser(GatewayMeta))


def list_profiles() -> Call[tuple[ProfilePublic, ...]]:
    """``GET /v1/profiles`` (reader JWT or ``profiles:read`` client)."""
    return Call(routes.PROFILES, AuthKind.SERVICE_OR_JWT, list_parser(ProfilePublic))


def get_profile(profile_key: str) -> Call[ProfilePublic]:
    """``GET /v1/profiles/{profile_key}``."""
    return Call(
        routes.PROFILE,
        AuthKind.SERVICE_OR_JWT,
        model_parser(ProfilePublic),
        params={"profile_key": profile_key_param(profile_key)},
    )


# --- execution ---------------------------------------------------------------


def _json(
    body: OcrRequest | EmbedRequest | RerankRequest | StructuredOutputRequest,
) -> object:
    return body.model_dump(mode="json")


def ocr_spool(
    document: IO[bytes], options: OcrRequest, job_context: object
) -> Call[OcrSpoolResult]:
    """Phase 1 of OCR: spool and verify the document, no provider call."""
    token = require_job_context(job_context)
    if not isinstance(options, OcrRequest):
        raise TypeError("options must be an OcrRequest")
    return Call(
        routes.EXECUTE_OCR,
        AuthKind.SERVICE,
        model_parser(OcrSpoolResult),
        files=multipart_document(options.model_dump_json().encode("utf-8"), document),
        job_context=token,
    )


def ocr_dispatch(spool_id: UUID | str, job_context: object) -> Call[OcrResponse]:
    """Phase 2 of OCR: disclose the spooled document under a dispatch context."""
    token = require_job_context(job_context)
    return Call(
        routes.EXECUTE_OCR_DISPATCH,
        AuthKind.SERVICE,
        model_parser(OcrResponse),
        params={"spool_id": uuid_param(spool_id, "spool_id")},
        job_context=token,
    )


def embed(request: EmbedRequest, job_context: object) -> Call[EmbedResponse]:
    """``POST /v1/execute/embed``."""
    token = require_job_context(job_context)
    return Call(
        routes.EXECUTE_EMBED,
        AuthKind.SERVICE,
        model_parser(EmbedResponse),
        json=_json(request),
        job_context=token,
    )


def rerank(request: RerankRequest, job_context: object) -> Call[RerankResponse]:
    """``POST /v1/execute/rerank``."""
    token = require_job_context(job_context)
    return Call(
        routes.EXECUTE_RERANK,
        AuthKind.SERVICE,
        model_parser(RerankResponse),
        json=_json(request),
        job_context=token,
    )


def structured_output(
    request: StructuredOutputRequest, job_context: object
) -> Call[StructuredOutputResponse]:
    """``POST /v1/execute/structured-output``."""
    token = require_job_context(job_context)
    return Call(
        routes.EXECUTE_STRUCTURED_OUTPUT,
        AuthKind.SERVICE,
        model_parser(StructuredOutputResponse),
        json=_json(request),
        job_context=token,
    )


# --- providers, models, profiles (superuser) ---------------------------------


def list_providers() -> Call[tuple[ProviderAdmin, ...]]:
    """List providers."""
    return Call(routes.PROVIDERS_LIST, AuthKind.JWT, list_parser(ProviderAdmin))


def create_provider(body: ProviderCreate) -> Call[ProviderAdmin]:
    """Create a provider."""
    return Call(
        routes.PROVIDERS_CREATE,
        AuthKind.JWT,
        model_parser(ProviderAdmin),
        json=dump_body(body),
    )


def get_provider(provider_id: UUID | str) -> Call[ProviderAdmin]:
    """Read one provider."""
    return Call(
        routes.PROVIDER_GET,
        AuthKind.JWT,
        model_parser(ProviderAdmin),
        params={"provider_id": uuid_param(provider_id, "provider_id")},
    )


def update_provider(
    provider_id: UUID | str, body: ProviderUpdate
) -> Call[ProviderAdmin]:
    """Change a provider."""
    return Call(
        routes.PROVIDER_UPDATE,
        AuthKind.JWT,
        model_parser(ProviderAdmin),
        params={"provider_id": uuid_param(provider_id, "provider_id")},
        json=dump_body(body),
    )


def list_models() -> Call[tuple[ModelAdmin, ...]]:
    """List models."""
    return Call(routes.MODELS_LIST, AuthKind.JWT, list_parser(ModelAdmin))


def create_model(body: ModelCreate) -> Call[ModelAdmin]:
    """Create a model."""
    return Call(
        routes.MODELS_CREATE,
        AuthKind.JWT,
        model_parser(ModelAdmin),
        json=dump_body(body),
    )


def get_model(model_id: UUID | str) -> Call[ModelAdmin]:
    """Read one model."""
    return Call(
        routes.MODEL_GET,
        AuthKind.JWT,
        model_parser(ModelAdmin),
        params={"model_id": uuid_param(model_id, "model_id")},
    )


def update_model(model_id: UUID | str, body: ModelUpdate) -> Call[ModelAdmin]:
    """Change a model."""
    return Call(
        routes.MODEL_UPDATE,
        AuthKind.JWT,
        model_parser(ModelAdmin),
        params={"model_id": uuid_param(model_id, "model_id")},
        json=dump_body(body),
    )


def admin_list_profiles() -> Call[tuple[ProfileAdmin, ...]]:
    """List every profile, published or not."""
    return Call(routes.ADMIN_PROFILES_LIST, AuthKind.JWT, list_parser(ProfileAdmin))


def admin_create_profile(body: ProfileCreate) -> Call[ProfileAdmin]:
    """Create a profile and its first revision."""
    return Call(
        routes.ADMIN_PROFILES_CREATE,
        AuthKind.JWT,
        model_parser(ProfileAdmin),
        json=dump_body(body),
    )


def admin_get_profile(profile_key: str) -> Call[ProfileAdmin]:
    """Read one profile with its current revision."""
    return Call(
        routes.ADMIN_PROFILE_GET,
        AuthKind.JWT,
        model_parser(ProfileAdmin),
        params={"profile_key": profile_key_param(profile_key)},
    )


def admin_update_profile(profile_key: str, body: ProfileUpdate) -> Call[ProfileAdmin]:
    """Change a profile; a new configuration is a new revision."""
    return Call(
        routes.ADMIN_PROFILE_UPDATE,
        AuthKind.JWT,
        model_parser(ProfileAdmin),
        params={"profile_key": profile_key_param(profile_key)},
        json=dump_body(body),
    )


def admin_profile_revisions(profile_key: str) -> Call[tuple[ProfileRevisionAdmin, ...]]:
    """Every revision of a profile, oldest first."""
    return Call(
        routes.ADMIN_PROFILE_REVISIONS,
        AuthKind.JWT,
        list_parser(ProfileRevisionAdmin),
        params={"profile_key": profile_key_param(profile_key)},
    )


# --- the superuser's user-scope stop (A-2) -----------------------------------


def admin_list_user_credentials(
    owner_user_id: UUID | str,
) -> Call[tuple[CredentialPublic, ...]]:
    """One user's credentials, metadata only."""
    return Call(
        routes.USER_CREDENTIALS_ADMIN_LIST,
        AuthKind.JWT,
        list_parser(CredentialPublic),
        query={"owner_user_id": uuid_param(owner_user_id, "owner_user_id")},
    )


def admin_disable_user_credential(credential_id: UUID | str) -> Call[CredentialPublic]:
    """Disable a user's credential (incident response, offboarding)."""
    return Call(
        routes.USER_CREDENTIAL_ADMIN_DISABLE,
        AuthKind.JWT,
        model_parser(CredentialPublic),
        params={"credential_id": uuid_param(credential_id, "credential_id")},
    )


def admin_delete_user_credential(credential_id: UUID | str) -> Call[None]:
    """Delete a user's credential (incident response, offboarding)."""
    return Call(
        routes.USER_CREDENTIAL_ADMIN_DELETE,
        AuthKind.JWT,
        no_content,
        params={"credential_id": uuid_param(credential_id, "credential_id")},
    )


# --- credentials and bindings under a scope ----------------------------------


def _scoped(route: routes.Route, scope: str) -> routes.Route:
    return routes.Route(route.method, route.path.replace("{scope}", scope))


def _scope_params(scope_params: dict[str, str], **extra: str) -> dict[str, str]:
    return {**scope_params, **extra}


def list_credentials(
    scope: str, scope_params: dict[str, str]
) -> Call[tuple[CredentialPublic, ...]]:
    """List the scope's credentials."""
    return Call(
        _scoped(routes.CREDENTIALS_LIST, scope),
        AuthKind.JWT,
        list_parser(CredentialPublic),
        params=scope_params,
    )


def create_credential(
    scope: str, scope_params: dict[str, str], body: CredentialCreate
) -> Call[CredentialPublic]:
    """Store a new credential in the scope."""
    return Call(
        _scoped(routes.CREDENTIALS_CREATE, scope),
        AuthKind.JWT,
        model_parser(CredentialPublic),
        params=scope_params,
        json=dump_body(body),
    )


def _credential_call(
    route: routes.Route,
    scope: str,
    scope_params: dict[str, str],
    credential_id: UUID | str,
) -> tuple[routes.Route, dict[str, str]]:
    return _scoped(route, scope), _scope_params(
        scope_params, credential_id=uuid_param(credential_id, "credential_id")
    )


def get_credential(
    scope: str, scope_params: dict[str, str], credential_id: UUID | str
) -> Call[CredentialPublic]:
    """Read one credential."""
    route, params = _credential_call(
        routes.CREDENTIAL_GET, scope, scope_params, credential_id
    )
    return Call(route, AuthKind.JWT, model_parser(CredentialPublic), params=params)


def update_credential(
    scope: str,
    scope_params: dict[str, str],
    credential_id: UUID | str,
    body: CredentialUpdate,
) -> Call[CredentialPublic]:
    """Change a credential's name or incident-listing consent."""
    route, params = _credential_call(
        routes.CREDENTIAL_UPDATE, scope, scope_params, credential_id
    )
    return Call(
        route,
        AuthKind.JWT,
        model_parser(CredentialPublic),
        params=params,
        json=dump_body(body),
    )


def delete_credential(
    scope: str, scope_params: dict[str, str], credential_id: UUID | str
) -> Call[None]:
    """Delete a credential (logical while referenced)."""
    route, params = _credential_call(
        routes.CREDENTIAL_DELETE, scope, scope_params, credential_id
    )
    return Call(route, AuthKind.JWT, no_content, params=params)


def rotate_credential(
    scope: str,
    scope_params: dict[str, str],
    credential_id: UUID | str,
    body: CredentialRotate,
) -> Call[CredentialPublic]:
    """Store a new current version of a credential."""
    route, params = _credential_call(
        routes.CREDENTIAL_ROTATE, scope, scope_params, credential_id
    )
    return Call(
        route,
        AuthKind.JWT,
        model_parser(CredentialPublic),
        params=params,
        json=dump_body(body),
    )


def validate_credential(
    scope: str, scope_params: dict[str, str], credential_id: UUID | str
) -> Call[CredentialValidation]:
    """Probe a credential at its provider."""
    route, params = _credential_call(
        routes.CREDENTIAL_VALIDATE, scope, scope_params, credential_id
    )
    return Call(route, AuthKind.JWT, model_parser(CredentialValidation), params=params)


def _credential_verb(
    route: routes.Route,
    scope: str,
    scope_params: dict[str, str],
    credential_id: UUID | str,
) -> Call[CredentialPublic]:
    route, params = _credential_call(route, scope, scope_params, credential_id)
    return Call(route, AuthKind.JWT, model_parser(CredentialPublic), params=params)


def disable_credential(
    scope: str, scope_params: dict[str, str], credential_id: UUID | str
) -> Call[CredentialPublic]:
    """Disable a credential; its bindings become unavailable."""
    return _credential_verb(
        routes.CREDENTIAL_DISABLE, scope, scope_params, credential_id
    )


def enable_credential(
    scope: str, scope_params: dict[str, str], credential_id: UUID | str
) -> Call[CredentialPublic]:
    """Re-enable a disabled credential."""
    return _credential_verb(
        routes.CREDENTIAL_ENABLE, scope, scope_params, credential_id
    )


def reconfirm_credential(
    scope: str, scope_params: dict[str, str], credential_id: UUID | str
) -> Call[CredentialPublic]:
    """Re-confirm a credential after a restore."""
    return _credential_verb(
        routes.CREDENTIAL_RECONFIRM, scope, scope_params, credential_id
    )


def credential_remote_artifacts(
    scope: str, scope_params: dict[str, str], credential_id: UUID | str
) -> Call[tuple[RemoteArtifactPublic, ...]]:
    """Provider-side files under a credential: ids and status, never content."""
    route, params = _credential_call(
        routes.CREDENTIAL_REMOTE_ARTIFACTS, scope, scope_params, credential_id
    )
    return Call(route, AuthKind.JWT, list_parser(RemoteArtifactPublic), params=params)


def list_bindings(
    scope: str, scope_params: dict[str, str]
) -> Call[tuple[BindingPublic, ...]]:
    """List the scope's bindings."""
    return Call(
        _scoped(routes.BINDINGS_LIST, scope),
        AuthKind.JWT,
        list_parser(BindingPublic),
        params=scope_params,
    )


def create_binding(
    scope: str, scope_params: dict[str, str], body: BindingCreate
) -> Call[BindingPublic]:
    """Bind a profile in the scope."""
    return Call(
        _scoped(routes.BINDINGS_CREATE, scope),
        AuthKind.JWT,
        model_parser(BindingPublic),
        params=scope_params,
        json=dump_body(body),
    )


def _binding_params(
    scope_params: dict[str, str], binding_id: UUID | str
) -> dict[str, str]:
    return _scope_params(scope_params, binding_id=uuid_param(binding_id, "binding_id"))


def get_binding(
    scope: str, scope_params: dict[str, str], binding_id: UUID | str
) -> Call[BindingPublic]:
    """Read one binding."""
    return Call(
        _scoped(routes.BINDING_GET, scope),
        AuthKind.JWT,
        model_parser(BindingPublic),
        params=_binding_params(scope_params, binding_id),
    )


def update_binding(
    scope: str,
    scope_params: dict[str, str],
    binding_id: UUID | str,
    body: BindingUpdate,
) -> Call[BindingPublic]:
    """Change a binding."""
    return Call(
        _scoped(routes.BINDING_UPDATE, scope),
        AuthKind.JWT,
        model_parser(BindingPublic),
        params=_binding_params(scope_params, binding_id),
        json=dump_body(body),
    )


def delete_binding(
    scope: str, scope_params: dict[str, str], binding_id: UUID | str
) -> Call[None]:
    """Remove a binding."""
    return Call(
        _scoped(routes.BINDING_DELETE, scope),
        AuthKind.JWT,
        no_content,
        params=_binding_params(scope_params, binding_id),
    )
