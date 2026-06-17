"""M2 sub-step 6: canonical round-trip harness + the first coverage-metric row.

The harness drives `part def Engine; part vehicleEngine : Engine;` through
import -> save -> reload -> export -> re-parse and compares CANONICAL forms
(structure + resolved references), never ids or raw text. This is the required
M2 deliverable and the first row of the growing coverage metric.
"""

from __future__ import annotations

from gaphor.SysML2.roundtrip import canonical_form, round_trip
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package

TRACER = "part def Engine;\npart vehicleEngine : Engine;"


def test_tracer_round_trip_preserves_canonical_form():
    result = round_trip(TRACER)
    assert result.preserved
    # The canonical form is the expected semantic structure.
    assert result.source_form == frozenset(
        {
            ("PartDefinition", "Root::Engine"),
            ("PartUsage", "Root::vehicleEngine", "Root::Engine"),
        }
    )


def test_round_trip_survives_save_reload():
    result = round_trip(TRACER)
    assert result.source_form == result.reloaded_form


def test_round_trip_survives_export_reparse():
    result = round_trip(TRACER)
    assert result.reloaded_form == result.reexported_form


def test_canonical_form_ignores_element_ids(element_factory):
    # Two independently-mapped models of the same text have equal canonical form
    # despite different element ids.
    a = map_package(parse(TRACER), element_factory)
    a.root.declaredName = "Root"
    from gaphor.core.modeling import ElementFactory

    b_factory = ElementFactory()
    b = map_package(parse(TRACER), b_factory)
    b.root.declaredName = "Root"

    assert canonical_form(a.root) == canonical_form(b.root)
    # ...but the elements are genuinely different objects/ids.
    a_engine = a.elements_by_name["Engine"]
    b_engine = b.elements_by_name["Engine"]
    assert a_engine.id != b_engine.id


def test_untyped_usage_round_trips():
    result = round_trip("part def Engine;\npart wheel;")
    assert result.preserved
    assert ("PartUsage", "Root::wheel", "") in result.source_form


def test_round_trip_includes_validation():
    # The harness runs validation as part of the chain; the valid tracer is
    # both preserved and valid.
    result = round_trip(TRACER)
    assert result.preserved
    assert result.valid


def test_round_trip_surfaces_validation_errors():
    # A duplicate-name model still round-trips structurally, but the harness
    # reports it as invalid -- preservation and validity are distinct.
    result = round_trip("part def Engine;\npart def Engine;")
    assert not result.valid


def test_cross_package_qualified_typing_round_trips():
    # Regression: export must emit a re-resolvable type name. A usage typed by a
    # definition in ANOTHER package must export the qualified name (A::Engine),
    # not the bare effective name, or re-import loses the typing.
    src = "package A { part def Engine; } package B { part e : A::Engine; }"
    result = round_trip(src)
    assert result.preserved
    assert result.valid
    assert (
        "PartUsage",
        "Root::B::e",
        "Root::A::Engine",
    ) in result.source_form


def test_nested_cross_package_qualified_typing_round_trips():
    src = (
        "package Outer { package Inner { part def Engine; } } "
        "package Uses { part e : Outer::Inner::Engine; }"
    )
    result = round_trip(src)
    assert result.preserved
    assert result.valid


def test_attribute_definition_and_usage_round_trip():
    src = "attribute def Mass;\nattribute m : Mass;"
    result = round_trip(src)
    assert result.preserved
    assert result.valid
    assert ("AttributeDefinition", "Root::Mass") in result.source_form
    assert (
        "AttributeUsage",
        "Root::m",
        "Root::Mass",
    ) in result.source_form


def test_attribute_in_package_cross_references_round_trip():
    src = (
        "package Units { attribute def Mass; } "
        "package M { attribute m : Units::Mass; }"
    )
    result = round_trip(src)
    assert result.preserved
    assert result.valid
    assert (
        "AttributeUsage",
        "Root::M::m",
        "Root::Units::Mass",
    ) in result.source_form


def test_empty_semicolon_package_round_trips():
    result = round_trip("package P;")
    assert result.preserved
    assert result.valid
    assert ("Package", "Root::P") in result.source_form


def test_nested_package_round_trips():
    src = "package Outer { package Inner { part def Engine; part e : Engine; } }"
    result = round_trip(src)
    assert result.preserved
    assert result.valid
    # Canonical form captures the nesting via qualified names.
    assert ("Package", "Root::Outer") in result.source_form
    assert ("Package", "Root::Outer::Inner") in result.source_form
    assert ("PartDefinition", "Root::Outer::Inner::Engine") in result.source_form
    assert (
        "PartUsage",
        "Root::Outer::Inner::e",
        "Root::Outer::Inner::Engine",
    ) in result.source_form
