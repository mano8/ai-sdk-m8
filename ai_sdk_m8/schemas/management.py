"""
Management wire models of the gateway (D-05, D-20, C-04, C-07).

These are the bodies of the JWT-authenticated management routes: providers,
models and profiles (superuser), credentials and bindings (per scope). Write
bodies never carry an owner, a tenant or a scope: those come from the token
and the route, so a body naming one is refused as an unknown field. Secrets
travel only in write bodies, as ``SecretStr``, and no response carries one.

Update bodies use *presence* semantics: a field left out is unchanged, a
nullable field sent as ``null`` is cleared, and a non-nullable field sent as
``null`` is refused.
"""

import json
from enum import StrEnum
from typing import Annotated, Final, Self

from pydantic import (
    UUID4,
    AfterValidator,
    AwareDatetime,
    Field,
    JsonValue,
    SecretStr,
    StrictBool,
    StrictStr,
    StringConstraints,
    model_validator,
)

from ai_sdk_m8.schemas._base import (
    AiModel,
    NonNegativeInt,
    PositiveInt,
    ProfileKey,
    Revision,
    SafeStr,
)
from ai_sdk_m8.schemas.enums import (
    V1_CAPABILITIES,
    Capability,
    IdentityAssurance,
    ProviderBoundary,
)
from ai_sdk_m8.schemas.errors import ProviderMetadata
from ai_sdk_m8.signed._encoding import canonicalize
from ai_sdk_m8.signed._errors import MalformedSignedObjectError


class ProviderType(StrEnum):
    """Adapter family a provider row is served by."""

    MISTRAL = "mistral"
    OLLAMA = "ollama"
    OPENAI_COMPATIBLE = "openai_compatible"


class AuthType(StrEnum):
    """How a provider's credential is presented (D-20)."""

    NONE = "none"
    API_KEY_HEADER = "api_key_header"
    BEARER = "bearer"


class ScopeType(StrEnum):
    """Whose credential or binding a row is (R-08, C-04)."""

    GLOBAL = "global"
    TENANT = "tenant"
    USER = "user"


class CredentialStatus(StrEnum):
    """Lifecycle of a credential; only ``active`` is execution-eligible."""

    PROVISIONING = "provisioning"
    ACTIVE = "active"
    DISABLED = "disabled"
    INVALID = "invalid"
    DELETED = "deleted"
    REPROVISION_REQUIRED = "reprovision_required"
    RECONFIRM_REQUIRED = "reconfirm_required"


class OnUnavailable(StrEnum):
    """What an explicit binding does when its credential is unavailable (C-04)."""

    FAIL = "fail"
    FALL_THROUGH = "fall_through"


class BindingStatus(StrEnum):
    """Whether a binding's credential can currently serve it (T20a)."""

    ACTIVE = "active"
    CREDENTIAL_UNAVAILABLE = "credential_unavailable"


class RemoteArtifactStatus(StrEnum):
    """Stored status of a provider-side temporary file (D-43)."""

    UPLOADING = "uploading"
    UPLOADING_UNKNOWN_ID = "uploading_unknown_id"
    ACTIVE = "active"
    PENDING_DELETE = "pending_delete"
    MANUAL_CLEANUP_REQUIRED = "manual_cleanup_required"


class ValidationOutcome(StrEnum):
    """Result of a credential validation probe (T25)."""

    VALID = "valid"
    AUTH_FAILED = "auth_failed"
    INCONCLUSIVE = "inconclusive"


#: Header-name prefixes a provider credential may never be sent under (D-20).
RESERVED_HEADER_PREFIXES: Final = ("x-forwarded-", "x-internal-", "x-ai-")

#: Longest provider ``base_url``.
BASE_URL_MAX_LENGTH: Final = 2048

#: Largest JCS size of a profile's ``execution_config``, in bytes.
EXECUTION_CONFIG_MAX_BYTES: Final = 4096

#: Longest secret a write body accepts, in characters.
SECRET_MAX_LENGTH: Final = 8192


def _auth_header_name(value: str) -> str:
    if value.startswith(RESERVED_HEADER_PREFIXES):
        raise ValueError("auth_header_name uses a reserved prefix")
    return value


def _base_url(value: str) -> str:
    if not value.startswith(("http://", "https://")):
        raise ValueError("base_url must be an http or https URL")
    return value


def _unique_v1_capabilities(
    value: tuple[Capability, ...],
) -> tuple[Capability, ...]:
    if len(set(value)) != len(value):
        raise ValueError("capabilities must not repeat")
    if not set(value) <= V1_CAPABILITIES:
        raise ValueError("a reserved capability has no V1 route")
    return value


