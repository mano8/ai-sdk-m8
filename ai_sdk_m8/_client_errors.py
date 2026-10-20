"""
Client-side errors.

A gateway answer that carries a valid :class:`~ai_sdk_m8.schemas.AiError`
raises :class:`~ai_sdk_m8.schemas.AiGatewayError`. Everything else is one of
these. None of them carries a header, a body or a secret: the message is the
status code or a fixed sentence.
"""


class AiGatewayClientError(Exception):
    """Base class of the client's own errors."""


class AiGatewayHTTPError(AiGatewayClientError):
    """A non-2xx answer whose body is not a gateway ``AiError``."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"gateway answered HTTP {status_code}")


class AiGatewayRedirectError(AiGatewayHTTPError):
    """A 3xx answer; redirects are never followed (credentials would leak)."""


class AiGatewayResponseError(AiGatewayClientError):
    """A 2xx answer whose body does not match the expected model."""

    def __init__(self) -> None:
        super().__init__("gateway answer does not match the expected model")


class IncompatibleGatewayError(AiGatewayClientError):
    """``/meta`` names a contract or a version this SDK does not support."""


__all__ = [
    "AiGatewayClientError",
    "AiGatewayHTTPError",
    "AiGatewayRedirectError",
    "AiGatewayResponseError",
    "IncompatibleGatewayError",
]
