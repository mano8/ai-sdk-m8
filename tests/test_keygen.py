"""``python -m ai_sdk_m8.jobcontext keygen``."""

import runpy
import stat
import sys
from pathlib import Path

import pytest

from ai_sdk_m8.jobcontext._cli import main
from ai_sdk_m8.signed import (
    decode_public_key,
    derive_kid,
    load_seed_file,
    public_key_from_seed,
)


def test_keygen_writes_a_0600_seed_and_prints_kid_and_key(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "seed"
    assert main(["keygen", "--out", str(out)]) == 0
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    seed = load_seed_file(out)
    public = public_key_from_seed(seed)
    printed = capsys.readouterr()
    assert printed.out.splitlines() == [
        f"kid={derive_kid(public)}",
        f"public_key={printed.out.split('public_key=')[1].strip()}",
    ]
    assert decode_public_key(printed.out.split("public_key=")[1].strip()) == public
    assert seed.hex() not in printed.out + printed.err


def test_keygen_never_overwrites(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "seed"
    out.write_bytes(b"existing")
    assert main(["keygen", "--out", str(out)]) == 1
    assert out.read_bytes() == b"existing"
    printed = capsys.readouterr()
    assert printed.out == ""
    assert "cannot create" in printed.err


def test_keygen_requires_out(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["keygen"])
    assert caught.value.code == 2
    assert "--out" in capsys.readouterr().err


def test_module_entry_point(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "seed"
    monkeypatch.setattr(
        sys, "argv", ["ai_sdk_m8.jobcontext", "keygen", "--out", str(out)]
    )
    with pytest.raises(SystemExit) as caught:
        runpy.run_module("ai_sdk_m8.jobcontext", run_name="__main__")
    assert caught.value.code == 0
    assert len(out.read_bytes()) == 32