def _execution_config(value: dict[str, JsonValue]) -> dict[str, JsonValue]:
    try:
        encoded = canonicalize(value)
    except MalformedSignedObjectError as exc:
        raise ValueError(
            "execution_config must be integer-only JSON, at most 4 levels deep"
        ) from exc
    if len(encoded) > EXECUTION_CONFIG_MAX_BYTES:
        raise ValueError(f"execution_config exceeds {EXECUTION_CONFIG_MAX_BYTES} bytes")
    return value


def _bounded_secret(value: SecretStr) -> SecretStr:
    if not 1 <= len(value.get_secret_value()) <= SECRET_MAX_LENGTH:
        raise ValueError(f"secret must be 1-{SECRET_MAX_LENGTH} characters")
    return value


#: A display name: 1-64 printable characters, no surrounding whitespace.
Name = Annotated[
    SafeStr,
    StringConstraints(
        pattern=r"^[^\s\x00-\x1f\x7f](?:[^\x00-\x1f\x7f]{0,62}[^\s\x00-\x1f\x7f])?$"
    ),
]

#: A credential header name: ``x-…`` lower-case or ``api-key`` (D-20).
AuthHeaderName = Annotated[
    StrictStr,
    StringConstraints(pattern=r"^(?:x-[a-z0-9-]{1,60}|api-key)$"),
    AfterValidator(_auth_header_name),
]

#: A provider endpoint; the gateway runs the full destination check (T19).
BaseUrl = Annotated[
    StrictStr,
    StringConstraints(max_length=BASE_URL_MAX_LENGTH),
    AfterValidator(_base_url),
]

#: A provider-side model id; URL-encoded by the gateway at use.
ExternalModelId = Annotated[
    StrictStr, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,255}$")
]

#: An operator label such as a model version or a pinned snapshot.
Label = Annotated[
    StrictStr, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}$")
]

#: A non-empty, unique set of V1 capabilities.
Capabilities = Annotated[
    tuple[Capability, ...],
    Field(min_length=1),
    AfterValidator(_unique_v1_capabilities),
]

#: Execution-affecting profile configuration, integer-only and bounded.
ExecutionConfig = Annotated[dict[str, JsonValue], AfterValidator(_execution_config)]

#: A provider credential in a write body.
Secret = Annotated[SecretStr, AfterValidator(_bounded_secret)]


def _refuse_null(model: AiModel, fields: tuple[str, ...]) -> None:
    for name in set(fields) & model.model_fields_set:
        if getattr(model, name) is None:
            raise ValueError(f"{name} cannot be null")


def _refuse_assurance_digest(value: IdentityAssurance | None) -> None:
    if value is IdentityAssurance.PROVIDER_DIGEST:
        raise ValueError(
            "provider_digest is recorded by the adapter, never declared by hand"
        )


# --- providers ---------------------------------------------------------------


class ProviderCreate(AiModel):
    """A new provider endpoint (superuser)."""

    name: Name
    provider_type: ProviderType
    base_url: BaseUrl
    auth_type: AuthType
    auth_header_name: AuthHeaderName | None = None
    boundary: ProviderBoundary
    enabled: StrictBool = True

    @model_validator(mode="after")
    def _header_matches_auth(self) -> Self:
        if (self.auth_type is AuthType.API_KEY_HEADER) != (
            self.auth_header_name is not None
        ):
            raise ValueError(
                "auth_header_name is required for api_key_header and "
                "forbidden otherwise"
            )
        return self


class ProviderUpdate(AiModel):
    """
    A provider change (superuser).

    ``base_url``, ``provider_type``, ``auth_type`` and ``auth_header_name``
    are frozen once the provider was first used, and ``boundary`` is frozen
    from creation: the gateway answers 409, and the operator creates a new
    row instead. ``enabled = false`` is the emergency stop.
    """

    name: Name | None = None
    provider_type: ProviderType | None = None
    base_url: BaseUrl | None = None
    auth_type: AuthType | None = None
    auth_header_name: AuthHeaderName | None = None
    boundary: ProviderBoundary | None = None
    enabled: StrictBool | None = None

    @model_validator(mode="after")
    def _no_null(self) -> Self:
        _refuse_null(
            self,
            ("name", "provider_type", "base_url", "auth_type", "boundary", "enabled"),
        )
        return self


class ProviderAdmin(AiModel):
    """A provider as the superuser sees it; never shown to readers."""

    id: UUID4
    name: Name
    provider_type: ProviderType
    base_url: BaseUrl
    auth_type: AuthType
    auth_header_name: AuthHeaderName | None = None
    boundary: ProviderBoundary
    enabled: StrictBool
    first_used_at: AwareDatetime | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime


