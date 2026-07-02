"""Projection entry points: drop SysML2 elements onto a diagram.

Dropping projects an EXISTING semantic element: it looks up the diagram item
registered for the element's type, creates that item, and binds it via `subject`
(invariant 4 -- a diagram item is a view onto an element, created only by
projecting one that already exists, never symbol-only).

A FeatureTyping (a relationship) is projected as a line connecting the items of
its two ends; it only appears when BOTH ends are already projected (otherwise
there is nothing to connect, and the projection is skipped, not invented).
"""

from __future__ import annotations

from gaphor.core.modeling import Diagram
from gaphor.diagram.drop import diagram_has_presentation, drop
from gaphor.diagram.presentation import Presentation, connect
from gaphor.diagram.support import get_diagram_item, get_diagram_item_metadata
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk

# Importing diagramitems runs the @represents decorators (item registration) and
# connectors runs the @Connector.register decorators (the FeatureTyping connector
# that reuses the existing subject). The dispatch path reaches drop without
# necessarily going through uicomponents, so these dependencies are explicit.
from gaphor.SysML2 import connectors, diagramitems  # noqa: F401


def _project_element(element, diagram: Diagram, x: float, y: float):
    item_class = get_diagram_item(type(element))
    if item_class is None:
        return None
    item = diagram.create(item_class)
    assert item
    item.matrix.translate(x, y)
    item.subject = element
    return item


