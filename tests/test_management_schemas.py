"""Management wire models and the gateway meta model."""

import json
from typing import Any

import pytest
from client_samples import (
    MODEL_ID,
    PROVIDER_ID,
    binding_public,
    credential_public,
    credential_validation,
    gateway_meta,
    model_admin,
    profile_admin,
    profile_revision,
    provider_admin,
    remote_artifact,
)
from pydantic import BaseModel, SecretStr, ValidationError

from ai_sdk_m8.schemas import Capability, IdentityAssurance, ProviderBoundary
from ai_sdk_m8.schemas import management as m
from ai_sdk_m8.schemas.meta import GatewayMeta

SECRET = "sk-" + "z" * 40


def _provider(**changes: object) -> dict[str, object]:
    body: dict[str, object] = {
        "name": "Local Ollama",
        "provider_type": "ollama",
        "base_url": "http://ollama:11434",
        "auth_type": "none",
        "boundary": "local",
    }
    body.update(changes)
    return body


def _model(**changes: object) -> dict[str, object]:
    body: dict[str, object] = {
        "provider_id": str(PROVIDER_ID),
        "external_model_id": "nomic-embed-text:v1.5",
        "capabilities": ["embedding"],
        "dimensions": 768,
        "model_version_label": "v1.5",
    }
    body.update(changes)
    return body


# --- responses round-trip ----------------------------------------------------

RESPONSES: list[tuple[type[BaseModel], dict[str, object]]] = [
    (m.ProviderAdmin, provider_admin()),
    (m.ModelAdmin, model_admin()),
    (m.ProfileRevisionAdmin, profile_revision()),
    (m.ProfileAdmin, profile_admin()),
    (m.CredentialPublic, credential_public()),
    (m.CredentialValidation, credential_validation()),
    (m.RemoteArtifactPublic, remote_artifact()),
    (m.BindingPublic, binding_public()),
]


@pytest.mark.parametrize(
    ("model", "body"), RESPONSES, ids=[r[0].__name__ for r in RESPONSES]
)
def test_responses_round_trip_and_are_closed(
    model: type[BaseModel], body: dict[str, object]
) -> None:
    parsed = model.model_validate_json(json.dumps(body))
    assert json.loads(parsed.model_dump_json()) == body
    with pytest.raises(ValidationError):
        model.model_validate({**body, "unexpected": 1})
    with pytest.raises(ValidationError, match="frozen"):
        setattr(parsed, next(iter(model.model_fields)), None)


def test_no_response_model_has_a_secret_field() -> None:
    for model, _ in RESPONSES:
        for name, info in model.model_fields.items():
            assert "secret" not in name or name == "secret_hint", (model, name)
            assert info.annotation is not SecretStr


# --- providers ---------------------------------------------------------------


def test_provider_create_defaults() -> None:
    provider = m.ProviderCreate.model_validate(_provider())
    assert provider.enabled is True
    assert provider.boundary is ProviderBoundary.LOCAL


@pytest.mark.parametrize("name", ["x-api-key", "api-key", "x-goog-api-key", "x-a"])
def test_allowed_header_names(name: str) -> None:
    m.ProviderCreate.model_validate(
        _provider(auth_type="api_key_header", auth_header_name=name)
    )


@pytest.mark.parametrize(
    "name",
    [
        "Host",
        "host",
        "Proxy-Authorization",
        "proxy-authorization",
        "X-Internal-Token",
        "x-internal-token",
        "x-forwarded-for",
        "x-ai-job-context",
        "authorization",
        "cookie",
        "content-length",
        "X-Api-Key",
        "x-",
        "x-" + "a" * 61,
        "x-api_key",
    ],
)
def test_refused_header_names(name: str) -> None:
    with pytest.raises(ValidationError):
        m.ProviderCreate.model_validate(
            _provider(auth_type="api_key_header", auth_header_name=name)
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"auth_type": "api_key_header"},
        {"auth_type": "bearer", "auth_header_name": "x-api-key"},
        {"auth_type": "none", "auth_header_name": "x-api-key"},
    ],
)
def test_header_name_matches_auth_type(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="auth_header_name"):
        m.ProviderCreate.model_validate(_provider(**changes))


