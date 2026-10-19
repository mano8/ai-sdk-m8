"""
Authentication strategies of the gateway client.

``BearerJwt`` authenticates a user on the management routes only.
``ServiceClient`` authenticates a service (``X-Internal-Client`` +
``X-Internal-Token``) on the execution routes and on ``profiles:read``.
Neither holds a job context: a context authorises one call and is passed to
that call alone. Every secret is a ``SecretStr`` and ``repr`` redacts it.
"""

from typing import Final

from pydantic import SecretStr

from ai_sdk_m8.headers import INTERNAL_CLIENT_HEADER, INTERNAL_TOKEN_HEADER

#: The service-client id charset the fleet registries accept.
_CLIENT_ID_MAX: Final = 128


def _secret(value: str | SecretStr, what: str) -> SecretStr:
    if isinstance(value, SecretStr):
        value = value.get_secret_value()
    if not isinstance(value, str) or not value:
        raise ValueError(f"{what} must be a non-empty string")
    if any(ch in value for ch in "\r\n\x00"):
        raise ValueError(f"{what} must not contain line breaks or NUL")
    return SecretStr(value)


class BearerJwt:
    """A user access token, sent as ``Authorization: Bearer``."""

    __slots__ = ("_token",)

    def __init__(self, token: str | SecretStr) -> None:
        self._token = _secret(token, "token")

    def __repr__(self) -> str:
        return "BearerJwt(token=<redacted>)"

    def headers(self) -> dict[str, str]:
        """Headers that authenticate one request."""
        return {"Authorization": f"Bearer {self._token.get_secret_value()}"}


class ServiceClient:
    """A registered service client: its id and its secret."""

    __slots__ = ("_client_id", "_secret")

    def __init__(self, client_id: str, secret: str | SecretStr) -> None:
        if (
            not isinstance(client_id, str)
            or not client_id
            or len(client_id) > _CLIENT_ID_MAX
            or not client_id.isascii()
            or not client_id.isprintable()
            or " " in client_id
        ):
            raise ValueError("client_id must be a printable ASCII token")
        self._client_id = client_id
        self._secret = _secret(secret, "secret")

    @property
    def client_id(self) -> str:
        """The ``X-Internal-Client`` value."""
        return self._client_id

    def __repr__(self) -> str:
        return f"ServiceClient(client_id={self._client_id!r}, secret=<redacted>)"

    def headers(self) -> dict[str, str]:
        """Headers that authenticate one request."""
        return {
            INTERNAL_CLIENT_HEADER: self._client_id,
            INTERNAL_TOKEN_HEADER: self._secret.get_secret_value(),
        }


#: Either strategy.
Auth = BearerJwt | ServiceClient

__all__ = ["Auth", "BearerJwt", "ServiceClient"]
