"""Command-line stubs for the SysML v2 textual workflow."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

NOT_IMPLEMENTED_EXIT_CODE = 1


def _stub_command(name: str):
    def run(_args: argparse.Namespace) -> int:
        print(
            f"SysML v2 {name} is scaffolded, "
            "but no SysML v2 semantics are implemented yet.",
            file=sys.stderr,
        )
        return NOT_IMPLEMENTED_EXIT_CODE

    return run


def validate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate SysML v2 text without importing it."
    )
    parser.add_argument("source", nargs="*", help="SysML v2 source file(s)")
    parser.set_defaults(command=_stub_command("validation"))
    return parser


def import_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import SysML v2 text into a Gaphor model."
    )
    parser.add_argument("source", nargs="?", help="SysML v2 source file")
    parser.add_argument("model", nargs="?", help="target .gaphor model")
    parser.set_defaults(command=_stub_command("import"))
    return parser


def export_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export a Gaphor model as SysML v2.")
    parser.add_argument("model", nargs="?", help="source .gaphor model")
    parser.add_argument("-o", "--output", help="output SysML v2 file")
    parser.set_defaults(command=_stub_command("export"))
    return parser


def parser_names() -> Sequence[str]:
    return ("sysml2-validate", "sysml2-import", "sysml2-export")
