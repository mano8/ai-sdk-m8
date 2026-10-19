"""Importing the package performs no network, file or environment I/O."""

import builtins
import importlib
import os
import socket
import sys
from collections.abc import Callable, Iterator

import pytest


class _IoAttempted(AssertionError):
    pass


def _refuse(*_args: object, **_kwargs: object) -> None:
    raise _IoAttempted("I/O attempted during import")


def _guard_env(original: Callable[..., object]) -> Callable[..., object]:
    """Refuse environment reads made by ``ai_sdk_m8`` code; pass others on.

    Pydantic reads ``PYDANTIC_DISABLE_PLUGINS`` whenever a model class is
    built; that is the dependency's behaviour, not this package's.
    """

    def guarded(*args: object, **kwargs: object) -> object:
        caller = sys._getframe(1).f_globals.get("__name__", "")
        if caller.split(".")[0] == "ai_sdk_m8":
            _refuse()
        return original(*args, **kwargs)

    return guarded


@pytest.fixture
def no_io(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Block sockets, DNS and ``open``; refuse the package's env reads."""
    for name in ("socket", "create_connection", "getaddrinfo", "gethostbyname"):
        monkeypatch.setattr(socket, name, _refuse)
    monkeypatch.setattr(builtins, "open", _refuse)
    monkeypatch.setattr(os, "getenv", _guard_env(os.getenv))
    yield


@pytest.fixture
def fresh_modules() -> Iterator[None]:
    """Drop every ``ai_sdk_m8`` module, then restore the originals."""
    saved = {k: v for k, v in sys.modules.items() if k.split(".")[0] == "ai_sdk_m8"}
    for name in saved:
        del sys.modules[name]
    yield
    for name in [k for k in sys.modules if k.split(".")[0] == "ai_sdk_m8"]:
        del sys.modules[name]
    sys.modules.update(saved)


def test_fixture_blocks_io(no_io: None) -> None:
    with pytest.raises(_IoAttempted):
        socket.create_connection(("example.invalid", 443))
    with pytest.raises(_IoAttempted):
        open(__file__)  # noqa: SIM115
    assert os.getenv("PATH") is not None  # reads from outside the package pass


@pytest.mark.parametrize(
    "module",
    [
        "ai_sdk_m8",
        "ai_sdk_m8.schemas",
        "ai_sdk_m8.headers",
        "ai_sdk_m8.signed",
        "ai_sdk_m8.jobcontext",
        "ai_sdk_m8.jobcontext._cli",
        "ai_sdk_m8.testing",
    ],
)
def test_import_performs_no_io(fresh_modules: None, no_io: None, module: str) -> None:
    imported = importlib.import_module(module)
    assert imported.__name__ == module