@pytest.mark.parametrize(
    "url", ["ftp://host", "ollama:11434", "https://" + "a" * 2050, ""]
)
def test_base_url_shape(url: str) -> None:
    with pytest.raises(ValidationError):
        m.ProviderCreate.model_validate(_provider(base_url=url))


@pytest.mark.parametrize("name", ["", " lead", "trail ", "a\nb", "a" * 65, "\x00"])
def test_names(name: str) -> None:
    with pytest.raises(ValidationError):
        m.ProviderCreate.model_validate(_provider(name=name))


def test_provider_update_presence_semantics() -> None:
    update = m.ProviderUpdate.model_validate({"auth_header_name": None})
    assert m.dump_body(update) == {"auth_header_name": None}
    assert m.dump_body(m.ProviderUpdate()) == {}
    for field in (
        "name",
        "provider_type",
        "base_url",
        "auth_type",
        "boundary",
        "enabled",
    ):
        with pytest.raises(ValidationError, match=f"{field} cannot be null"):
            m.ProviderUpdate.model_validate({field: None})


# --- models ------------------------------------------------------------------


def test_model_create_defaults() -> None:
    model = m.ModelCreate.model_validate(_model())
    assert model.identity_assurance is IdentityAssurance.OPERATOR_DECLARED
    assert model.metadata == {}


