"""
The ``admin`` namespace: every JWT-authenticated management route.

``client.admin`` groups the superuser routes (providers, models, profiles,
the platform's own credentials and bindings, the user-scope stop) with the
per-scope routes a tenant ``ADMIN`` (``client.admin.tenant(tenant_id)``) or a
``WRITER`` (``client.admin.me``) uses for their own credentials and bindings.
The gateway decides who may call which route; this namespace only sends.
"""

from collections.abc import Awaitable
from typing import Protocol, TypeVar
from uuid import UUID

from ai_sdk_m8.client import _ops, routes
from ai_sdk_m8.client._core import Call, uuid_param
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
)

T = TypeVar("T")


class SyncSend(Protocol):
    """Sends one call and returns its parsed answer."""

    def __call__(self, call: Call[T], /) -> T:
        """Send ``call``."""
        ...


class AsyncSend(Protocol):
    """Sends one call and returns an awaitable of its parsed answer."""

    def __call__(self, call: Call[T], /) -> Awaitable[T]:
        """Send ``call``."""
        ...


# --- sync --------------------------------------------------------------------


class Providers:
    """Provider endpoints (superuser)."""

    def __init__(self, send: SyncSend) -> None:
        self._send = send

    def list(self) -> tuple[ProviderAdmin, ...]:
        """Every provider."""
        return self._send(_ops.list_providers())

    def create(self, body: ProviderCreate) -> ProviderAdmin:
        """Create a provider."""
        return self._send(_ops.create_provider(body))

    def get(self, provider_id: UUID | str) -> ProviderAdmin:
        """One provider."""
        return self._send(_ops.get_provider(provider_id))

    def update(self, provider_id: UUID | str, body: ProviderUpdate) -> ProviderAdmin:
        """Change a provider."""
        return self._send(_ops.update_provider(provider_id, body))


class Models:
    """Model rows (superuser)."""

    def __init__(self, send: SyncSend) -> None:
        self._send = send

    def list(self) -> tuple[ModelAdmin, ...]:
        """Every model."""
        return self._send(_ops.list_models())

    def create(self, body: ModelCreate) -> ModelAdmin:
        """Create a model."""
        return self._send(_ops.create_model(body))

    def get(self, model_id: UUID | str) -> ModelAdmin:
        """One model."""
        return self._send(_ops.get_model(model_id))

    def update(self, model_id: UUID | str, body: ModelUpdate) -> ModelAdmin:
        """Change a model."""
        return self._send(_ops.update_model(model_id, body))


class Profiles:
    """Profiles and their revisions (superuser)."""

    def __init__(self, send: SyncSend) -> None:
        self._send = send

    def list(self) -> tuple[ProfileAdmin, ...]:
        """Every profile, published or not."""
        return self._send(_ops.admin_list_profiles())

    def create(self, body: ProfileCreate) -> ProfileAdmin:
        """Create a profile."""
        return self._send(_ops.admin_create_profile(body))

    def get(self, profile_key: str) -> ProfileAdmin:
        """One profile."""
        return self._send(_ops.admin_get_profile(profile_key))

    def update(self, profile_key: str, body: ProfileUpdate) -> ProfileAdmin:
        """Change a profile."""
        return self._send(_ops.admin_update_profile(profile_key, body))

    def revisions(self, profile_key: str) -> tuple[ProfileRevisionAdmin, ...]:
        """Every revision of a profile."""
        return self._send(_ops.admin_profile_revisions(profile_key))


class UserCredentialStop:
    """The superuser's disable/delete of a user's credential (A-2)."""

    def __init__(self, send: SyncSend) -> None:
        self._send = send

    def list(self, owner_user_id: UUID | str) -> tuple[CredentialPublic, ...]:
        """One user's credentials, metadata only."""
        return self._send(_ops.admin_list_user_credentials(owner_user_id))

    def disable(self, credential_id: UUID | str) -> CredentialPublic:
        """Disable it; the owner's bindings become unavailable."""
        return self._send(_ops.admin_disable_user_credential(credential_id))

    def delete(self, credential_id: UUID | str) -> None:
        """Delete it."""
        return self._send(_ops.admin_delete_user_credential(credential_id))


