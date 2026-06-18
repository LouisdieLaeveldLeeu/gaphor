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