@drop.register(kerml.Package, Diagram)
def drop_package(
    element: kerml.Package, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    return _project_element(element, diagram, x, y)


@drop.register(sysml2.PartDefinition, Diagram)
def drop_part_definition(
    element: sysml2.PartDefinition, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    return _project_element(element, diagram, x, y)


@drop.register(sysml2.PartUsage, Diagram)
def drop_part_usage(
    element: sysml2.PartUsage, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    return _project_element(element, diagram, x, y)


@drop.register(sysml2.AttributeDefinition, Diagram)
def drop_attribute_definition(
    element: sysml2.AttributeDefinition, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    return _project_element(element, diagram, x, y)


@drop.register(sysml2.AttributeUsage, Diagram)
def drop_attribute_usage(
    element: sysml2.AttributeUsage, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    return _project_element(element, diagram, x, y)


@drop.register(sysml2.ActionDefinition, Diagram)
def drop_action_definition(
    element: sysml2.ActionDefinition, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    return _project_element(element, diagram, x, y)


@drop.register(sysml2.ActionUsage, Diagram)
def drop_action_usage(
    element: sysml2.ActionUsage, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    return _project_element(element, diagram, x, y)


@drop.register(sysml2.SuccessionAsUsage, Diagram)
def drop_succession(
    element: sysml2.SuccessionAsUsage, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    # A succession is a binary connector line: anchor its handles to the projected
    # step items exactly like a connection (else the line collapses unanchored).
    return drop_connection_usage(element, diagram, x, y)


@drop.register(sysml2.FlowUsage, Diagram)
def drop_flow(
    element: sysml2.FlowUsage, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    # A flow is a binary connector line: anchor its handles to the projected ends.
    return drop_connection_usage(element, diagram, x, y)


@drop.register(sysml2.ConstraintDefinition, Diagram)
def drop_constraint_definition(
    element: sysml2.ConstraintDefinition, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    return _project_element(element, diagram, x, y)


@drop.register(sysml2.ConstraintUsage, Diagram)
def drop_constraint_usage(
    element: sysml2.ConstraintUsage, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    return _project_element(element, diagram, x, y)


@drop.register(sysml2.RequirementDefinition, Diagram)
def drop_requirement_definition(
    element: sysml2.RequirementDefinition, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    return _project_element(element, diagram, x, y)


@drop.register(sysml2.RequirementUsage, Diagram)
def drop_requirement_usage(
    element: sysml2.RequirementUsage, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    return _project_element(element, diagram, x, y)


@drop.register(sysml2.ConcernDefinition, Diagram)
def drop_concern_definition(
    element: sysml2.ConcernDefinition, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    return _project_element(element, diagram, x, y)


@drop.register(sysml2.ConcernUsage, Diagram)
def drop_concern_usage(
    element: sysml2.ConcernUsage, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    return _project_element(element, diagram, x, y)


@drop.register(sysml2.PortDefinition, Diagram)
def drop_port_definition(
    element: sysml2.PortDefinition, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    # The implicit conjugate of a PortDefinition (a ConjugatedPortDefinition) has
    # no concrete syntax and is not a user-facing element; it surfaces only as
    # `~Original` on a port usage, so it is never projected as its own box.
    if isinstance(element, sysml2.ConjugatedPortDefinition):
        return None
    return _project_element(element, diagram, x, y)


@drop.register(sysml2.PortUsage, Diagram)
def drop_port_usage(
    element: sysml2.PortUsage, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    """Project a PortUsage as a boundary square (spec 8.2.3.12): attached to its
    owning part's item when that owner is already on the diagram, otherwise a
    clearly-labelled standalone square (never a bare one). Visual attach only -- the
    port's membership already exists in the model, so no subject is authored."""
    item = _project_element(element, diagram, x, y)
    if item is None:
        return None
    owner = kk.owning_namespace(element)
    owner_item = (
        diagram_has_presentation(diagram, owner) if owner is not None else None
    )
    if owner_item is not None:
        connect(item, item._handle, owner_item)
        item.change_parent(owner_item)
    return item


@drop.register(sysml2.ConnectionDefinition, Diagram)
def drop_connection_definition(
    element: sysml2.ConnectionDefinition, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    return _project_element(element, diagram, x, y)


@drop.register(sysml2.ConnectionUsage, Diagram)
def drop_connection_usage(
    element: sysml2.ConnectionUsage, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    """Project a ConnectionUsage as a line bound to its connector ends.

    The line is anchored to the source/target items when they are already on the
    diagram (a view onto the existing ends). A connection with no ends, or whose
    ends are not on the diagram, still projects as the line with its handles free.
    `ConnectionUsageConnect` preserves the existing connection subject, so
    anchoring the handles never creates a duplicate.
    """
    item = _project_element(element, diagram, x, y)
    if item is None:
        return None
    metadata = get_diagram_item_metadata(type(item))
    if metadata:
        for handle, end in ((item.head, "head"), (item.tail, "tail")):
            end_item = next(
                (
                    i
                    for e in metadata[end].get(element)
                    if (i := diagram_has_presentation(diagram, e))
                ),
                None,
            )
            if end_item is not None:
                connect(item, handle, end_item)
    return item


@drop.register(sysml2.InterfaceDefinition, Diagram)
def drop_interface_definition(
    element: sysml2.InterfaceDefinition, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    return _project_element(element, diagram, x, y)


@drop.register(sysml2.InterfaceUsage, Diagram)
def drop_interface_usage(
    element: sysml2.InterfaceUsage, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    # An InterfaceUsage IS a ConnectionUsage; project it as a line bound to its
    # connector ends exactly like a connection (via its own InterfaceUsageItem).
    return drop_connection_usage(element, diagram, x, y)


@drop.register(kerml.FeatureTyping, Diagram)
def drop_feature_typing(
    element: kerml.FeatureTyping, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    """Project a FeatureTyping as a line VIEW onto the existing typing, anchored
    to the endpoint items.

    The line is created only when both ends (head=typedFeature, tail=type) are
    already projected on this diagram, so it is never a symbol-only line. Its
    `subject` is bound to the existing typing, then its handles are connected to
    the head/tail items. The `FeatureTypingConnect` connector keeps that existing
    subject on connect (the generic connector would find-or-create a duplicate).
    """
    item_class = get_diagram_item(type(element))
    if not item_class:
        return None
    metadata = get_diagram_item_metadata(item_class)
    if not metadata:
        return None
    # Resolve the endpoint items (must both already be on the diagram).
    head_item = next(
        (
            i
            for h in metadata["head"].get(element)
            if (i := diagram_has_presentation(diagram, h))
        ),
        None,
    )
    tail_item = next(
        (
            i
            for t in metadata["tail"].get(element)
            if (i := diagram_has_presentation(diagram, t))
        ),
        None,
    )
    if head_item is None or tail_item is None:
        return None

    item = diagram.create(item_class)
    assert item
    item.matrix.translate(x, y)
    item.subject = element
    # Anchor the line to its endpoints; the connector reuses the existing
    # subject, so no duplicate typing is created.
    connect(item, item.head, head_item)
    connect(item, item.tail, tail_item)
    return item
