"""Feature direction (Phase 8b): `in` / `out` / `inout` on usages.

A usage may carry a feature direction prefix, mapping to the nullable KerML
`Feature::direction`. Undirected (no prefix) is `None`, distinct from `in`.
Covers parse, map, export, round-trip, diagram label, and UI-edit, plus the
nullable-direction storage round-trip.
"""

from __future__ import annotations

import pytest

from gaphor.core.modeling import Diagram, ElementFactory
from gaphor.diagram.drop import drop
from gaphor.diagram.propertypages import PropertyPages
from gaphor.diagram.tests.fixtures import find
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2.diagramitems import (
    PartDefinitionItem,
    PartUsageItem,
    _subject_label,
)
from gaphor.SysML2.export import export_namespace
from gaphor.SysML2.grammar import ast
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.kerml import FeatureDirectionKind as D
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.propertypages import FeatureDirectionPropertyPage
from gaphor.SysML2.roundtrip import round_trip

# Importing registers the projection handlers and property pages.
import gaphor.SysML2.drop  # noqa: F401, E402
import gaphor.SysML2.propertypages  # noqa: F401, E402


def _map(text: str):
    factory = ElementFactory()
    return factory, map_package(parse(text), factory)


def _usage(factory, cls, name):
    return next(u for u in factory.select(cls) if u.declaredName == name)


# --- parse -------------------------------------------------------------------


def test_parse_direction_on_each_usage_kind():
    pkg = parse(
        "in part a;\nout attribute b;\ninout action c;\n"
        "in constraint d;\nout requirement e;\ninout port f;\nin connection g;"
    )
    directions = {m.name: m.direction for m in pkg.members}
    assert directions == {
        "a": "in",
        "b": "out",
        "c": "inout",
        "d": "in",
        "e": "out",
        "f": "inout",
        "g": "in",
    }


def test_undirected_usage_has_no_direction():
    pkg = parse("part p;")
    assert pkg.members[0].direction is None


def test_direction_is_rejected_on_a_definition():
    with pytest.raises(SyntaxError):
        parse("in part def D;")


def test_reserved_words_do_not_block_other_names():
    # `in`/`out`/`inout` are only directions in prefix position; a part may still
    # be named e.g. `inlet` (not a reserved word).
    assert parse("part inlet;").members[0] == ast.PartUsage(name="inlet")


# --- map ---------------------------------------------------------------------


def test_map_sets_feature_direction():
    factory, _ = _map("in part a;\nout part b;\ninout part c;\npart d;")
    assert _usage(factory, sysml2.PartUsage, "a").direction == D.in_
    assert _usage(factory, sysml2.PartUsage, "b").direction == D.out
    assert _usage(factory, sysml2.PartUsage, "c").direction == D.inout
    assert _usage(factory, sysml2.PartUsage, "d").direction is None


def test_definition_has_no_direction_attribute_set():
    factory, _ = _map("part def D;")
    # PartDefinition is a Classifier, not a Feature -- it has no direction.
    assert not hasattr(_usage(factory, sysml2.PartDefinition, "D"), "direction")


# --- export ------------------------------------------------------------------


def test_export_emits_direction_prefix():
    _factory, result = _map("in part a;\nout attribute b;\ninout port c;\npart d;")
    text = export_namespace(result.root)
    assert "in part a;" in text
    assert "out attribute b;" in text
    assert "inout port c;" in text
    assert "part d;" in text  # undirected: no prefix


# --- round-trip --------------------------------------------------------------


def test_all_directions_round_trip():
    result = round_trip(
        "in part a;\nout part b;\ninout part c;\npart d;"
    )
    assert result.preserved
    assert result.valid


def test_directed_and_undirected_are_distinct_fingerprints():
    assert round_trip("part p;").source_form != round_trip("in part p;").source_form


def test_distinct_directions_are_distinct_fingerprints():
    assert round_trip("in part p;").source_form != round_trip("out part p;").source_form


# --- nullable storage --------------------------------------------------------


