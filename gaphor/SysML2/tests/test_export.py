"""M2 sub-step 5: textual export of the semantic model to SysML v2 text."""

from __future__ import annotations

from gaphor.SysML2.export import export_namespace
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package


def test_exports_part_definition(element_factory):
    result = map_package(parse("part def Engine;"), element_factory)
    assert export_namespace(result.root) == "part def Engine;\n"


def test_exports_untyped_usage(element_factory):
    result = map_package(parse("part vehicleEngine;"), element_factory)
    assert export_namespace(result.root) == "part vehicleEngine;\n"


def test_exports_typed_usage_with_typing_intact(element_factory):
    result = map_package(
        parse("part def Engine;\npart vehicleEngine : Engine;"), element_factory
    )
    text = export_namespace(result.root)
    assert "part def Engine;" in text
    assert "part vehicleEngine : Engine;" in text


def test_definition_stays_definition_usage_stays_usage(element_factory):
    result = map_package(
        parse("part def Engine;\npart vehicleEngine : Engine;"), element_factory
    )
    text = export_namespace(result.root)
    # The definition must not be emitted as a usage, nor the usage as a def.
    assert "part def Engine;" in text
    assert "part def vehicleEngine" not in text
    assert "part Engine" not in text.replace("part def Engine", "")


def test_export_is_reparseable(element_factory):
    src = "part def Engine;\npart vehicleEngine : Engine;"
    result = map_package(parse(src), element_factory)
    exported = export_namespace(result.root)
    # The exported text parses back to the same AST.
    assert parse(exported) == parse(src)
