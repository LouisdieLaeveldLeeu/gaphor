"""Projection entry point: drop a SysML2 element onto a diagram.

Dropping projects an EXISTING semantic element: it looks up the diagram item
registered for the element's type, creates that item, and binds it via
`subject` (invariant 4 -- a diagram item is a view onto an element, created only
by projecting one that already exists, never symbol-only).
"""

from __future__ import annotations

from gaphor.core.modeling import Diagram
from gaphor.diagram.drop import drop
from gaphor.diagram.presentation import Presentation
from gaphor.diagram.support import get_diagram_item
from gaphor.SysML2 import sysml2


@drop.register(sysml2.PartDefinition, Diagram)
def drop_part_definition(
    element: sysml2.PartDefinition, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    item_class = get_diagram_item(type(element))
    if item_class is None:
        return None
    item = diagram.create(item_class)
    assert item
    item.matrix.translate(x, y)
    item.subject = element
    return item
