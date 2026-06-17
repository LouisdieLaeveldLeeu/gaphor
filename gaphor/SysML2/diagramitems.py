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

from gaphor.diagram.presentation import ElementPresentation, Named
from gaphor.diagram.shapes import Box, Text, draw_border
from gaphor.diagram.support import represents
from gaphor.SysML2 import sysml2


@represents(sysml2.PartDefinition)
class PartDefinitionItem(Named, ElementPresentation[sysml2.PartDefinition]):
    """A diagram view onto a SysML2 `PartDefinition` (its declared name)."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self.watch("subject[Element].declaredName", self.update_shapes)
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = Box(
            Text(
                text=lambda: (self.subject.declaredName if self.subject else "")
                or "",
            ),
            draw=draw_border,
        )