def test_direction_persists_and_clears(element_factory, saver, loader):
    map_package(parse("in part a;\npart b;"), element_factory)
    a = _usage(element_factory, sysml2.PartUsage, "a")
    b = _usage(element_factory, sysml2.PartUsage, "b")
    a_id, b_id = a.id, b.id

    loader(saver())

    # The explicit `in` survives; the undirected `b` reloads as None (absence is
    # not persisted as a literal).
    assert element_factory.lookup(a_id).direction == D.in_
    assert element_factory.lookup(b_id).direction is None


# --- diagram -----------------------------------------------------------------


def test_diagram_label_shows_direction(element_factory):
    map_package(parse("in part a;\npart b;\npart def D;"), element_factory)
    a = _usage(element_factory, sysml2.PartUsage, "a")
    b = _usage(element_factory, sysml2.PartUsage, "b")
    d = _usage(element_factory, sysml2.PartDefinition, "D")
    diagram = element_factory.create(Diagram)

    a_item = drop(a, diagram, 0, 0)
    b_item = drop(b, diagram, 100, 0)
    d_item = drop(d, diagram, 200, 0)

    assert type(a_item) is PartUsageItem
    assert _subject_label(a_item) == "in a"
    assert _subject_label(b_item) == "b"  # undirected: just the name
    assert type(d_item) is PartDefinitionItem
    assert _subject_label(d_item) == "D"  # a definition never shows a direction


def test_directed_connection_line_label_shows_direction(element_factory):
    # A connection usage is a line item; its middle label must also show the
    # direction prefix (not just the name).
    from gaphor.SysML2.diagramitems import ConnectionUsageItem

    map_package(
        parse("in connection c;\nconnection d;"), element_factory
    )
    c = _usage(element_factory, sysml2.ConnectionUsage, "c")
    d = _usage(element_factory, sysml2.ConnectionUsage, "d")
    diagram = element_factory.create(Diagram)

    c_item = drop(c, diagram, 0, 0)
    d_item = drop(d, diagram, 50, 0)

    assert isinstance(c_item, ConnectionUsageItem)
    assert _subject_label(c_item) == "in c"
    assert _subject_label(d_item) == "d"  # undirected: just the name


# --- UI-edit -----------------------------------------------------------------


def test_direction_property_page_sets_and_clears(element_factory, event_manager):
    usage = element_factory.create(sysml2.PartUsage)
    usage.declaredName = "p"
    page = FeatureDirectionPropertyPage(usage, event_manager)

    widget = page.construct()
    dropdown = find(widget, "feature-direction")
    # Choices: 0=(undirected), 1=in, 2=out, 3=inout.
    dropdown.set_selected(2)
    assert usage.direction == D.out
    dropdown.set_selected(3)
    assert usage.direction == D.inout
    dropdown.set_selected(0)
    assert usage.direction is None


def test_direction_property_page_reflects_existing(element_factory, event_manager):
    usage = element_factory.create(sysml2.PortUsage)
    usage.direction = D.in_
    page = FeatureDirectionPropertyPage(usage, event_manager)

    widget = page.construct()
    dropdown = find(widget, "feature-direction")
    selected = dropdown.get_selected_item()
    assert selected is not None and selected.value == "in"


def test_direction_page_registered_for_usages_not_definitions(element_factory):
    def pages(element):
        return list(PropertyPages.find(element))

    for cls in (
        sysml2.PartUsage,
        sysml2.AttributeUsage,
        sysml2.ActionUsage,
        sysml2.ConstraintUsage,
        sysml2.RequirementUsage,
        sysml2.PortUsage,
        sysml2.ConnectionUsage,
    ):
        found = pages(element_factory.create(cls))
        # Exactly one direction editor per usage -- including ConnectionUsage (a
        # PartUsage) and RequirementUsage (a ConstraintUsage), matched by MRO.
        assert found.count(FeatureDirectionPropertyPage) == 1, cls

    for cls in (
        sysml2.PartDefinition,
        sysml2.AttributeDefinition,
        sysml2.PortDefinition,
        sysml2.ConnectionDefinition,
    ):
        assert FeatureDirectionPropertyPage not in pages(element_factory.create(cls)), cls
