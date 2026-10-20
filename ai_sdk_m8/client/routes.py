"""
The gateway's route table, relative to its ``API_PREFIX``.

The client builds every URL from these templates, and the gateway's own test
suite checks that it serves each one with the listed method, so the two
sides cannot drift. Path parameters are UUIDs or profile keys, both of which
are URL-safe once validated.
"""

from typing import Final, NamedTuple


class Route(NamedTuple):
    """One method and path template."""

    method: str
    path: str


META: Final = Route("GET", "meta")

PROFILES: Final = Route("GET", "v1/profiles")
PROFILE: Final = Route("GET", "v1/profiles/{profile_key}")

EXECUTE_OCR: Final = Route("POST", "v1/execute/ocr")
EXECUTE_OCR_DISPATCH: Final = Route("POST", "v1/execute/ocr/{spool_id}:dispatch")
EXECUTE_EMBED: Final = Route("POST", "v1/execute/embed")
EXECUTE_RERANK: Final = Route("POST", "v1/execute/rerank")
EXECUTE_STRUCTURED_OUTPUT: Final = Route("POST", "v1/execute/structured-output")

# Superuser: providers, models, profiles.
PROVIDERS_LIST: Final = Route("GET", "v1/admin/providers")
PROVIDERS_CREATE: Final = Route("POST", "v1/admin/providers")
PROVIDER_GET: Final = Route("GET", "v1/admin/providers/{provider_id}")
PROVIDER_UPDATE: Final = Route("PATCH", "v1/admin/providers/{provider_id}")
MODELS_LIST: Final = Route("GET", "v1/admin/models")
MODELS_CREATE: Final = Route("POST", "v1/admin/models")
MODEL_GET: Final = Route("GET", "v1/admin/models/{model_id}")
MODEL_UPDATE: Final = Route("PATCH", "v1/admin/models/{model_id}")
ADMIN_PROFILES_LIST: Final = Route("GET", "v1/admin/profiles")
ADMIN_PROFILES_CREATE: Final = Route("POST", "v1/admin/profiles")
ADMIN_PROFILE_GET: Final = Route("GET", "v1/admin/profiles/{profile_key}")
ADMIN_PROFILE_UPDATE: Final = Route("PATCH", "v1/admin/profiles/{profile_key}")
ADMIN_PROFILE_REVISIONS: Final = Route(
    "GET", "v1/admin/profiles/{profile_key}/revisions"
)

# Superuser: the user-scope stop (disable or delete only, A-2).
USER_CREDENTIALS_ADMIN_LIST: Final = Route("GET", "v1/admin/user-credentials")
USER_CREDENTIAL_ADMIN_DISABLE: Final = Route(
    "POST", "v1/admin/user-credentials/{credential_id}:disable"
)
USER_CREDENTIAL_ADMIN_DELETE: Final = Route(
    "DELETE", "v1/admin/user-credentials/{credential_id}"
)

#: Base of each scope's credential and binding routes.
GLOBAL_SCOPE: Final = "v1/admin"
TENANT_SCOPE: Final = "v1/tenants/{tenant_id}"
USER_SCOPE: Final = "v1/me"

# Credential routes under a scope base.
CREDENTIALS_LIST: Final = Route("GET", "{scope}/credentials")
CREDENTIALS_CREATE: Final = Route("POST", "{scope}/credentials")
CREDENTIAL_GET: Final = Route("GET", "{scope}/credentials/{credential_id}")
CREDENTIAL_UPDATE: Final = Route("PATCH", "{scope}/credentials/{credential_id}")
CREDENTIAL_DELETE: Final = Route("DELETE", "{scope}/credentials/{credential_id}")
CREDENTIAL_ROTATE: Final = Route("POST", "{scope}/credentials/{credential_id}:rotate")
CREDENTIAL_VALIDATE: Final = Route(
    "POST", "{scope}/credentials/{credential_id}:validate"
)
CREDENTIAL_DISABLE: Final = Route("POST", "{scope}/credentials/{credential_id}:disable")
CREDENTIAL_ENABLE: Final = Route("POST", "{scope}/credentials/{credential_id}:enable")
CREDENTIAL_RECONFIRM: Final = Route(
    "POST", "{scope}/credentials/{credential_id}:reconfirm"
)
CREDENTIAL_REMOTE_ARTIFACTS: Final = Route(
    "GET", "{scope}/credentials/{credential_id}/remote-artifacts"
)

# Binding routes under a scope base.
BINDINGS_LIST: Final = Route("GET", "{scope}/bindings")
BINDINGS_CREATE: Final = Route("POST", "{scope}/bindings")
BINDING_GET: Final = Route("GET", "{scope}/bindings/{binding_id}")
BINDING_UPDATE: Final = Route("PATCH", "{scope}/bindings/{binding_id}")
BINDING_DELETE: Final = Route("DELETE", "{scope}/bindings/{binding_id}")

#: Scoped templates, expanded for each scope base.
SCOPED_ROUTES: Final = (
    CREDENTIALS_LIST,
    CREDENTIALS_CREATE,
    CREDENTIAL_GET,
    CREDENTIAL_UPDATE,
    CREDENTIAL_DELETE,
    CREDENTIAL_ROTATE,
    CREDENTIAL_VALIDATE,
    CREDENTIAL_DISABLE,
    CREDENTIAL_ENABLE,
    CREDENTIAL_RECONFIRM,
    CREDENTIAL_REMOTE_ARTIFACTS,
    BINDINGS_LIST,
    BINDINGS_CREATE,
    BINDING_GET,
    BINDING_UPDATE,
    BINDING_DELETE,
)


def all_routes() -> tuple[Route, ...]:
    """Every concrete route template the client may call."""
    fixed = tuple(
        value
        for value in globals().values()
        if isinstance(value, Route) and not value.path.startswith("{scope}")
    )
    scoped = tuple(
        Route(route.method, route.path.replace("{scope}", scope))
        for scope in (GLOBAL_SCOPE, TENANT_SCOPE, USER_SCOPE)
        for route in SCOPED_ROUTES
    )
    return fixed + scoped


__all__ = ["Route", "all_routes"]
