"""CLI tests: the SysML v2 commands run the real pipeline (not stubs)."""

from __future__ import annotations

from pathlib import Path

from gaphor.SysML2 import cli

TRACER = "part def Engine;\npart vehicleEngine : Engine;"


def test_cli_stub_parsers_are_registered_by_name():
    assert cli.parser_names() == (
        "sysml2-validate",
        "sysml2-import",
        "sysml2-export",
        "sysml2-round-trip",
    )


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
