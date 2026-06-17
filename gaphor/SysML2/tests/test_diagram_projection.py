"""Diagram projection (headless): a diagram item is a view onto a semantic
element via `subject`, created only by projecting an existing element -- never
symbol-only (invariant 4).
"""

from __future__ import annotations

from gaphor.core.modeling import Diagram
from gaphor.diagram.connectors import Connector
from gaphor.diagram.drop import drop
from gaphor.diagram.presentation import connect
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2.diagramitems import (
    FeatureTypingItem,
    PartDefinitionItem,
    PartUsageItem,
)
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package

# Importing gaphor.SysML2.drop registers the projection handlers + connector.
import gaphor.SysML2.drop  # noqa: F401, E402


def _allows(line, handle, target_item) -> bool:
    """Whether the FeatureTyping connector permits connecting `handle` to
    `target_item` (mirrors how the diagram gates a connection)."""
    connector = Connector(target_item, line)
    port = target_item.ports()[0]
    return bool(connector.allow(handle, port))


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


def test_feature_typing_line_is_anchored_to_its_endpoints(element_factory):
    diagram, usage, engine, typing = _project_tracer(element_factory)

    line = drop(typing, diagram, 50, 0)

    # Both handles are connected to the endpoint items (usage and definition),
    # and the connection did NOT create a duplicate typing (the connector reuses
    # the existing subject).
    connected_subjects = {
        diagram.connections.get_connection(h).connected.subject
        for h in line.handles()
        if diagram.connections.get_connection(h)
    }
    assert usage in connected_subjects
    assert engine in connected_subjects
    assert line.subject is typing
    assert len(element_factory.lselect(kerml.FeatureTyping)) == 1


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


# --- reconnect semantics of a projected typing line (a VIEW, not an editor) ---


def _project_with_other_usage(element_factory):
    """Project Engine + vehicleEngine + a second usage `other`, plus the typing
    line for vehicleEngine:Engine. Returns (diagram, line, usage_item,
    other_item, typing)."""
    result = map_package(
        parse(
            "part def Engine;\npart vehicleEngine : Engine;\npart other : Engine;"
        ),
        element_factory,
    )
    engine = result.elements_by_name["Engine"]
    usage = result.elements_by_name["vehicleEngine"]
    other = result.elements_by_name["other"]
    typing = next(
        t for t in element_factory.lselect(kerml.FeatureTyping) if usage in list(t.typedFeature)
    )
    diagram = element_factory.create(Diagram)
    engine_item = drop(engine, diagram, 0, 0)
    usage_item = drop(usage, diagram, 100, 0)
    other_item = drop(other, diagram, 200, 0)
    line = drop(typing, diagram, 50, 0)
    return diagram, line, usage_item, other_item, engine_item, typing


def test_reconnect_head_to_original_feature_keeps_one_typing(element_factory):
    diagram, line, usage_item, other_item, engine_item, typing = (
        _project_with_other_usage(element_factory)
    )
    before = len(element_factory.lselect(kerml.FeatureTyping))

    connect(line, line.head, usage_item)

    assert _allows(line, line.head, usage_item)
    assert line.subject is typing
    assert len(element_factory.lselect(kerml.FeatureTyping)) == before


def test_reconnect_head_to_other_usage_is_refused_no_duplicate(element_factory):
    diagram, line, usage_item, other_item, engine_item, typing = (
        _project_with_other_usage(element_factory)
    )
    before = len(element_factory.lselect(kerml.FeatureTyping))
    original_connection = diagram.connections.get_connection(line.head)
    assert original_connection
    assert original_connection.connected is usage_item

    # `other` is not the typing's typed feature -> the connector must refuse.
    assert not _allows(line, line.head, other_item)
    # Even if a connect is attempted, the visual endpoint, subject, and relation
    # count remain unchanged.
    connect(line, line.head, other_item)
    refused_connection = diagram.connections.get_connection(line.head)
    assert refused_connection
    assert refused_connection.connected is usage_item
    assert line.subject is typing
    assert len(element_factory.lselect(kerml.FeatureTyping)) == before


def test_reconnect_tail_to_non_type_is_refused(element_factory):
    diagram, line, usage_item, other_item, engine_item, typing = (
        _project_with_other_usage(element_factory)
    )
    before = len(element_factory.lselect(kerml.FeatureTyping))
    original_connection = diagram.connections.get_connection(line.tail)
    assert original_connection
    assert original_connection.connected is engine_item

    # The tail must be the typing's type (Engine); a usage item is not it.
    assert not _allows(line, line.tail, usage_item)
    connect(line, line.tail, usage_item)
    refused_connection = diagram.connections.get_connection(line.tail)
    assert refused_connection
    assert refused_connection.connected is engine_item
    assert line.subject is typing
    assert len(element_factory.lselect(kerml.FeatureTyping)) == before


def test_temporary_disconnect_preserves_the_view_subject(element_factory):
    diagram, line, usage_item, other_item, engine_item, typing = (
        _project_with_other_usage(element_factory)
    )
    from gaphor.diagram.connectors import Connector

    before = len(element_factory.lselect(kerml.FeatureTyping))

    # Disconnect the head handle; the line must still view the same typing, and
    # the disconnect must not add/remove any typing.
    connector = Connector(usage_item, line)
    connector.disconnect(line.head)

    assert line.subject is typing
    assert len(element_factory.lselect(kerml.FeatureTyping)) == before