class Credentials:
    """Credentials of one scope."""

    def __init__(self, send: SyncSend, scope: str, params: dict[str, str]) -> None:
        self._send = send
        self._scope = scope
        self._params = params

    def list(self) -> tuple[CredentialPublic, ...]:
        """The scope's credentials."""
        return self._send(_ops.list_credentials(self._scope, self._params))

    def create(self, body: CredentialCreate) -> CredentialPublic:
        """Store a credential."""
        return self._send(_ops.create_credential(self._scope, self._params, body))

    def get(self, credential_id: UUID | str) -> CredentialPublic:
        """One credential."""
        return self._send(_ops.get_credential(self._scope, self._params, credential_id))

    def update(
        self, credential_id: UUID | str, body: CredentialUpdate
    ) -> CredentialPublic:
        """Change its name or incident-listing consent."""
        return self._send(
            _ops.update_credential(self._scope, self._params, credential_id, body)
        )

    def delete(self, credential_id: UUID | str) -> None:
        """Delete it."""
        return self._send(
            _ops.delete_credential(self._scope, self._params, credential_id)
        )

    def rotate(
        self, credential_id: UUID | str, body: CredentialRotate
    ) -> CredentialPublic:
        """Store a new current version."""
        return self._send(
            _ops.rotate_credential(self._scope, self._params, credential_id, body)
        )

    def validate(self, credential_id: UUID | str) -> CredentialValidation:
        """Probe it at its provider."""
        return self._send(
            _ops.validate_credential(self._scope, self._params, credential_id)
        )

    def disable(self, credential_id: UUID | str) -> CredentialPublic:
        """Disable it."""
        return self._send(
            _ops.disable_credential(self._scope, self._params, credential_id)
        )

    def enable(self, credential_id: UUID | str) -> CredentialPublic:
        """Re-enable it."""
        return self._send(
            _ops.enable_credential(self._scope, self._params, credential_id)
        )

    def reconfirm(self, credential_id: UUID | str) -> CredentialPublic:
        """Re-confirm it after a restore."""
        return self._send(
            _ops.reconfirm_credential(self._scope, self._params, credential_id)
        )

    def remote_artifacts(
        self, credential_id: UUID | str
    ) -> tuple[RemoteArtifactPublic, ...]:
        """Provider-side files under it."""
        return self._send(
            _ops.credential_remote_artifacts(self._scope, self._params, credential_id)
        )


class Bindings:
    """Bindings of one scope."""

    def __init__(self, send: SyncSend, scope: str, params: dict[str, str]) -> None:
        self._send = send
        self._scope = scope
        self._params = params

    def list(self) -> tuple[BindingPublic, ...]:
        """The scope's bindings."""
        return self._send(_ops.list_bindings(self._scope, self._params))

    def create(self, body: BindingCreate) -> BindingPublic:
        """Bind a profile."""
        return self._send(_ops.create_binding(self._scope, self._params, body))

    def get(self, binding_id: UUID | str) -> BindingPublic:
        """One binding."""
        return self._send(_ops.get_binding(self._scope, self._params, binding_id))

    def update(self, binding_id: UUID | str, body: BindingUpdate) -> BindingPublic:
        """Change a binding."""
        return self._send(
            _ops.update_binding(self._scope, self._params, binding_id, body)
        )

    def delete(self, binding_id: UUID | str) -> None:
        """Remove a binding."""
        return self._send(_ops.delete_binding(self._scope, self._params, binding_id))


class ScopeNamespace:
    """The credentials and bindings of one tenant or of the caller."""

    def __init__(self, send: SyncSend, scope: str, params: dict[str, str]) -> None:
        self.credentials = Credentials(send, scope, params)
        self.bindings = Bindings(send, scope, params)


class Admin:
    """Every management route; authenticate the client with a ``BearerJwt``."""

    def __init__(self, send: SyncSend) -> None:
        self._send = send
        self.providers = Providers(send)
        self.models = Models(send)
        self.profiles = Profiles(send)
        self.credentials = Credentials(send, routes.GLOBAL_SCOPE, {})
        self.bindings = Bindings(send, routes.GLOBAL_SCOPE, {})
        self.user_credentials = UserCredentialStop(send)
        self.me = ScopeNamespace(send, routes.USER_SCOPE, {})

    def tenant(self, tenant_id: UUID | str) -> ScopeNamespace:
        """One tenant's credentials and bindings."""
        return ScopeNamespace(
            self._send,
            routes.TENANT_SCOPE,
            {"tenant_id": uuid_param(tenant_id, "tenant_id")},
        )


