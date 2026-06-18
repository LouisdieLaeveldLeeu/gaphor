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


def test_parses_attribute_definition():
    pkg = parse("attribute def Mass;")
    assert pkg == ast.Package(members=(ast.AttributeDefinition(name="Mass"),))


def test_parses_typed_attribute_usage():
    pkg = parse("attribute m : Mass;")
    assert pkg == ast.Package(
        members=(ast.AttributeUsage(name="m", type_name=("Mass",)),)
    )


def test_parses_attribute_and_part_together():
    pkg = parse("attribute def Mass;\npart def Engine;\nattribute m : Mass;")
    assert pkg.members == (
        ast.AttributeDefinition(name="Mass"),
        ast.PartDefinition(name="Engine"),
        ast.AttributeUsage(name="m", type_name=("Mass",)),
    )


def test_parses_action_definition():
    pkg = parse("action def Brake;")
    assert pkg == ast.Package(members=(ast.ActionDefinition(name="Brake"),))


def test_parses_untyped_action_usage():
    pkg = parse("action brake;")
    assert pkg == ast.Package(
        members=(ast.ActionUsage(name="brake", type_name=None),)
    )


def test_parses_typed_action_usage():
    pkg = parse("action emergencyBrake : Brake;")
    assert pkg == ast.Package(
        members=(ast.ActionUsage(name="emergencyBrake", type_name=("Brake",)),)
    )


def test_parses_action_definition_and_usage_together():
    pkg = parse("action def Brake;\naction emergencyBrake : Brake;")
    assert pkg.members == (
        ast.ActionDefinition(name="Brake"),
        ast.ActionUsage(name="emergencyBrake", type_name=("Brake",)),
    )


def test_parses_constraint_definition_and_usage():
    pkg = parse("constraint def Limit;\nconstraint c : Limit;")
    assert pkg.members == (
        ast.ConstraintDefinition(name="Limit"),
        ast.ConstraintUsage(name="c", type_name=("Limit",)),
    )


def test_parses_requirement_definition_and_usage():
    pkg = parse("requirement def MassReq;\nrequirement r : MassReq;")
    assert pkg.members == (
        ast.RequirementDefinition(name="MassReq"),
        ast.RequirementUsage(name="r", type_name=("MassReq",)),
    )


def test_parses_untyped_requirement_usage():
    pkg = parse("requirement r;")
    assert pkg == ast.Package(
        members=(ast.RequirementUsage(name="r", type_name=None),)
    )


def test_parses_port_definition_and_usage():
    pkg = parse("port def Fuel;\nport p : Fuel;")
    assert pkg.members == (
        ast.PortDefinition(name="Fuel"),
        ast.PortUsage(name="p", type_name=("Fuel",)),
    )


def test_parses_untyped_port_usage():
    pkg = parse("port p;")
    assert pkg == ast.Package(members=(ast.PortUsage(name="p", type_name=None),))


def test_parses_empty_package_semicolon_form():
    pkg = parse("package P;")
    assert pkg == ast.Package(
        members=(ast.PackageDefinition(name="P", members=()),)
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
