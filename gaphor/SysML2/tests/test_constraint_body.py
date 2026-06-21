"""Constraint expression bodies (Phase 6a): preserved opaque text.

`constraint c { <expr> }` preserves the body as OPAQUE text (a TextualRepresentation,
language `sysml`, owned by the constraint) -- it is NOT parsed into an expression
tree. Covers parse, map, export, round-trip, persistence, basic well-formedness
validation, and UI-edit. The constraint rows stay `alpha` (no expression semantics).
"""

from __future__ import annotations

import pytest

from gaphor.core.modeling import Diagram, ElementFactory
from gaphor.diagram.drop import drop
from gaphor.diagram.tests.fixtures import find
from gaphor.SysML2 import constraints, kerml, sysml2
from gaphor.SysML2.export import export_namespace
from gaphor.SysML2.grammar import ast
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.propertypages import ConstraintBodyPropertyPage
from gaphor.SysML2.roundtrip import round_trip
from gaphor.SysML2.validation import has_errors, validate

import gaphor.SysML2.drop  # noqa: F401, E402
import gaphor.SysML2.propertypages  # noqa: F401, E402


def _map(text: str):
    factory = ElementFactory()
    return factory, map_package(parse(text), factory)


def _def(factory, name):
    return next(
        d for d in factory.select(sysml2.ConstraintDefinition) if d.declaredName == name
    )


def _usage(factory, name):
    return next(
        u for u in factory.select(sysml2.ConstraintUsage) if u.declaredName == name
    )


# --- parse -------------------------------------------------------------------


def test_parse_constraint_bodies():
    pkg = parse(
        "constraint def C { x > 0 }\nconstraint c : C { mass <= maxMass }\n"
        "constraint d;"
    )
    assert pkg.members == (
        ast.ConstraintDefinition(name="C", body="x > 0"),
        ast.ConstraintUsage(name="c", type_name=("C",), body="mass <= maxMass"),
        ast.ConstraintUsage(name="d"),
    )


def test_unbalanced_body_is_a_syntax_error():
    with pytest.raises(SyntaxError):
        parse("constraint c { x > 0 ;")


def test_requirement_body_is_not_parsed_in_6a():
    # Requirement bodies are Phase 6b; the requirement grammar has no body.
    with pytest.raises(SyntaxError):
        parse("requirement r { x > 0 }")


# --- map ---------------------------------------------------------------------


def test_body_is_stored_as_a_sysml_textual_representation():
    factory, _ = _map("constraint c { mass > 0 }")
    c = _usage(factory, "c")
    rep = constraints.body_representation(c)
    assert isinstance(rep, kerml.TextualRepresentation)
    assert rep.language == "sysml"
    assert rep.body == "mass > 0"
    # The carrier is owned by the constraint (so it cascades + round-trips).
    from gaphor.SysML2 import kerml_kernel as kk

    assert kk.owning_namespace(rep) is c


def test_no_body_stores_no_representation():
    factory, _ = _map("constraint c;")
    assert constraints.body_text(_usage(factory, "c")) is None
    assert not list(factory.select(kerml.TextualRepresentation))


def test_complex_body_with_nested_braces_is_preserved():
    factory, _ = _map("constraint c { f(a, b) >= g(c) and h({1, 2}) }")
    assert constraints.body_text(_usage(factory, "c")) == "f(a, b) >= g(c) and h({1, 2})"


# --- export / round-trip -----------------------------------------------------


def test_export_emits_body_or_semicolon():
    _factory, result = _map(
        "constraint def C { x > 0 }\nconstraint c : C { a and b }\nconstraint d;"
    )
    text = export_namespace(result.root)
    assert "constraint def C { x > 0 }" in text
    assert "constraint c : C { a and b }" in text
    assert "constraint d;" in text


def test_constraint_body_round_trips():
    result = round_trip(
        "constraint def C { x > 0 }\nconstraint c : C { mass <= maxMass }\n"
        "constraint d;"
    )
    assert result.preserved
    assert result.valid


def test_body_vs_no_body_are_distinct_fingerprints():
    assert round_trip("constraint c;").source_form != round_trip(
        "constraint c { x }"
    ).source_form


def test_different_bodies_are_distinct_fingerprints():
    assert round_trip("constraint c { x > 0 }").source_form != round_trip(
        "constraint c { x < 0 }"
    ).source_form


# --- persistence -------------------------------------------------------------


def test_body_survives_save_reload(element_factory, saver, loader):
    map_package(parse("constraint c { mass > 0 }"), element_factory)
    c_id = _usage(element_factory, "c").id

    loader(saver())

    assert constraints.body_text(element_factory.lookup(c_id)) == "mass > 0"


# --- validation --------------------------------------------------------------


def test_empty_body_is_a_warning_not_an_error():
    factory, _ = _map("constraint c { }")
    diagnostics = validate(factory)
    empty = [d for d in diagnostics if d.rule == "empty-constraint-body"]
    assert empty and empty[0].severity.value == "warning"
    # A warning must not make the model invalid.
    assert not has_errors(diagnostics)


def test_non_empty_body_has_no_warning():
    factory, _ = _map("constraint c { x > 0 }")
    assert not any(
        d.rule == "empty-constraint-body" for d in validate(factory)
    )


# --- diagram -----------------------------------------------------------------


def test_constraint_with_body_projects_and_survives_reload(
    element_factory, saver, loader
):
    map_package(parse("constraint c { x > 0 }"), element_factory)
    c = _usage(element_factory, "c")
    diagram = element_factory.create(Diagram)

    item = drop(c, diagram, 0, 0)
    assert item is not None and item.subject is c
    c_id = c.id

    loader(saver())

    assert constraints.body_text(element_factory.lookup(c_id)) == "x > 0"


# --- UI-edit -----------------------------------------------------------------


def test_constraint_body_property_page_sets_and_clears(element_factory, event_manager):
    c = element_factory.create(sysml2.ConstraintUsage)
    c.declaredName = "c"
    page = ConstraintBodyPropertyPage(c, event_manager)

    widget = page.construct()
    entry = find(widget, "constraint-body")
    entry.set_text("mass > 0")
    assert constraints.body_text(c) == "mass > 0"

    entry.set_text("")  # clearing removes the body
    assert constraints.body_text(c) is None


def test_constraint_body_property_page_reflects_existing(element_factory, event_manager):
    c = element_factory.create(sysml2.ConstraintUsage)
    constraints.set_body_text(c, "a and b")
    page = ConstraintBodyPropertyPage(c, event_manager)

    entry = find(page.construct(), "constraint-body")
    assert entry.get_text() == "a and b"


def test_constraint_body_page_defers_for_requirements(element_factory, event_manager):
    # Requirement bodies are Phase 6b; the body editor must not apply to them.
    for cls in (sysml2.RequirementDefinition, sysml2.RequirementUsage):
        assert ConstraintBodyPropertyPage(
            element_factory.create(cls), event_manager
        ).construct() is None