# --- async -------------------------------------------------------------------


class AsyncProviders:
    """Provider endpoints (superuser)."""

    def __init__(self, send: AsyncSend) -> None:
        self._send = send

    async def list(self) -> tuple[ProviderAdmin, ...]:
        """Every provider."""
        return await self._send(_ops.list_providers())

    async def create(self, body: ProviderCreate) -> ProviderAdmin:
        """Create a provider."""
        return await self._send(_ops.create_provider(body))

    async def get(self, provider_id: UUID | str) -> ProviderAdmin:
        """One provider."""
        return await self._send(_ops.get_provider(provider_id))

    async def update(
        self, provider_id: UUID | str, body: ProviderUpdate
    ) -> ProviderAdmin:
        """Change a provider."""
        return await self._send(_ops.update_provider(provider_id, body))


class AsyncModels:
    """Model rows (superuser)."""

    def __init__(self, send: AsyncSend) -> None:
        self._send = send

    async def list(self) -> tuple[ModelAdmin, ...]:
        """Every model."""
        return await self._send(_ops.list_models())

    async def create(self, body: ModelCreate) -> ModelAdmin:
        """Create a model."""
        return await self._send(_ops.create_model(body))

    async def get(self, model_id: UUID | str) -> ModelAdmin:
        """One model."""
        return await self._send(_ops.get_model(model_id))

    async def update(self, model_id: UUID | str, body: ModelUpdate) -> ModelAdmin:
        """Change a model."""
        return await self._send(_ops.update_model(model_id, body))


class AsyncProfiles:
    """Profiles and their revisions (superuser)."""

    def __init__(self, send: AsyncSend) -> None:
        self._send = send

    async def list(self) -> tuple[ProfileAdmin, ...]:
        """Every profile, published or not."""
        return await self._send(_ops.admin_list_profiles())

    async def create(self, body: ProfileCreate) -> ProfileAdmin:
        """Create a profile."""
        return await self._send(_ops.admin_create_profile(body))

    async def get(self, profile_key: str) -> ProfileAdmin:
        """One profile."""
        return await self._send(_ops.admin_get_profile(profile_key))

    async def update(self, profile_key: str, body: ProfileUpdate) -> ProfileAdmin:
        """Change a profile."""
        return await self._send(_ops.admin_update_profile(profile_key, body))

    async def revisions(self, profile_key: str) -> tuple[ProfileRevisionAdmin, ...]:
        """Every revision of a profile."""
        return await self._send(_ops.admin_profile_revisions(profile_key))


class AsyncUserCredentialStop:
    """The superuser's disable/delete of a user's credential (A-2)."""

    def __init__(self, send: AsyncSend) -> None:
        self._send = send

    async def list(self, owner_user_id: UUID | str) -> tuple[CredentialPublic, ...]:
        """One user's credentials, metadata only."""
        return await self._send(_ops.admin_list_user_credentials(owner_user_id))

    async def disable(self, credential_id: UUID | str) -> CredentialPublic:
        """Disable it; the owner's bindings become unavailable."""
        return await self._send(_ops.admin_disable_user_credential(credential_id))

    async def delete(self, credential_id: UUID | str) -> None:
        """Delete it."""
        return await self._send(_ops.admin_delete_user_credential(credential_id))