@pytest.mark.parametrize(
    "changes",
    [
        {"dimensions": None},
        {"capabilities": ["rerank"], "dimensions": 768},
        {"capabilities": []},
        {"capabilities": ["embedding", "embedding"]},
        {"capabilities": ["embedding", "chat"]},
        {"identity_assurance": "provider_digest"},
        {"external_model_id": "../x"},
        {"external_model_id": "a b"},
        {"model_version_label": ""},
        {"metadata": {"Bad-Key": 1}},
        {"dimensions": 0},
    ],
)
def test_model_create_refusals(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        m.ModelCreate.model_validate(_model(**changes))


def test_model_ids_with_namespaces_are_allowed() -> None:
    model = m.ModelCreate.model_validate(
        _model(external_model_id="mistralai/mistral-embed@2024-01")
    )
    assert model.external_model_id == "mistralai/mistral-embed@2024-01"


def test_model_update_refusals() -> None:
    for field in (
        "external_model_id",
        "capabilities",
        "model_version_label",
        "identity_assurance",
        "metadata",
        "enabled",
    ):
        with pytest.raises(ValidationError, match=f"{field} cannot be null"):
            m.ModelUpdate.model_validate({field: None})
    with pytest.raises(ValidationError, match="provider_digest"):
        m.ModelUpdate.model_validate({"identity_assurance": "provider_digest"})
    assert m.dump_body(m.ModelUpdate(model_revision=None, dimensions=None)) == {
        "model_revision": None,
        "dimensions": None,
    }


# --- profiles ----------------------------------------------------------------


def test_profile_create() -> None:
    profile = m.ProfileCreate(profile_key="ocr", capability=Capability.OCR)
    assert profile.execution_config == {}
    with pytest.raises(ValidationError, match="no V1 route"):
        m.ProfileCreate(profile_key="c", capability=Capability.CHAT)


@pytest.mark.parametrize(
    "config",
    [
        {"temperature": 0.2},
        {"a": {"b": {"c": {"d": {"e": 1}}}}},
        {"big": "x" * 5000},
        {"n": 2**53},
    ],
)
def test_execution_config_is_integer_only_bounded_json(config: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="execution_config"):
        m.ProfileCreate(
            profile_key="p", capability=Capability.RERANK, execution_config=config
        )


def test_execution_config_accepts_integer_json() -> None:
    config = {
        "max_output_tokens": 512,
        "temperature_bp": 2000,
        "mode": ["a", None, True],
    }
    profile = m.ProfileCreate(
        profile_key="p",
        capability=Capability.STRUCTURED_OUTPUT,
        execution_config=config,
    )
    assert profile.execution_config == config


def test_profile_update_refusals() -> None:
    for field in ("execution_config", "enabled"):
        with pytest.raises(ValidationError, match=f"{field} cannot be null"):
            m.ProfileUpdate.model_validate({field: None})


# --- credentials -------------------------------------------------------------


def test_credential_create_keeps_the_secret_out_of_repr_and_json() -> None:
    body = m.CredentialCreate(provider_id=PROVIDER_ID, name="k", secret=SECRET)
    assert SECRET not in repr(body)
    assert SECRET not in body.model_dump_json()
    assert m.dump_body(body)["secret"] == SECRET
    rotate = m.CredentialRotate(secret=SecretStr(SECRET))
    assert m.dump_body(rotate) == {"secret": SECRET}


@pytest.mark.parametrize(
    "field", ["owner_user_id", "tenant_id", "scope_type", "status", "fingerprint"]
)
def test_credential_create_refuses_ownership_fields(field: str) -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        m.CredentialCreate.model_validate(
            {"provider_id": str(PROVIDER_ID), "name": "k", "secret": SECRET, field: "x"}
        )


@pytest.mark.parametrize("secret", ["", "x" * 8193])
def test_secret_length(secret: str) -> None:
    with pytest.raises(ValidationError, match="secret must be"):
        m.CredentialRotate(secret=SecretStr(secret))


def test_credential_update_refusals() -> None:
    for field in ("name", "incident_listing_consent"):
        with pytest.raises(ValidationError, match=f"{field} cannot be null"):
            m.CredentialUpdate.model_validate({field: None})


@pytest.mark.parametrize("hint", ["abc", "abcde"])
def test_secret_hint_is_four_characters(hint: str) -> None:
    with pytest.raises(ValidationError):
        m.CredentialPublic.model_validate({**credential_public(), "secret_hint": hint})


# --- bindings ----------------------------------------------------------------


def test_binding_create_defaults_to_fail() -> None:
    binding = m.BindingCreate(profile_key="p", model_id=MODEL_ID)
    assert binding.on_unavailable is m.OnUnavailable.FAIL
    assert binding.credential_id is None


@pytest.mark.parametrize("field", ["owner_user_id", "tenant_id", "scope_type"])
def test_binding_create_refuses_ownership_fields(field: str) -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        m.BindingCreate.model_validate(
            {"profile_key": "p", "model_id": str(MODEL_ID), field: "x"}
        )


def test_binding_update_refusals() -> None:
    for field in ("model_id", "on_unavailable"):
        with pytest.raises(ValidationError, match=f"{field} cannot be null"):
            m.BindingUpdate.model_validate({field: None})
    assert m.dump_body(m.BindingUpdate(credential_id=None)) == {"credential_id": None}


# --- meta --------------------------------------------------------------------


def test_gateway_meta_reads_the_fleet_shape_and_ignores_extras() -> None:
    meta = GatewayMeta.model_validate({**gateway_meta(), "build": "x"})
    assert meta.contract.name == "ai-gateway-m8"
    assert meta.gateway.capabilities_enabled == (
        Capability.EMBEDDING,
        Capability.RERANK,
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"service": ""},
        {"gateway": {**gateway_meta()["gateway"], "data_class_policy_sha256": "x"}},  # type: ignore[dict-item]
        {"gateway": {**gateway_meta()["gateway"], "user_byok_enabled": "yes"}},  # type: ignore[dict-item]
    ],
)
def test_gateway_meta_refusals(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        GatewayMeta.model_validate(gateway_meta(**changes))
