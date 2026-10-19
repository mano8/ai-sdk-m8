"""
The core package works without the ``jobcontext`` extra.

``cryptography`` is hidden from the import system, so the same checks hold
in the full test environment and in CI's ``core-without-extra`` job, which
installs the package without the extra.
"""

import importlib
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

_HIDDEN = "cryptography"


def _ours(name: str) -> bool:
    return name.split(".")[0] in {_HIDDEN, "ai_sdk_m8"}


@pytest.fixture
def without_cryptography() -> Iterator[None]:
    """Make every ``cryptography`` import fail; re-import the package fresh."""
    saved = {name: module for name, module in sys.modules.items() if _ours(name)}
    for name in saved:
        del sys.modules[name]
    sys.modules[_HIDDEN] = None  # type: ignore[assignment]
    yield
    for name in [name for name in sys.modules if _ours(name)]:
        del sys.modules[name]
    sys.modules.update(saved)


def test_cryptography_is_hidden(without_cryptography: None) -> None:
    with pytest.raises(ImportError):
        importlib.import_module("cryptography.hazmat.primitives.asymmetric.ed25519")


def test_core_imports_and_pure_parts_work(without_cryptography: None) -> None:
    signed = importlib.import_module("ai_sdk_m8.signed")
    jobcontext = importlib.import_module("ai_sdk_m8.jobcontext")
    importlib.import_module("ai_sdk_m8.testing")
    importlib.import_module("ai_sdk_m8.schemas")
    assert signed.canonicalize({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
    assert len(signed.derive_kid(b"\x00" * 32)) == 22
    assert jobcontext.JobContextPayload.__name__ == "JobContextPayload"


def test_use_raises_a_typed_error(without_cryptography: None) -> None:
    signed = importlib.import_module("ai_sdk_m8.signed")
    jobcontext = importlib.import_module("ai_sdk_m8.jobcontext")
    public = b"\x01" * 32
    kid = signed.derive_kid(public)
    payload = {"v": 1, "typ": "m8.ai.job-context.v1", "kid": kid}
    token = (
        signed.b64url_encode(signed.canonicalize(payload))
        + "."
        + signed.b64url_encode(b"\x00" * 64)
    )
    calls: tuple[Callable[[], object], ...] = (
        lambda: signed.public_key_from_seed(b"\x00" * 32),
        lambda: signed.sign_object(
            payload, domain="m8.ai.job-context.v1", seed=b"\x00" * 32
        ),
        lambda: jobcontext.verify(
            token, public_keys={kid: public}, aud="a", now=0, max_ttl=1, skew=0
        ),
    )
    for call in calls:
        with pytest.raises(signed.MissingExtraError, match=r"ai-sdk-m8\[jobcontext\]"):
            call()


def test_keygen_reports_the_missing_extra(
    without_cryptography: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli = importlib.import_module("ai_sdk_m8.jobcontext._cli")
    out = tmp_path / "seed"
    assert cli.main(["keygen", "--out", str(out)]) == 2
    assert not out.exists()
    assert "jobcontext" in capsys.readouterr().err
