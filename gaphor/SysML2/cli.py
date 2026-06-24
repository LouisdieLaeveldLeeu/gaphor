"""Command-line entry points for the SysML v2 textual workflow.

These wire the real M2 pipeline (parse -> map -> validate -> persist -> export
-> round-trip) so the CLI is a genuine path, not a stub. Scope matches the M2
tracer: PartDefinition/PartUsage. Unsupported input surfaces as a diagnostic or
a parse error, never a silent success.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from io import StringIO
from pathlib import Path

NOT_IMPLEMENTED_EXIT_CODE = 1
ERROR_EXIT_CODE = 2


def _modeling_language():
    from gaphor.core.modeling.modelinglanguage import (
        CoreModelingLanguage,
        MockModelingLanguage,
    )
    from gaphor.SysML2.modelinglanguage import (
        KerMLModelingLanguage,
        SysML2ModelingLanguage,
    )

    return MockModelingLanguage(
        CoreModelingLanguage(),
        KerMLModelingLanguage(),
        SysML2ModelingLanguage(),
    )


def _run_validate(args: argparse.Namespace) -> int:
    from gaphor.core.modeling import ElementFactory
    from gaphor.SysML2.grammar.parser import parse
    from gaphor.SysML2.mapping import map_package
    from gaphor.SysML2.validation import has_errors, validate

    text = Path(args.source).read_text(encoding="utf-8")
    try:
        pkg = parse(text)
    except SyntaxError as exc:
        print(f"parse error: {exc}", file=sys.stderr)
        return ERROR_EXIT_CODE

    factory = ElementFactory()
    result = map_package(pkg, factory)
    diagnostics = validate(factory, result.unresolved_types, result.mistyped, result.unresolved_ends, result.unresolved_frame_refs, result.ambiguous, result.unresolved_supertypes, result.unresolved_subsettings, result.unresolved_redefinitions)
    for d in diagnostics:
        print(f"{d.severity}: {d.rule}: {d.message}", file=sys.stderr)
    return ERROR_EXIT_CODE if has_errors(diagnostics) else 0


def _run_import(args: argparse.Namespace) -> int:
    """Parse + map SysML text and save it as a `.gaphor` model."""
    import gaphor.storage as storage
    from gaphor.core.modeling import ElementFactory
    from gaphor.SysML2.grammar.parser import parse
    from gaphor.SysML2.mapping import map_package
    from gaphor.SysML2.validation import has_errors, validate

    text = Path(args.source).read_text(encoding="utf-8")
    try:
        pkg = parse(text)
    except SyntaxError as exc:
        print(f"parse error: {exc}", file=sys.stderr)
        return ERROR_EXIT_CODE

    factory = ElementFactory()
    result = map_package(pkg, factory)

    # Validate before persisting: invalid input is never silently imported.
    diagnostics = validate(factory, result.unresolved_types, result.mistyped, result.unresolved_ends, result.unresolved_frame_refs, result.ambiguous, result.unresolved_supertypes, result.unresolved_subsettings, result.unresolved_redefinitions)
    for d in diagnostics:
        print(f"{d.severity}: {d.rule}: {d.message}", file=sys.stderr)
    if has_errors(diagnostics) and not args.allow_invalid:
        print(
            "import refused: model has validation errors "
            "(use --allow-invalid to import anyway)",
            file=sys.stderr,
        )
        return ERROR_EXIT_CODE

    with open(args.model, "w", encoding="utf-8") as f:
        storage.save(f, factory)
    return 0


def _run_export(args: argparse.Namespace) -> int:
    """Load a `.gaphor` model and emit SysML v2 text."""
    import gaphor.storage as storage
    from gaphor.core.modeling import ElementFactory
    from gaphor.SysML2 import kerml
    from gaphor.SysML2.export import export_namespace

    factory = ElementFactory()
    with open(args.model, encoding="utf-8") as f:
        storage.load(
            f, element_factory=factory, modeling_language=_modeling_language()
        )

    namespaces = [
        ns
        for ns in factory.select(kerml.Namespace)
        if kerml_kernel_owning_namespace(ns) is None
    ]
    text = "".join(export_namespace(ns) for ns in namespaces)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


def kerml_kernel_owning_namespace(ns):
    from gaphor.SysML2 import kerml_kernel as kk

    return kk.owning_namespace(ns)


def _run_round_trip(args: argparse.Namespace) -> int:
    """Run the canonical round-trip on a SysML text file and report."""
    from gaphor.SysML2.roundtrip import round_trip

    text = Path(args.source).read_text(encoding="utf-8")
    try:
        result = round_trip(text)
    except SyntaxError as exc:
        print(f"parse error: {exc}", file=sys.stderr)
        return ERROR_EXIT_CODE

    if result.preserved:
        print("round-trip: canonical form preserved")
    else:
        print("round-trip: canonical form NOT preserved", file=sys.stderr)
    for d in result.diagnostics:
        print(f"{d.severity}: {d.rule}: {d.message}", file=sys.stderr)
    return 0 if (result.preserved and result.valid) else ERROR_EXIT_CODE


def _run_kpar_info(args: argparse.Namespace) -> int:
    """Inspect a KPAR archive and print its metadata + model files (read-only).

    This does not import the archive into Gaphor; it only reports what the
    Phase 2 reader can determine. Malformed archives surface as a diagnostic and
    a non-zero exit, never a silent success.
    """
    from gaphor.SysML2.kpar import KparError, read_kpar

    try:
        archive = read_kpar(Path(args.archive))
    except KparError as exc:
        print(f"kpar error: {exc}", file=sys.stderr)
        return ERROR_EXIT_CODE

    print(f"archive: {archive.path}")
    print(f"project: {archive.project.name}")
    if archive.project.version:
        print(f"version: {archive.project.version}")
    if archive.project.description:
        print(f"description: {archive.project.description}")
    if archive.meta.metamodel:
        print(f"metamodel: {archive.meta.metamodel}")
    for usage in archive.project.usage:
        print(f"uses: {usage.resource}")
    print(f"model files ({len(archive.model_files)}):")
    for model_file in archive.model_files:
        print(f"  {model_file.name}")
    return 0


def _run_kpar_import(args: argparse.Namespace) -> int:
    """Import a user KPAR project into a `.gaphor` model (editable content).

    Per-member partial import: parseable members are imported and saved, rejected
    members and unresolved references are reported as diagnostics. Exits non-zero
    if the archive is invalid or nothing supported was found.
    """
    import gaphor.storage as storage
    from gaphor.SysML2.kpar import KparError
    from gaphor.SysML2.kpar.project_import import import_user_kpar

    try:
        result = import_user_kpar(Path(args.archive))
    except KparError as exc:
        print(f"kpar error: {exc}", file=sys.stderr)
        return ERROR_EXIT_CODE

    for rejected in result.rejected_members:
        print(
            f"warning: skipped unsupported member {rejected.member}: "
            f"{rejected.message}",
            file=sys.stderr,
        )
    for dep in result.external_dependencies:
        print(
            f"warning: external dependency not imported (self-contained import): "
            f"{dep.resource}",
            file=sys.stderr,
        )

    if not result.imported_any:
        print("kpar import: no supported content found", file=sys.stderr)
        return ERROR_EXIT_CODE

    # Validate before persisting (unresolved/mistyped/duplicate names surface
    # here, with provenance available via the result for programmatic callers).
    for d in result.validation_diagnostics:
        print(f"{d.severity}: {d.rule}: {d.message}", file=sys.stderr)
    if result.has_validation_errors and not args.allow_invalid:
        print(
            "import refused: model has validation errors "
            "(use --allow-invalid to import anyway)",
            file=sys.stderr,
        )
        return ERROR_EXIT_CODE

    with open(args.model, "w", encoding="utf-8") as f:
        storage.save(f, result.factory)
    print(f"imported {len(result.imported_members)} member(s) into {args.model}")
    return 0


def validate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate SysML v2 text without importing it."
    )
    parser.add_argument("source", help="SysML v2 source file")
    parser.set_defaults(command=_run_validate)
    return parser


def import_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import SysML v2 text into a Gaphor model."
    )
    parser.add_argument("source", help="SysML v2 source file")
    parser.add_argument("model", help="target .gaphor model")
    parser.add_argument(
        "--allow-invalid",
        action="store_true",
        help="import even if validation reports errors",
    )
    parser.set_defaults(command=_run_import)
    return parser


def export_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export a Gaphor model as SysML v2.")
    parser.add_argument("model", help="source .gaphor model")
    parser.add_argument("-o", "--output", help="output SysML v2 file")
    parser.set_defaults(command=_run_export)
    return parser


def round_trip_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Round-trip SysML v2 text and compare canonical forms."
    )
    parser.add_argument("source", help="SysML v2 source file")
    parser.set_defaults(command=_run_round_trip)
    return parser


def kpar_info_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect a KPAR archive (read-only): metadata and model files."
    )
    parser.add_argument("archive", help="path to a .kpar archive")
    parser.set_defaults(command=_run_kpar_info)
    return parser


def kpar_import_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import a user KPAR project into a Gaphor model (editable)."
    )
    parser.add_argument("archive", help="path to a .kpar project archive")
    parser.add_argument("model", help="target .gaphor model")
    parser.add_argument(
        "--allow-invalid",
        action="store_true",
        help="import even if validation reports errors",
    )
    parser.set_defaults(command=_run_kpar_import)
    return parser


def parser_names() -> Sequence[str]:
    return (
        "sysml2-validate",
        "sysml2-import",
        "sysml2-export",
        "sysml2-round-trip",
        "sysml2-kpar-info",
        "sysml2-kpar-import",
    )
