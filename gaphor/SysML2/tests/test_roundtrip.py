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
