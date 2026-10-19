"""
Known-answer vectors of the C-03 signed-object rule, shipped as package data.

Consumers test their signers and verifiers against the installed package,
never a sibling checkout:

>>> from ai_sdk_m8.testing import load_vectors
>>> vectors = load_vectors()  # doctest: +SKIP

The seeds are public test values derived as SHA-256(UTF-8(``seed_label``));
they authorise nothing. The file is read on call, never at import.
"""

import json
from importlib import resources

from pydantic import JsonValue

VECTORS_RESOURCE = "vectors.json"


def load_vectors() -> dict[str, JsonValue]:
    """The parsed ``vectors.json`` shipped with this package."""
    text = resources.files(__name__).joinpath(VECTORS_RESOURCE).read_text("utf-8")
    vectors: dict[str, JsonValue] = json.loads(text)
    return vectors


__all__ = ["VECTORS_RESOURCE", "load_vectors"]