class AsyncCredentials:
    """Credentials of one scope."""

    def __init__(self, send: AsyncSend, scope: str, params: dict[str, str]) -> None:
        self._send = send
        self._scope = scope
        self._params = params

    async def list(self) -> tuple[CredentialPublic, ...]:
        """The scope's credentials."""
        return await self._send(_ops.list_credentials(self._scope, self._params))

    async def create(self, body: CredentialCreate) -> CredentialPublic:
        """Store a credential."""
        return await self._send(_ops.create_credential(self._scope, self._params, body))

    async def get(self, credential_id: UUID | str) -> CredentialPublic:
        """One credential."""
        return await self._send(
            _ops.get_credential(self._scope, self._params, credential_id)
        )

    async def update(
        self, credential_id: UUID | str, body: CredentialUpdate
    ) -> CredentialPublic:
        """Change its name or incident-listing consent."""
        return await self._send(
            _ops.update_credential(self._scope, self._params, credential_id, body)
        )

    async def delete(self, credential_id: UUID | str) -> None:
        """Delete it."""
        return await self._send(
            _ops.delete_credential(self._scope, self._params, credential_id)
        )

    async def rotate(
        self, credential_id: UUID | str, body: CredentialRotate
    ) -> CredentialPublic:
        """Store a new current version."""
        return await self._send(
            _ops.rotate_credential(self._scope, self._params, credential_id, body)
        )

    async def validate(self, credential_id: UUID | str) -> CredentialValidation:
        """Probe it at its provider."""
        return await self._send(
            _ops.validate_credential(self._scope, self._params, credential_id)
        )

    async def disable(self, credential_id: UUID | str) -> CredentialPublic:
        """Disable it."""
        return await self._send(
            _ops.disable_credential(self._scope, self._params, credential_id)
        )

    async def enable(self, credential_id: UUID | str) -> CredentialPublic:
        """Re-enable it."""
        return await self._send(
            _ops.enable_credential(self._scope, self._params, credential_id)
        )

    async def reconfirm(self, credential_id: UUID | str) -> CredentialPublic:
        """Re-confirm it after a restore."""
        return await self._send(
            _ops.reconfirm_credential(self._scope, self._params, credential_id)
        )

    async def remote_artifacts(
        self, credential_id: UUID | str
    ) -> tuple[RemoteArtifactPublic, ...]:
        """Provider-side files under it."""
        return await self._send(
            _ops.credential_remote_artifacts(self._scope, self._params, credential_id)
        )


class AsyncBindings:
    """Bindings of one scope."""

    def __init__(self, send: AsyncSend, scope: str, params: dict[str, str]) -> None:
        self._send = send
        self._scope = scope
        self._params = params

    async def list(self) -> tuple[BindingPublic, ...]:
        """The scope's bindings."""
        return await self._send(_ops.list_bindings(self._scope, self._params))

    async def create(self, body: BindingCreate) -> BindingPublic:
        """Bind a profile."""
        return await self._send(_ops.create_binding(self._scope, self._params, body))

    async def get(self, binding_id: UUID | str) -> BindingPublic:
        """One binding."""
        return await self._send(_ops.get_binding(self._scope, self._params, binding_id))

    async def update(
        self, binding_id: UUID | str, body: BindingUpdate
    ) -> BindingPublic:
        """Change a binding."""
        return await self._send(
            _ops.update_binding(self._scope, self._params, binding_id, body)
        )

    async def delete(self, binding_id: UUID | str) -> None:
        """Remove a binding."""
        return await self._send(
            _ops.delete_binding(self._scope, self._params, binding_id)
        )


class AsyncScopeNamespace:
    """The credentials and bindings of one tenant or of the caller."""

    def __init__(self, send: AsyncSend, scope: str, params: dict[str, str]) -> None:
        self.credentials = AsyncCredentials(send, scope, params)
        self.bindings = AsyncBindings(send, scope, params)


class AsyncAdmin:
    """Every management route; authenticate the client with a ``BearerJwt``."""

    def __init__(self, send: AsyncSend) -> None:
        self._send = send
        self.providers = AsyncProviders(send)
        self.models = AsyncModels(send)
        self.profiles = AsyncProfiles(send)
        self.credentials = AsyncCredentials(send, routes.GLOBAL_SCOPE, {})
        self.bindings = AsyncBindings(send, routes.GLOBAL_SCOPE, {})
        self.user_credentials = AsyncUserCredentialStop(send)
        self.me = AsyncScopeNamespace(send, routes.USER_SCOPE, {})

    def tenant(self, tenant_id: UUID | str) -> AsyncScopeNamespace:
        """One tenant's credentials and bindings."""
        return AsyncScopeNamespace(
            self._send,
            routes.TENANT_SCOPE,
            {"tenant_id": uuid_param(tenant_id, "tenant_id")},
        )
