"""SysML v2 diagram items: views onto semantic elements (projection).

A diagram item is a PROJECTION of a semantic element, never storage (invariant
4): it is an `ElementPresentation` whose `subject` is an existing generated
SysML2 element, bound through Gaphor's subject mechanism. Items are created by
projecting an element that already exists (see `drop.py`), so there is no
symbol-only state -- delete the element and its projection goes with it.

This is the projection-core slice: a named box for `PartDefinition`. The shape
shows the element's declared name; the GTK/toolbox/property-page surface beyond
this is later work.
"""

from __future__ import annotations

from gaphor.core.modeling import DrawContext
from gaphor.diagram.presentation import (
    ElementPresentation,
    LinePresentation,
    Named,
)
from gaphor.diagram.shapes import Box, Text, draw_border
from gaphor.diagram.support import represents
from gaphor.SysML2 import kerml, sysml2


def _name_box(item):
    """A box shape showing the item's subject's declared name."""
    return Box(
        Text(text=lambda: (item.subject.declaredName if item.subject else "") or ""),
        draw=draw_border,
    )


@represents(sysml2.PartDefinition)
class PartDefinitionItem(Named, ElementPresentation[sysml2.PartDefinition]):
    """A diagram view onto a SysML2 `PartDefinition` (its declared name)."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self.watch("subject[Element].declaredName", self.update_shapes)
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _name_box(self)


@represents(sysml2.PartUsage)
class PartUsageItem(Named, ElementPresentation[sysml2.PartUsage]):
    """A diagram view onto a SysML2 `PartUsage` (its declared name)."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self.watch("subject[Element].declaredName", self.update_shapes)
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _name_box(self)


@represents(
    kerml.FeatureTyping,
    head=kerml.FeatureTyping.typedFeature,  # the typed feature (usage) end
    tail=kerml.FeatureTyping.type,  # the type (definition) end
)
class FeatureTypingItem(LinePresentation):
    """A diagram view onto a `FeatureTyping`: a line from a usage to its type."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self._handles[0].pos = (0, 0)
        self._handles[1].pos = (30, 20)

    def draw_tail(self, context: DrawContext):
        # Open arrowhead at the type (definition) end.
        cr = context.cairo
        cr.line_to(15, 0)
        cr.move_to(15, -10)
        cr.line_to(0, 0)
        cr.line_to(15, 10)