# --- models ------------------------------------------------------------------


class ModelCreate(AiModel):
    """
    A new model row under a provider (superuser).

    ``dimensions`` is required exactly when ``embedding`` is a capability.
    ``identity_assurance`` is ``pinned_snapshot`` for a dated, immutable
    provider model id and ``operator_declared`` otherwise; ``provider_digest``
    is recorded only by an adapter that reads an immutable digest.
    """

    provider_id: UUID4
    external_model_id: ExternalModelId
    capabilities: Capabilities
    context_window: PositiveInt | None = None
    max_output_tokens: PositiveInt | None = None
    dimensions: PositiveInt | None = None
    model_version_label: Label
    model_revision: Label | None = None
    identity_assurance: IdentityAssurance = IdentityAssurance.OPERATOR_DECLARED
    metadata: ProviderMetadata = {}
    enabled: StrictBool = True

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if (Capability.EMBEDDING in self.capabilities) != (self.dimensions is not None):
            raise ValueError(
                "dimensions is required for embedding models and forbidden otherwise"
            )
        _refuse_assurance_digest(self.identity_assurance)
        return self


class ModelUpdate(AiModel):
    """
    A model change (superuser).

    Once any reservation used the model, ``external_model_id``,
    ``dimensions``, ``model_revision`` and ``model_version_label`` are frozen
    and ``capabilities`` may only shrink (409 otherwise).
    """

    external_model_id: ExternalModelId | None = None
    capabilities: Capabilities | None = None
    context_window: PositiveInt | None = None
    max_output_tokens: PositiveInt | None = None
    dimensions: PositiveInt | None = None
    model_version_label: Label | None = None
    model_revision: Label | None = None
    identity_assurance: IdentityAssurance | None = None
    metadata: ProviderMetadata | None = None
    enabled: StrictBool | None = None

    @model_validator(mode="after")
    def _no_null(self) -> Self:
        _refuse_null(
            self,
            (
                "external_model_id",
                "capabilities",
                "model_version_label",
                "identity_assurance",
                "metadata",
                "enabled",
            ),
        )
        _refuse_assurance_digest(self.identity_assurance)
        return self


class ModelAdmin(AiModel):
    """
    A model as the superuser sees it.

    ``execution_identity`` is the C-07 identity
    ``h(provider_id, external_model_id, model_revision)``.
    """

    id: UUID4
    provider_id: UUID4
    external_model_id: ExternalModelId
    capabilities: Capabilities
    context_window: PositiveInt | None = None
    max_output_tokens: PositiveInt | None = None
    dimensions: PositiveInt | None = None
    model_version_label: Label
    model_revision: Label | None = None
    identity_assurance: IdentityAssurance
    metadata: ProviderMetadata
    enabled: StrictBool
    flagged_at: AwareDatetime | None = None
    first_used_at: AwareDatetime | None = None
    execution_identity: Revision
    created_at: AwareDatetime
    updated_at: AwareDatetime


# --- profiles ----------------------------------------------------------------


class ProfileCreate(AiModel):
    """A new profile with its first revision (superuser)."""

    profile_key: ProfileKey
    capability: Capability
    execution_config: ExecutionConfig = {}
    enabled: StrictBool = True

    @model_validator(mode="after")
    def _v1(self) -> Self:
        if self.capability not in V1_CAPABILITIES:
            raise ValueError(f"capability {self.capability.value!r} has no V1 route")
        return self


class ProfileUpdate(AiModel):
    """
    A profile change (superuser).

    A changed ``execution_config`` inserts a new immutable revision and
    moves the profile's ``current_revision`` to it.
    """

    execution_config: ExecutionConfig | None = None
    enabled: StrictBool | None = None

    @model_validator(mode="after")
    def _no_null(self) -> Self:
        _refuse_null(self, ("execution_config", "enabled"))
        return self


class ProfileRevisionAdmin(AiModel):
    """One immutable profile revision."""

    revision: PositiveInt
    execution_config: ExecutionConfig
    execution_config_hash: Annotated[
        StrictStr, StringConstraints(pattern=r"^[0-9a-f]{64}$")
    ]
    created_at: AwareDatetime


class ProfileAdmin(AiModel):
    """A profile and its current revision, as the superuser sees it."""

    id: UUID4
    profile_key: ProfileKey
    capability: Capability
    enabled: StrictBool
    current: ProfileRevisionAdmin
    created_at: AwareDatetime
    updated_at: AwareDatetime


# --- credentials -------------------------------------------------------------


class CredentialCreate(AiModel):
    """A new credential in the route's scope; owner and tenant are never sent."""

    provider_id: UUID4
    name: Name
    secret: Secret


