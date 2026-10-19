"""
Strict encodings of the signed-object rule (C-03).

* Unpadded base64url: padding, characters outside the alphabet and non-zero
  trailing bits are refused, so every byte string has exactly one encoding.
* JSON Canonicalization Scheme (RFC 8785), integer-only subset: object keys
  sorted by UTF-16 code units, integers within ±(2**53 - 1), no floats.
* Strict JSON parsing: duplicate keys, floats, ``NaN``/``Infinity``,
  out-of-range integers, lone surrogates and nesting deeper than
  ``MAX_DEPTH`` are refused.
"""

import base64
import json
import re
from collections.abc import Mapping, Sequence
from typing import Final

from ai_sdk_m8.schemas._base import JCS_INT_MAX
from ai_sdk_m8.signed._errors import MalformedSignedObjectError

#: Deepest container nesting a payload may have (the payload object is 1).
MAX_DEPTH: Final = 4

_B64URL: Final = re.compile(r"[A-Za-z0-9_-]+")
# Decimal digits of JCS_INT_MAX plus a sign: longer literals are refused
# before int() runs, so a huge literal costs nothing.
_MAX_INT_CHARS: Final = len(str(JCS_INT_MAX)) + 1


def b64url_encode(data: bytes) -> str:
    """Unpadded base64url of ``data``."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    """Decode strict unpadded base64url; anything non-canonical is refused."""
    if not _B64URL.fullmatch(text) or len(text) % 4 == 1:
        raise MalformedSignedObjectError("invalid base64url segment")
    raw = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    if b64url_encode(raw) != text:
        raise MalformedSignedObjectError("invalid base64url segment")
    return raw


def _string(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise MalformedSignedObjectError("string is not valid UTF-8") from None
    # json.dumps escapes exactly what ECMAScript's JSON.stringify escapes
    # (quote, backslash, controls below U+0020 with lower-case hex), which is
    # RFC 8785's string rule.
    return json.dumps(value, ensure_ascii=False)


def _object(value: Mapping[object, object], depth: int) -> str:
    members: list[tuple[str, str, object]] = []
    for key, item in value.items():
        if not isinstance(key, str):
            raise MalformedSignedObjectError("object key is not a string")
        # _string refuses a lone surrogate before the UTF-16 sort key is built.
        members.append((key, _string(key), item))
    # RFC 8785 orders keys by UTF-16 code units.
    members.sort(key=lambda member: member[0].encode("utf-16-be"))
    body = ",".join(f"{name}:{_encode(item, depth)}" for _, name, item in members)
    return "{" + body + "}"


def _encode(value: object, depth: int) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        if not -JCS_INT_MAX <= value <= JCS_INT_MAX:
            raise MalformedSignedObjectError("integer outside the JCS range")
        return str(value)
    if isinstance(value, str):
        return _string(value)
    if depth >= MAX_DEPTH:
        raise MalformedSignedObjectError("nesting too deep")
    if isinstance(value, Mapping):
        return _object(value, depth + 1)
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return "[" + ",".join(_encode(item, depth + 1) for item in value) + "]"
    raise MalformedSignedObjectError("value is not an integer-only JSON value")


def canonicalize(value: object) -> bytes:
    """``JCS(value)`` as UTF-8 bytes under the integer-only rule."""
    return _encode(value, 0).encode("utf-8")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    obj = dict(pairs)
    if len(obj) != len(pairs):
        raise MalformedSignedObjectError("duplicate object key")
    return obj


def _refuse_float(_literal: str) -> object:
    raise MalformedSignedObjectError("floating-point number")


def _bounded_int(literal: str) -> int:
    if len(literal) > _MAX_INT_CHARS:
        raise MalformedSignedObjectError("integer outside the JCS range")
    return int(literal)


def parse_strict(raw: bytes) -> object:
    """
    Parse ``raw`` as strict JSON.

    The result is re-checked by :func:`canonicalize`, which refuses lone
    surrogates (legal as JSON escapes), out-of-range integers and depth.
    """
    try:
        text = raw.decode("utf-8")
        value: object = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_float=_refuse_float,
            parse_constant=_refuse_float,
            parse_int=_bounded_int,
        )
    except MalformedSignedObjectError:
        raise
    except (ValueError, RecursionError):
        raise MalformedSignedObjectError("invalid JSON") from None
    canonicalize(value)
    return value


__all__ = [
    "MAX_DEPTH",
    "b64url_decode",
    "b64url_encode",
    "canonicalize",
    "parse_strict",
]
