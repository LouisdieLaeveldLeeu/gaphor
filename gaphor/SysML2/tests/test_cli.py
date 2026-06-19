"""CLI tests: the SysML v2 commands run the real pipeline (not stubs)."""

from __future__ import annotations

from pathlib import Path

from gaphor.SysML2 import cli

TRACER = "part def Engine;\npart vehicleEngine : Engine;"


def test_cli_parsers_are_registered_by_name():
    assert cli.parser_names() == (
        "sysml2-validate",
        "sysml2-import",
        "sysml2-export",
        "sysml2-round-trip",
        "sysml2-kpar-info",
    )


def test_kerml_sysml2_do_not_hijack_unqualified_lookup():
    # Regression: KerML/SysML2 generated class names (Class, Type, Feature, ...)
    # collide with legacy UML storage that persists names unqualified (ns=None).
    # An unqualified lookup of a COLLIDING name must still resolve to UML.
    from gaphor.services.modelinglanguage import ModelingLanguageService

    svc = ModelingLanguageService()
    cls = svc.lookup_element("Class")
    assert cls is not None and cls.__module__ == "gaphor.UML.uml"

    # SysML2/KerML do not participate in the unqualified fallback at all, so even
    # a non-colliding SysML2 name does not resolve without an explicit ns. This
    # is intentional: SysML2/KerML always persist and look up with a ns.
    assert svc.lookup_element("PartDefinition") is None


def test_qualified_lookup_reaches_kerml_and_sysml2_through_service():
    # The service now passes ns through to the routed provider, so a colliding
    # name resolves to the generated class when explicitly qualified -- while
    # the unqualified form (above) still goes to UML.
    from gaphor.services.modelinglanguage import ModelingLanguageService

    svc = ModelingLanguageService()
    kerml_cls = svc.lookup_element("Class", ns="KerML")
    assert kerml_cls is not None and kerml_cls.__module__ == "gaphor.SysML2.kerml"
    sysml2_type = svc.lookup_element("Type", ns="SysML2")
    assert sysml2_type is not None and sysml2_type.__module__ == "gaphor.SysML2.kerml"


def test_every_cli_command_has_a_packaged_entry_point():
    # Guard against drift: every command in parser_names() must be wired as a
    # gaphor.argparsers console entry point, or it is unreachable when packaged
    # (which is exactly how sysml2-round-trip was initially missed).
    from gaphor.entrypoint import load_entry_points

    registered = set(load_entry_points("gaphor.argparsers"))
    for name in cli.parser_names():
        assert name in registered, f"{name} is not a registered gaphor.argparsers entry point"


def test_validate_accepts_valid_text(tmp_path, capsys):
    src = tmp_path / "model.sysml"
    src.write_text(TRACER, encoding="utf-8")
    parser = cli.validate_parser()
    args = parser.parse_args([str(src)])
    assert args.command(args) == 0


def test_validate_reports_unresolved_type(tmp_path, capsys):
    src = tmp_path / "model.sysml"
    src.write_text("part p : Missing;", encoding="utf-8")
    parser = cli.validate_parser()
    args = parser.parse_args([str(src)])
    assert args.command(args) == cli.ERROR_EXIT_CODE
    assert "usage-without-valid-type" in capsys.readouterr().err


def test_validate_reports_parse_error(tmp_path, capsys):
    src = tmp_path / "bad.sysml"
    src.write_text("part def Engine", encoding="utf-8")  # missing ;
    parser = cli.validate_parser()
    args = parser.parse_args([str(src)])
    assert args.command(args) == cli.ERROR_EXIT_CODE
    assert "parse error" in capsys.readouterr().err


def test_import_then_export_round_trips(tmp_path):
    src = tmp_path / "model.sysml"
    src.write_text(TRACER, encoding="utf-8")
    model = tmp_path / "model.gaphor"
    out = tmp_path / "out.sysml"

    imp = cli.import_parser()
    imp_args = imp.parse_args([str(src), str(model)])
    assert imp_args.command(imp_args) == 0
    assert model.exists()

    exp = cli.export_parser()
    exp_args = exp.parse_args([str(model), "-o", str(out)])
    assert exp_args.command(exp_args) == 0

    exported = out.read_text(encoding="utf-8")
    assert "part def Engine;" in exported
    assert "part vehicleEngine : Engine;" in exported


def test_import_then_export_cross_package_round_trips(tmp_path):
    # Regression: the CLI saves the mapped root UNNAMED, so export must compute
    # the qualified type path relative to the (unnamed) export root -- emitting
    # `A::Engine`, not `::A::Engine` (which the grammar rejects). The
    # same-namespace tracer test above did not exercise this.
    src = tmp_path / "model.sysml"
    src.write_text(
        "package A { part def Engine; } package B { part e : A::Engine; }",
        encoding="utf-8",
    )
    model = tmp_path / "model.gaphor"
    out = tmp_path / "out.sysml"

    imp = cli.import_parser()
    imp_args = imp.parse_args([str(src), str(model)])
    assert imp_args.command(imp_args) == 0

    exp = cli.export_parser()
    exp_args = exp.parse_args([str(model), "-o", str(out)])
    assert exp_args.command(exp_args) == 0

    exported = out.read_text(encoding="utf-8")
    assert "part e : A::Engine;" in exported
    assert "::A::Engine" not in exported  # no stray leading separator

    # The exported text must re-import cleanly (validates, no parse error).
    reout = tmp_path / "re.gaphor"
    re_args = imp.parse_args([str(out), str(reout)])
    assert re_args.command(re_args) == 0


def test_import_refuses_invalid_model(tmp_path, capsys):
    src = tmp_path / "model.sysml"
    src.write_text("part p : Missing;", encoding="utf-8")
    model = tmp_path / "model.gaphor"

    imp = cli.import_parser()
    args = imp.parse_args([str(src), str(model)])
    assert args.command(args) == cli.ERROR_EXIT_CODE
    assert "import refused" in capsys.readouterr().err
    assert not model.exists()


def test_import_allow_invalid_overrides(tmp_path):
    src = tmp_path / "model.sysml"
    src.write_text("part p : Missing;", encoding="utf-8")
    model = tmp_path / "model.gaphor"

    imp = cli.import_parser()
    args = imp.parse_args([str(src), str(model), "--allow-invalid"])
    assert args.command(args) == 0
    assert model.exists()


def test_round_trip_command_reports_invalid(tmp_path, capsys):
    # Unresolved type: round-trips structurally but is invalid; the command must
    # not crash and must exit non-zero.
    src = tmp_path / "model.sysml"
    src.write_text("part p : Missing;", encoding="utf-8")
    parser = cli.round_trip_parser()
    args = parser.parse_args([str(src)])
    assert args.command(args) == cli.ERROR_EXIT_CODE


def test_round_trip_command_reports_preserved(tmp_path, capsys):
    src = tmp_path / "model.sysml"
    src.write_text(TRACER, encoding="utf-8")
    parser = cli.round_trip_parser()
    args = parser.parse_args([str(src)])
    assert args.command(args) == 0
    assert "canonical form preserved" in capsys.readouterr().out
