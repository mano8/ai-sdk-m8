"""Package import and version parity checks."""

import re
import tomllib
from pathlib import Path

import ai_sdk_m8

ROOT = Path(__file__).resolve().parents[1]


def test_package_imports_and_exposes_version() -> None:
    """The empty package imports and exports only ``__version__``."""
    assert ai_sdk_m8.__all__ == ["__version__"]


def test_version_matches_pyproject() -> None:
    """``__version__`` equals the pyproject literal."""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"] == ai_sdk_m8.__version__


def test_changelog_has_current_version_heading() -> None:
    """CHANGELOG.md carries a Keep a Changelog heading for the version."""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    pattern = rf"^## \[{re.escape(ai_sdk_m8.__version__)}\] - \d{{4}}-\d{{2}}-\d{{2}}$"
    assert re.search(pattern, text, re.MULTILINE)


def test_core_dependencies_are_bounded() -> None:
    """Core deps stay pydantic + httpx; cryptography only behind the extra."""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    names = {re.split(r"[<>=!~ ]", d)[0] for d in data["project"]["dependencies"]}
    assert names == {"pydantic", "httpx"}
    extra = data["project"]["optional-dependencies"]["jobcontext"]
    assert [re.split(r"[<>=!~ ]", d)[0] for d in extra] == ["cryptography"]
