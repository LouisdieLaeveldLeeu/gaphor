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


def _subject_label(item) -> str:
    """The item's label: its subject's name, prefixed by a feature direction
    (`in`/`out`/`inout`) when the subject is a directed usage (Phase 8b).
    Definitions are not Features, so they show just the name."""
    subject = item.subject
    if subject is None:
        return ""
    name = subject.declaredName or ""
    direction = getattr(subject, "direction", None)
    return f"{direction} {name}" if direction is not None else name


def _name_box(item):
    """A box shape showing the item's subject's declared name (and direction)."""
    return Box(
        Text(text=lambda: _subject_label(item)),
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
        # Redraw when a usage's feature direction changes (no-op for definitions,
        # whose subject is not a Feature, so the path matches nothing).
        self.watch("subject[Feature].direction", self.update_shapes)
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _package_box(self)


@represents(sysml2.PartDefinition)
class PartDefinitionItem(Named, ElementPresentation[sysml2.PartDefinition]):
    """A diagram view onto a SysML2 `PartDefinition` (its declared name)."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self.watch("subject[Element].declaredName", self.update_shapes)
        # Redraw when a usage's feature direction changes (no-op for definitions,
        # whose subject is not a Feature, so the path matches nothing).
        self.watch("subject[Feature].direction", self.update_shapes)
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _name_box(self)


@represents(sysml2.AttributeDefinition)
class AttributeDefinitionItem(Named, ElementPresentation[sysml2.AttributeDefinition]):
    """A diagram view onto a SysML2 `AttributeDefinition`."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self.watch("subject[Element].declaredName", self.update_shapes)
        # Redraw when a usage's feature direction changes (no-op for definitions,
        # whose subject is not a Feature, so the path matches nothing).
        self.watch("subject[Feature].direction", self.update_shapes)
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _name_box(self)


@represents(sysml2.ActionDefinition)
class ActionDefinitionItem(Named, ElementPresentation[sysml2.ActionDefinition]):
    """A diagram view onto a SysML2 `ActionDefinition`."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self.watch("subject[Element].declaredName", self.update_shapes)
        # Redraw when a usage's feature direction changes (no-op for definitions,
        # whose subject is not a Feature, so the path matches nothing).
        self.watch("subject[Feature].direction", self.update_shapes)
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _name_box(self)


@represents(sysml2.ConstraintDefinition)
class ConstraintDefinitionItem(
    Named, ElementPresentation[sysml2.ConstraintDefinition]
):
    """A diagram view onto a SysML2 `ConstraintDefinition`."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self.watch("subject[Element].declaredName", self.update_shapes)
        # Redraw when a usage's feature direction changes (no-op for definitions,
        # whose subject is not a Feature, so the path matches nothing).
        self.watch("subject[Feature].direction", self.update_shapes)
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _name_box(self)


@represents(sysml2.RequirementDefinition)
class RequirementDefinitionItem(
    Named, ElementPresentation[sysml2.RequirementDefinition]
):
    """A diagram view onto a SysML2 `RequirementDefinition`."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self.watch("subject[Element].declaredName", self.update_shapes)
        # Redraw when a usage's feature direction changes (no-op for definitions,
        # whose subject is not a Feature, so the path matches nothing).
        self.watch("subject[Feature].direction", self.update_shapes)
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _name_box(self)


@represents(sysml2.PortDefinition)
class PortDefinitionItem(Named, ElementPresentation[sysml2.PortDefinition]):
    """A diagram view onto a SysML2 `PortDefinition`."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self.watch("subject[Element].declaredName", self.update_shapes)
        # Redraw when a usage's feature direction changes (no-op for definitions,
        # whose subject is not a Feature, so the path matches nothing).
        self.watch("subject[Feature].direction", self.update_shapes)
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _name_box(self)


@represents(sysml2.ConnectionDefinition)
class ConnectionDefinitionItem(
    Named, ElementPresentation[sysml2.ConnectionDefinition]
):
    """A diagram view onto a SysML2 `ConnectionDefinition`."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self.watch("subject[Element].declaredName", self.update_shapes)
        # Redraw when a usage's feature direction changes (no-op for definitions,
        # whose subject is not a Feature, so the path matches nothing).
        self.watch("subject[Feature].direction", self.update_shapes)
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _name_box(self)


@represents(sysml2.PartUsage)
class PartUsageItem(Named, ElementPresentation[sysml2.PartUsage]):
    """A diagram view onto a SysML2 `PartUsage` (its declared name)."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self.watch("subject[Element].declaredName", self.update_shapes)
        # Redraw when a usage's feature direction changes (no-op for definitions,
        # whose subject is not a Feature, so the path matches nothing).
        self.watch("subject[Feature].direction", self.update_shapes)
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _name_box(self)


@represents(sysml2.AttributeUsage)
class AttributeUsageItem(Named, ElementPresentation[sysml2.AttributeUsage]):
    """A diagram view onto a SysML2 `AttributeUsage`."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self.watch("subject[Element].declaredName", self.update_shapes)
        # Redraw when a usage's feature direction changes (no-op for definitions,
        # whose subject is not a Feature, so the path matches nothing).
        self.watch("subject[Feature].direction", self.update_shapes)
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _name_box(self)


@represents(sysml2.ActionUsage)
class ActionUsageItem(Named, ElementPresentation[sysml2.ActionUsage]):
    """A diagram view onto a SysML2 `ActionUsage`."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self.watch("subject[Element].declaredName", self.update_shapes)
        # Redraw when a usage's feature direction changes (no-op for definitions,
        # whose subject is not a Feature, so the path matches nothing).
        self.watch("subject[Feature].direction", self.update_shapes)
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _name_box(self)


@represents(sysml2.ConstraintUsage)
class ConstraintUsageItem(Named, ElementPresentation[sysml2.ConstraintUsage]):
    """A diagram view onto a SysML2 `ConstraintUsage`."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self.watch("subject[Element].declaredName", self.update_shapes)
        # Redraw when a usage's feature direction changes (no-op for definitions,
        # whose subject is not a Feature, so the path matches nothing).
        self.watch("subject[Feature].direction", self.update_shapes)
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _name_box(self)


@represents(sysml2.RequirementUsage)
class RequirementUsageItem(Named, ElementPresentation[sysml2.RequirementUsage]):
    """A diagram view onto a SysML2 `RequirementUsage`."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self.watch("subject[Element].declaredName", self.update_shapes)
        # Redraw when a usage's feature direction changes (no-op for definitions,
        # whose subject is not a Feature, so the path matches nothing).
        self.watch("subject[Feature].direction", self.update_shapes)
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _name_box(self)


@represents(sysml2.PortUsage)
class PortUsageItem(Named, ElementPresentation[sysml2.PortUsage]):
    """A diagram view onto a SysML2 `PortUsage`."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self.watch("subject[Element].declaredName", self.update_shapes)
        # Redraw when a usage's feature direction changes (no-op for definitions,
        # whose subject is not a Feature, so the path matches nothing).
        self.watch("subject[Feature].direction", self.update_shapes)
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _name_box(self)


@represents(
    sysml2.ConnectionUsage,
    head=kerml.Relationship.source,  # connector end 1
    tail=kerml.Relationship.target,  # connector end 2
)
class ConnectionUsageItem(LinePresentation):
    """A diagram view onto a `ConnectionUsage`: a line bound to its binary
    connector ends (head=source, tail=target), labelled with its name.

    The line is a view onto the connector/end state: connecting a handle to a
    feature item sets that end (source/target); the connection's own subject is
    preserved (see `ConnectionUsageConnect`), so the diagram never invents or
    duplicates a connection."""

    def __init__(self, diagram, id=None):
        super().__init__(
            diagram,
            id=id,
            shape_middle=Text(text=lambda: _subject_label(self)),
        )
        self._handles[0].pos = (0, 0)
        self._handles[1].pos = (40, 20)
        self.watch("subject[Element].declaredName")
        # A connection usage may be directed too; redraw the line label on change.
        self.watch("subject[Feature].direction")


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
