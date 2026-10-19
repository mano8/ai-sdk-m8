"""JSON answers a stub gateway returns, one per response model."""

from uuid import UUID

from schema_samples import EXECUTION_ID, IDENTITY, SPACE, execution, ocr_result

from ai_sdk_m8.schemas import Capability

PROVIDER_ID = UUID("1b6f8c1e-2a4d-4e8b-9c3f-5d7a9e1b2c40")
MODEL_ID = UUID("2c7a9d2f-3b5e-4f9c-8d4a-6e8b0f2c3d51")
CREDENTIAL_ID = UUID("3d8b0e3a-4c6f-4a0d-9e5b-7f9c1a3d4e62")
BINDING_ID = UUID("4e9c1f4b-5d7a-4b1e-8f6c-8a0d2b4e5f73")
TENANT_ID = UUID("5f0d2a5c-6e8b-4c2f-9a7d-9b1e3c5f6a84")
USER_ID = UUID("6a1e3b6d-7f9c-4d3a-8b8e-0c2f4d6a7b95")
NOW = "2026-10-19T08:00:00Z"


def provider_admin() -> dict[str, object]:
    return {
        "id": str(PROVIDER_ID),
        "name": "Mistral EU",
        "provider_type": "mistral",
        "base_url": "https://api.mistral.ai",
        "auth_type": "bearer",
        "auth_header_name": None,
        "boundary": "external",
        "enabled": True,
        "first_used_at": None,
        "created_at": NOW,
        "updated_at": NOW,
    }


def model_admin() -> dict[str, object]:
    return {
        "id": str(MODEL_ID),
        "provider_id": str(PROVIDER_ID),
        "external_model_id": "mistral-embed",
        "capabilities": ["embedding"],
        "context_window": None,
        "max_output_tokens": None,
        "dimensions": 1024,
        "model_version_label": "2024-01",
        "model_revision": None,
        "identity_assurance": "operator_declared",
        "metadata": {},
        "enabled": True,
        "flagged_at": None,
        "first_used_at": None,
        "execution_identity": IDENTITY,
        "created_at": NOW,
        "updated_at": NOW,
    }


def profile_revision() -> dict[str, object]:
    return {
        "revision": 1,
        "execution_config": {},
        "execution_config_hash": "a" * 64,
        "created_at": NOW,
    }


def profile_admin() -> dict[str, object]:
    return {
        "id": str(BINDING_ID),
        "profile_key": "embed.small",
        "capability": "embedding",
        "enabled": True,
        "current": profile_revision(),
        "created_at": NOW,
        "updated_at": NOW,
    }


def credential_public() -> dict[str, object]:
    return {
        "id": str(CREDENTIAL_ID),
        "scope_type": "user",
        "tenant_id": str(TENANT_ID),
        "owner_user_id": str(USER_ID),
        "provider_id": str(PROVIDER_ID),
        "name": "my key",
        "status": "active",
        "current_version": 1,
        "secret_hint": "wxyz",
        "auth_failure_count": 0,
        "incident_listing_consent": False,
        "throttled_until": None,
        "created_at": NOW,
        "updated_at": NOW,
    }


def credential_validation() -> dict[str, object]:
    return {"outcome": "valid", "credential": credential_public()}


def remote_artifact() -> dict[str, object]:
    return {
        "id": str(BINDING_ID),
        "credential_version": 1,
        "status": "pending_delete",
        "remote_artifact_id": "file-123",
        "provider_expires_at": NOW,
        "created_at": NOW,
    }


def binding_public() -> dict[str, object]:
    return {
        "id": str(BINDING_ID),
        "profile_key": "embed.small",
        "scope_type": "tenant",
        "tenant_id": str(TENANT_ID),
        "owner_user_id": None,
        "model_id": str(MODEL_ID),
        "credential_id": str(CREDENTIAL_ID),
        "on_unavailable": "fail",
        "status": "active",
        "created_at": NOW,
        "updated_at": NOW,
    }


def profile_public() -> dict[str, object]:
    return {
        "profile_key": "embed.small",
        "capability": "embedding",
        "revision": 1,
        "enabled": True,
        "identity_assurance": "operator_declared",
        "dimensions": 2,
        "embedding_space_id": SPACE,
    }


def gateway_meta(**changes: object) -> dict[str, object]:
    meta: dict[str, object] = {
        "service": "ai-gateway-m8",
        "version": "0.2.0",
        "api_version": "v1",
        "contract": {
            "name": "ai-gateway-m8",
            "version": "1.0",
            "range": ">=1.0.0 <2.0.0",
        },
        "gateway": {
            "deployment_id": "8b2f0c3d-1e4a-4b5c-9d6e-7f8a9b0c1d2e",
            "user_byok_enabled": True,
            "job_context_max_ttl_seconds": 900,
            "dispatch_context_ttl_seconds": 30,
            "data_class_policy_sha256": "b" * 64,
            "capabilities_enabled": ["embedding", "rerank"],
            "credential_storage_backend": "database",
            "kek_key_version": "kek-1",
            "fingerprint_key_version": "fp-1",
        },
    }
    meta.update(changes)
    return meta


def spool_result() -> dict[str, object]:
    return {"spool_id": str(EXECUTION_ID), "expires_at": NOW}


def ocr_response() -> dict[str, object]:
    return {
        "result": ocr_result().model_dump(mode="json"),
        "execution": execution(Capability.OCR).model_dump(mode="json"),
    }


def embed_response() -> dict[str, object]:
    return {
        "result": {"dimensions": 2, "vectors": [[0.5, 0.25]]},
        "execution": execution(Capability.EMBEDDING).model_dump(mode="json"),
    }


def rerank_response() -> dict[str, object]:
    return {
        "result": {"hits": [{"index": 0, "relevance_score": 0.9}]},
        "execution": execution(Capability.RERANK).model_dump(mode="json"),
    }


def structured_output_response() -> dict[str, object]:
    return {
        "result": {"output": {"n": 1}},
        "execution": execution(Capability.STRUCTURED_OUTPUT).model_dump(mode="json"),
    }
