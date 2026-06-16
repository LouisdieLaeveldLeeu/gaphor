from gaphor.SysML2 import cli


def test_cli_stub_parsers_are_registered_by_name():
    assert cli.parser_names() == (
        "sysml2-validate",
        "sysml2-import",
        "sysml2-export",
    )


def test_validate_stub_fails_explicitly(capsys):
    parser = cli.validate_parser()
    args = parser.parse_args(["model.sysml"])

    assert args.command(args) == cli.NOT_IMPLEMENTED_EXIT_CODE
    assert "no SysML v2 semantics are implemented yet" in capsys.readouterr().err


def test_import_stub_fails_explicitly(capsys):
    parser = cli.import_parser()
    args = parser.parse_args(["model.sysml", "model.gaphor"])

    assert args.command(args) == cli.NOT_IMPLEMENTED_EXIT_CODE
    assert "no SysML v2 semantics are implemented yet" in capsys.readouterr().err


def test_export_stub_fails_explicitly(capsys):
    parser = cli.export_parser()
    args = parser.parse_args(["model.gaphor", "--output", "model.sysml"])

    assert args.command(args) == cli.NOT_IMPLEMENTED_EXIT_CODE
    assert "no SysML v2 semantics are implemented yet" in capsys.readouterr().err
