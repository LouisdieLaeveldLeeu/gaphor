"""Diagram projection (headless): a diagram item is a view onto a semantic
element via `subject`, created only by projecting an existing element -- never
symbol-only (invariant 4).
"""

from __future__ import annotations

from gaphor.core.modeling import Diagram
from gaphor.diagram.drop import drop
from gaphor.SysML2 import sysml2
from gaphor.SysML2.diagramitems import PartDefinitionItem
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package

# Importing gaphor.SysML2.drop registers the projection handler.
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