class CredentialRotate(AiModel):
    """A replacement secret; it becomes a new, current version."""

    secret: Secret


class CredentialUpdate(AiModel):
    """A credential's mutable metadata (owner only)."""

    name: Name | None = None
    incident_listing_consent: StrictBool | None = None

    @model_validator(mode="after")
    def _no_null(self) -> Self:
        _refuse_null(self, ("name", "incident_listing_consent"))
        return self


class CredentialPublic(AiModel):
    """
    A credential as its owner sees it; never the secret or its fingerprint.

    ``secret_hint`` (the last four characters) is shown only for secrets of
    at least 24 characters.
    """

    id: UUID4
    scope_type: ScopeType
    tenant_id: UUID4 | None = None
    owner_user_id: UUID4 | None = None
    provider_id: UUID4
    name: Name
    status: CredentialStatus
    current_version: PositiveInt | None = None
    secret_hint: (
        Annotated[StrictStr, StringConstraints(min_length=4, max_length=4)] | None
    ) = None
    auth_failure_count: NonNegativeInt
    incident_listing_consent: StrictBool
    throttled_until: AwareDatetime | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class CredentialValidation(AiModel):
    """The outcome of ``:validate`` and the credential afterwards (T25)."""

    outcome: ValidationOutcome
    credential: CredentialPublic


class RemoteArtifactPublic(AiModel):
    """A provider-side temporary file under a credential: ids, never content."""

    id: UUID4
    credential_version: PositiveInt
    status: RemoteArtifactStatus
    remote_artifact_id: Annotated[SafeStr, StringConstraints(max_length=256)] | None = (
        None
    )
    provider_expires_at: AwareDatetime | None = None
    created_at: AwareDatetime


# --- bindings ----------------------------------------------------------------


class BindingCreate(AiModel):
    """
    A binding of a profile, in the route's scope, to a model and credential.

    The credential must belong to the same scope and to the model's provider;
    it may be omitted only for a provider with ``auth_type = none``.
    """

    profile_key: ProfileKey
    model_id: UUID4
    credential_id: UUID4 | None = None
    on_unavailable: OnUnavailable = OnUnavailable.FAIL


class BindingUpdate(AiModel):
    """A binding change; ``credential_id`` may be cleared with ``null``."""

    model_id: UUID4 | None = None
    credential_id: UUID4 | None = None
    on_unavailable: OnUnavailable | None = None

    @model_validator(mode="after")
    def _no_null(self) -> Self:
        _refuse_null(self, ("model_id", "on_unavailable"))
        return self


class BindingPublic(AiModel):
    """A binding as its owner sees it."""

    id: UUID4
    profile_key: ProfileKey
    scope_type: ScopeType
    tenant_id: UUID4 | None = None
    owner_user_id: UUID4 | None = None
    model_id: UUID4
    credential_id: UUID4 | None = None
    on_unavailable: OnUnavailable
    status: BindingStatus
    created_at: AwareDatetime
    updated_at: AwareDatetime


def dump_body(body: AiModel) -> dict[str, object]:
    """
    JSON body of a write model, for the wire.

    Only the fields that were set are sent (presence semantics for updates),
    and a ``SecretStr`` field is revealed here and nowhere else.
    """
    loaded: dict[str, object] = json.loads(body.model_dump_json(exclude_unset=True))
    for name in body.model_fields_set:
        value = getattr(body, name)
        if isinstance(value, SecretStr):
            loaded[name] = value.get_secret_value()
    return loaded


__all__ = [
    "BASE_URL_MAX_LENGTH",
    "EXECUTION_CONFIG_MAX_BYTES",
    "RESERVED_HEADER_PREFIXES",
    "SECRET_MAX_LENGTH",
    "AuthHeaderName",
    "AuthType",
    "BindingCreate",
    "BindingPublic",
    "BindingStatus",
    "BindingUpdate",
    "CredentialCreate",
    "CredentialPublic",
    "CredentialRotate",
    "CredentialStatus",
    "CredentialUpdate",
    "CredentialValidation",
    "ExecutionConfig",
    "ModelAdmin",
    "ModelCreate",
    "ModelUpdate",
    "OnUnavailable",
    "ProfileAdmin",
    "ProfileCreate",
    "ProfileRevisionAdmin",
    "ProfileUpdate",
    "ProviderAdmin",
    "ProviderCreate",
    "ProviderType",
    "ProviderUpdate",
    "RemoteArtifactPublic",
    "RemoteArtifactStatus",
    "ScopeType",
    "ValidationOutcome",
    "dump_body",
]
