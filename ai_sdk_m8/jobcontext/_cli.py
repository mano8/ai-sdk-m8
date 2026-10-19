"""
``python -m ai_sdk_m8.jobcontext keygen --out <seed-file>``.

Writes a fresh Ed25519 seed to a new ``0600`` file and prints only the
``kid`` and the public key. The seed itself is never printed.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from ai_sdk_m8.signed import (
    MissingExtraError,
    derive_kid,
    encode_public_key,
    generate_seed,
    public_key_from_seed,
    write_seed_file,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m ai_sdk_m8.jobcontext")
    commands = parser.add_subparsers(dest="command", required=True)
    keygen = commands.add_parser(
        "keygen", help="write a new Ed25519 seed file and print its kid"
    )
    keygen.add_argument(
        "--out", required=True, type=Path, help="seed file to create (must not exist)"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line; returns the process exit status."""
    args = _parser().parse_args(argv)
    seed = generate_seed()
    try:
        public_key = public_key_from_seed(seed)
    except MissingExtraError as exc:
        print(exc, file=sys.stderr)
        return 2
    try:
        write_seed_file(args.out, seed)
    except OSError as exc:
        print(f"cannot create {args.out}: {exc.strerror}", file=sys.stderr)
        return 1
    print(f"kid={derive_kid(public_key)}")
    print(f"public_key={encode_public_key(public_key)}")
    return 0


__all__ = ["main"]
