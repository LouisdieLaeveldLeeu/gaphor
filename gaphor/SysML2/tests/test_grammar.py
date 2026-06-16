"""M2 sub-step 1: SysML v2 grammar + AST for the vertical-tracer slice."""

from __future__ import annotations

import pytest

from gaphor.SysML2.grammar import ast
from gaphor.SysML2.grammar.parser import parse


def test_parses_part_definition():
    pkg = parse("part def Engine;")
    assert pkg == ast.Package(members=(ast.PartDefinition(name="Engine"),))


def test_parses_untyped_part_usage():
    pkg = parse("part vehicleEngine;")
    assert pkg == ast.Package(
        members=(ast.PartUsage(name="vehicleEngine", type_name=None),)
    )


def test_parses_typed_part_usage():
    pkg = parse("part vehicleEngine : Engine;")
    assert pkg == ast.Package(
        members=(ast.PartUsage(name="vehicleEngine", type_name=("Engine",)),)
    )


def test_parses_the_tracer_pair_together():
    pkg = parse("part def Engine;\npart vehicleEngine : Engine;")
    assert pkg == ast.Package(
        members=(
            ast.PartDefinition(name="Engine"),
            ast.PartUsage(name="vehicleEngine", type_name=("Engine",)),
        )
    )


def test_parses_qualified_type_name():
    pkg = parse("part e : Vehicles::Engine;")
    usage = pkg.members[0]
    assert isinstance(usage, ast.PartUsage)
    assert usage.type_name == ("Vehicles", "Engine")


def test_ignores_comments_and_whitespace():
    pkg = parse("// a part\n  part def Engine ;\n")
    assert pkg.members == (ast.PartDefinition(name="Engine"),)


def test_parses_empty_package():
    pkg = parse("package Vehicles { }")
    assert pkg == ast.Package(
        members=(ast.PackageDefinition(name="Vehicles", members=()),)
    )


def test_parses_package_with_members():
    pkg = parse("package Vehicles { part def Engine; part e : Engine; }")
    (vehicles,) = pkg.members
    assert isinstance(vehicles, ast.PackageDefinition)
    assert vehicles.name == "Vehicles"
    assert vehicles.members == (
        ast.PartDefinition(name="Engine"),
        ast.PartUsage(name="e", type_name=("Engine",)),
    )


def test_parses_nested_packages():
    pkg = parse("package Outer { package Inner { part def Engine; } }")
    (outer,) = pkg.members
    (inner,) = outer.members
    assert isinstance(inner, ast.PackageDefinition)
    assert inner.name == "Inner"
    assert inner.members == (ast.PartDefinition(name="Engine"),)


@pytest.mark.parametrize(
    "bad",
    [
        "part def Engine",  # missing semicolon
        "part def ;",  # missing name
        "definition Engine;",  # unknown keyword
        "part def 1Engine;",  # invalid identifier
        "package Vehicles {",  # unclosed package
        "package { }",  # missing package name
    ],
)
def test_invalid_text_raises_syntax_error(bad):
    with pytest.raises(SyntaxError):
        parse(bad)
