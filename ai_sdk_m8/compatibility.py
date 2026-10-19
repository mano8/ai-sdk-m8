"""
Which gateways this SDK supports, checked against ``/meta`` on request.

The check runs only when the caller asks for it
(``client.check_compatibility()``); no client call reads ``/meta`` on its
own.
"""

import re
from typing import Final

from ai_sdk_m8._client_errors import IncompatibleGatewayError
from ai_sdk_m8.schemas.meta import GatewayMeta

#: Contract the gateway must name in ``/meta``.
CONTRACT_NAME: Final = "ai-gateway-m8"

#: Contract major version this SDK speaks.
CONTRACT_MAJOR: Final = 1

#: Oldest gateway release that serves every route this SDK calls.
MIN_GATEWAY_VERSION: Final = "0.2.0"

_VERSION: Final = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_CONTRACT_VERSION: Final = re.compile(r"(\d+)(?:\.\d+){0,2}")


def _release(version: str) -> tuple[int, int, int] | None:
    match = _VERSION.fullmatch(version)
    if match is None:
        return None
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def check_gateway_meta(meta: GatewayMeta) -> None:
    """Raise :class:`IncompatibleGatewayError` unless ``meta`` is supported."""
    if meta.contract.name != CONTRACT_NAME:
        raise IncompatibleGatewayError(f"gateway contract is not {CONTRACT_NAME!r}")
    contract = _CONTRACT_VERSION.fullmatch(meta.contract.version)
    if contract is None or int(contract.group(1)) != CONTRACT_MAJOR:
        raise IncompatibleGatewayError(
            f"gateway contract major is not {CONTRACT_MAJOR}"
        )
    found = _release(meta.version)
    minimum = _release(MIN_GATEWAY_VERSION)
    if found is None or minimum is None or found < minimum:
        raise IncompatibleGatewayError(
            f"gateway version is below {MIN_GATEWAY_VERSION}"
        )


__all__ = [
    "CONTRACT_MAJOR",
    "CONTRACT_NAME",
    "MIN_GATEWAY_VERSION",
    "check_gateway_meta",
]
