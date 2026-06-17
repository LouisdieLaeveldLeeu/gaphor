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
from gaphor.diagram.drop import drop
from gaphor.diagram.drop import diagram_has_presentation
from gaphor.diagram.presentation import Presentation
from gaphor.diagram.support import get_diagram_item, get_diagram_item_metadata
from gaphor.SysML2 import kerml, sysml2

# Importing diagramitems runs the @represents decorators that register the items
# this module's drop handlers look up. The dispatch path reaches drop without
# necessarily going through uicomponents, so the dependency is made explicit
# here rather than relied upon transitively.
from gaphor.SysML2 import diagramitems  # noqa: F401


def _project_element(element, diagram: Diagram, x: float, y: float):
    item_class = get_diagram_item(type(element))
    if item_class is None:
        return None
    item = diagram.create(item_class)
    assert item
    item.matrix.translate(x, y)
    item.subject = element
    return item


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


@drop.register(kerml.FeatureTyping, Diagram)
def drop_feature_typing(
    element: kerml.FeatureTyping, diagram: Diagram, x: float, y: float
) -> Presentation | None:
    """Project a FeatureTyping as a line that is a VIEW onto the existing typing.

    The line is created only when both ends (typedFeature, type) are already
    projected on this diagram, so it is never a symbol-only line. Its `subject`
    is bound to the existing typing; the handles are not auto-connected here
    (gaphas connection would invoke a connector that creates a NEW typing,
    duplicating the model element). Visual anchoring of the handles to the
    endpoint items is a follow-up that needs a custom connector reusing the
    existing subject; see MAPPING_DECISIONS.md.
    """
    item_class = get_diagram_item(type(element))
    if not item_class:
        return None
    metadata = get_diagram_item_metadata(item_class)
    if not metadata:
        return None
    heads = list(metadata["head"].get(element))
    tails = list(metadata["tail"].get(element))
    # Require both ends already projected (a view connects existing views).
    both_projected = any(
        diagram_has_presentation(diagram, h) for h in heads
    ) and any(diagram_has_presentation(diagram, t) for t in tails)
    if not both_projected:
        return None
    item = diagram.create(item_class)
    assert item
    item.matrix.translate(x, y)
    item.subject = element
    return item
