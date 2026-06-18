"""SysML v2 diagram items: views onto semantic elements (projection).

A diagram item is a PROJECTION of a semantic element, never storage (invariant
4): it is an `ElementPresentation` whose `subject` is an existing generated
SysML2 element, bound through Gaphor's subject mechanism. Items are created by
projecting an element that already exists (see `drop.py`), so there is no
symbol-only state -- delete the element and its projection goes with it.

Shapes show the subject's declared name. Diagram items remain views: semantic
elements are created or imported first, then projected through `subject`.
"""

from __future__ import annotations

from gaphor.core.modeling import DrawContext
from gaphor.diagram.presentation import (
    ElementPresentation,
    LinePresentation,
    Named,
)
from gaphor.diagram.shapes import Box, Text, cairo_state, draw_border, stroke
from gaphor.diagram.support import represents
from gaphor.SysML2 import kerml, sysml2


def _name_box(item):
    """A box shape showing the item's subject's declared name."""
    return Box(
        Text(text=lambda: (item.subject.declaredName if item.subject else "") or ""),
        draw=draw_border,
    )


def _package_box(item):
    """A package frame showing the item's subject's declared name."""
    return Box(
        Text(text=lambda: (item.subject.declaredName if item.subject else "") or ""),
        draw=draw_package,
    )


@represents(kerml.Package)
class PackageItem(Named, ElementPresentation[kerml.Package]):
    """A diagram view onto a KerML `Package` namespace."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id, width=120, height=80)
        self.watch("subject[Element].declaredName", self.update_shapes)
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _package_box(self)


@represents(sysml2.PartDefinition)
class PartDefinitionItem(Named, ElementPresentation[sysml2.PartDefinition]):
    """A diagram view onto a SysML2 `PartDefinition` (its declared name)."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self.watch("subject[Element].declaredName", self.update_shapes)
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _name_box(self)


@represents(sysml2.AttributeDefinition)
class AttributeDefinitionItem(Named, ElementPresentation[sysml2.AttributeDefinition]):
    """A diagram view onto a SysML2 `AttributeDefinition`."""

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


@represents(sysml2.AttributeUsage)
class AttributeUsageItem(Named, ElementPresentation[sysml2.AttributeUsage]):
    """A diagram view onto a SysML2 `AttributeUsage`."""

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


def draw_package(box, context: DrawContext, bounding_box):
    """Draw a simple package frame with a tab."""
    with cairo_state(context.cairo) as cr:
        o = 0.0
        h = bounding_box.height
        w = bounding_box.width
        tab_width = min(50, w * 0.45)
        tab_height = min(20, h * 0.3)
        cr.move_to(tab_width, tab_height)
        cr.line_to(tab_width, o)
        cr.line_to(o, o)
        cr.line_to(o, h)
        cr.line_to(w, h)
        cr.line_to(w, tab_height)
        cr.line_to(o, tab_height)
        stroke(context, fill=True)
