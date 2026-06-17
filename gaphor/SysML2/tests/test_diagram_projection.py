"""Diagram projection (headless): a diagram item is a view onto a semantic
element via `subject`, created only by projecting an existing element -- never
symbol-only (invariant 4).
"""

from __future__ import annotations

from gaphor.core.modeling import Diagram
from gaphor.diagram.drop import drop
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2.diagramitems import (
    FeatureTypingItem,
    PartDefinitionItem,
    PartUsageItem,
)
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package

# Importing gaphor.SysML2.drop registers the projection handlers.
import gaphor.SysML2.drop  # noqa: F401, E402


def test_item_registered_for_part_definition():
    from gaphor.diagram.support import get_diagram_item

    assert get_diagram_item(sysml2.PartDefinition) is PartDefinitionItem


def test_drop_projects_an_existing_element(element_factory):
    # The element exists first; dropping creates a view bound to it.
    engine = element_factory.create(sysml2.PartDefinition)
    engine.declaredName = "Engine"
    diagram = element_factory.create(Diagram)

    item = drop(engine, diagram, 0, 0)

    assert isinstance(item, PartDefinitionItem)
    assert item.subject is engine
    assert item in diagram.ownedPresentation


def test_projection_subject_persists_and_reloads(element_factory, saver, loader):
    result = map_package(parse("part def Engine;"), element_factory)
    engine = result.elements_by_name["Engine"]
    diagram = element_factory.create(Diagram)
    item = drop(engine, diagram, 0, 0)
    item_id, engine_id = item.id, engine.id

    loader(saver())

    reloaded_item = element_factory.lookup(item_id)
    reloaded_engine = element_factory.lookup(engine_id)
    assert isinstance(reloaded_item, PartDefinitionItem)
    # The view -> element link survives the .gaphor round-trip.
    assert reloaded_item.subject is reloaded_engine


def test_deleting_element_removes_its_projection(element_factory):
    # No symbol-only state: unlinking the semantic element removes the view.
    engine = element_factory.create(sysml2.PartDefinition)
    diagram = element_factory.create(Diagram)
    item = drop(engine, diagram, 0, 0)
    item_id = item.id

    engine.unlink()

    assert element_factory.lookup(item_id) is None


def test_item_shows_subject_name(element_factory):
    engine = element_factory.create(sysml2.PartDefinition)
    engine.declaredName = "Engine"
    diagram = element_factory.create(Diagram)
    item = drop(engine, diagram, 0, 0)
    # The projection reflects the element's declared name (a view, not a copy).
    assert item.subject.declaredName == "Engine"


def test_part_usage_is_projectable(element_factory):
    usage = element_factory.create(sysml2.PartUsage)
    diagram = element_factory.create(Diagram)
    item = drop(usage, diagram, 0, 0)
    assert isinstance(item, PartUsageItem)
    assert item.subject is usage


def _project_tracer(element_factory):
    """Map the tracer pair and project both items, returning (diagram, usage,
    definition, typing)."""
    result = map_package(
        parse("part def Engine;\npart vehicleEngine : Engine;"), element_factory
    )
    engine = result.elements_by_name["Engine"]
    usage = result.elements_by_name["vehicleEngine"]
    typing = element_factory.lselect(kerml.FeatureTyping)[0]
    diagram = element_factory.create(Diagram)
    drop(engine, diagram, 0, 0)
    drop(usage, diagram, 100, 0)
    return diagram, usage, engine, typing


def test_feature_typing_projects_as_a_view_on_the_existing_typing(element_factory):
    diagram, usage, engine, typing = _project_tracer(element_factory)
    typings_before = len(element_factory.lselect(kerml.FeatureTyping))

    line = drop(typing, diagram, 50, 0)

    assert isinstance(line, FeatureTypingItem)
    # The line is a VIEW onto the existing typing -- it binds the same element,
    # and does NOT create a new FeatureTyping.
    assert line.subject is typing
    assert len(element_factory.lselect(kerml.FeatureTyping)) == typings_before


def test_typing_line_not_projected_when_an_endpoint_is_absent(element_factory):
    # Only the definition is projected (not the usage), so the typing line has
    # nothing to connect to and is not created -- never a dangling/symbol-only line.
    result = map_package(
        parse("part def Engine;\npart vehicleEngine : Engine;"), element_factory
    )
    engine = result.elements_by_name["Engine"]
    typing = element_factory.lselect(kerml.FeatureTyping)[0]
    diagram = element_factory.create(Diagram)
    drop(engine, diagram, 0, 0)  # usage NOT projected

    line = drop(typing, diagram, 50, 0)

    assert line is None
    assert not element_factory.lselect(FeatureTypingItem)


def test_typing_line_persists_and_reloads(element_factory, saver, loader):
    diagram, usage, engine, typing = _project_tracer(element_factory)
    line = drop(typing, diagram, 50, 0)
    line_id, typing_id = line.id, typing.id

    loader(saver())

    reloaded_line = element_factory.lookup(line_id)
    assert isinstance(reloaded_line, FeatureTypingItem)
    assert reloaded_line.subject is element_factory.lookup(typing_id)


def test_deleting_typing_removes_its_line(element_factory):
    diagram, usage, engine, typing = _project_tracer(element_factory)
    line = drop(typing, diagram, 50, 0)
    line_id = line.id

    typing.unlink()

    assert element_factory.lookup(line_id) is None
