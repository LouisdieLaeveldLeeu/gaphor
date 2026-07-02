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
    AttachedPresentation,
    ElementPresentation,
    LinePresentation,
    Named,
)
from gaphor.diagram.shapes import (
    Box,
    CssNode,
    IconBox,
    Text,
    cairo_state,
    draw_border,
    stroke,
)
from gaphor.diagram.support import represents
from gaphor.SysML2 import conjugation, constraints, kerml, requirements, sysml2
from gaphor.SysML2.diagramtype import show_ports_compartment
from gaphor.SysML2.shapes import (
    feature_compartments,
    features_compartment,
    group_feature_compartments,
    name_label,
    node_shape,
    owned_features,
    text_compartment,
)


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


def _requirement_compartments(req):
    """A requirement/concern's spec compartments (8.2.3.21): id, subject, actors,
    stakeholders, `frames` (framed concerns), and the `assume constraints` /
    `require constraints` expressions -- the exact compartment labels from the pinned
    SysML v2 Language spec. Concerns are RequirementDefinition/Usage subtypes, so this
    serves both."""
    subj = requirements.subject(req)
    out = [
        text_compartment("id", [requirements.reqId(req) or ""]),
        text_compartment("subject", [name_label(subj)] if subj is not None else []),
        features_compartment("actors", list(requirements.actors(req))),
        features_compartment("stakeholders", list(requirements.stakeholders(req))),
        features_compartment("frames", list(requirements.framed_concerns(req))),
        text_compartment(
            "assume constraints",
            [
                constraints.body_text(c) or ""
                for c in requirements.requirement_constraints(
                    req, requirements.Assumption
                )
            ],
        ),
        text_compartment(
            "require constraints",
            [
                constraints.body_text(c) or ""
                for c in requirements.requirement_constraints(
                    req, requirements.Requirement
                )
            ],
        ),
    ]
    return [c for c in out if c is not None]


def _action_compartments(action):
    """An action's parameters (its directed features, 8.2.3.17) followed by its other
    owned features grouped by kind."""
    features = owned_features(action)
    parameters = [f for f in features if getattr(f, "direction", None) is not None]
    rest = [f for f in features if getattr(f, "direction", None) is None]
    out = [features_compartment("parameters", parameters)]
    out += group_feature_compartments(rest)
    return [c for c in out if c is not None]


def _construct_compartments(subject):
    """Construct-specific compartments for requirement/action/constraint subjects, or
    None to fall back to the generic owned-feature compartments."""
    if isinstance(subject, (sysml2.RequirementDefinition, sysml2.RequirementUsage)):
        return _requirement_compartments(subject)
    if isinstance(subject, (sysml2.ActionDefinition, sysml2.ActionUsage)):
        return _action_compartments(subject)
    if isinstance(subject, (sysml2.ConstraintDefinition, sysml2.ConstraintUsage)):
        body = constraints.body_text(subject)
        return [c for c in [text_compartment("constraint", [body or ""])] if c]
    return None


def _name_box(item):
    """The faithful SysML v2 node shape (Phase 15): the «keyword» name compartment
    (e.g. «part def» / «part» over `[direction] name : Type`) plus compartments --
    construct-specific for requirement/action/constraint (id/subject/expression/...),
    else the subject's owned features grouped by kind. Shared by every box item, so the
    notation is consistent and traces to `docs/sysml-v2/DIAGRAM_NOTATION.md`."""
    compartments = _construct_compartments(item.subject)
    if compartments is None:
        # A part's ports render as boundary squares by default (PortDisplayMode);
        # only list them in the `ports` compartment in compartment/both_debug mode.
        compartments = feature_compartments(
            item.subject, include_ports=show_ports_compartment(item.diagram)
        )
    return node_shape(item, *compartments)


def port_boundary_label(subject) -> str:
    """The boundary port's label: `[direction] name [: Type]`, rendering a conjugated
    port typing as `: ~Original` (spec 8.2.3.12; conjugation reused, not re-derived)."""
    if subject is None:
        return ""
    original = (
        conjugation.conjugated_type_name(subject)
        if isinstance(subject, sysml2.PortUsage)
        else None
    )
    if original is not None and original.declaredName:
        name = subject.declaredName or ""
        direction = getattr(subject, "direction", None)
        prefix = f"{direction} " if direction is not None else ""
        return f"{prefix}{name} : ~{original.declaredName}".strip()
    return name_label(subject)


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
        # Rebuild the shape when the subject attaches or its owned members change, so
        # the feature compartments stay current (the event-driven rebuild every gaphor
        # item relies on -- a live view needs an event manager, as in the app).
        self.watch("subject[Element].ownedRelationship", self.update_shapes)
        # ... and when a CONTAINED member's name/direction/typing changes, so the
        # feature compartments do not go stale after member edits (nested watches).
        _m = "subject[Element].ownedRelationship[OwningMembership].memberElement"
        self.watch(f"{_m}.declaredName", self.update_shapes)
        self.watch(f"{_m}[Feature].direction", self.update_shapes)
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type", self.update_shapes
        )
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type.declaredName",
            self.update_shapes,
        )
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
        # Rebuild the shape when the subject attaches or its owned members change, so
        # the feature compartments stay current (the event-driven rebuild every gaphor
        # item relies on -- a live view needs an event manager, as in the app).
        self.watch("subject[Element].ownedRelationship", self.update_shapes)
        # ... and when a CONTAINED member's name/direction/typing changes, so the
        # feature compartments do not go stale after member edits (nested watches).
        _m = "subject[Element].ownedRelationship[OwningMembership].memberElement"
        self.watch(f"{_m}.declaredName", self.update_shapes)
        self.watch(f"{_m}[Feature].direction", self.update_shapes)
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type", self.update_shapes
        )
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type.declaredName",
            self.update_shapes,
        )
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
        # Rebuild the shape when the subject attaches or its owned members change, so
        # the feature compartments stay current (the event-driven rebuild every gaphor
        # item relies on -- a live view needs an event manager, as in the app).
        self.watch("subject[Element].ownedRelationship", self.update_shapes)
        # ... and when a CONTAINED member's name/direction/typing changes, so the
        # feature compartments do not go stale after member edits (nested watches).
        _m = "subject[Element].ownedRelationship[OwningMembership].memberElement"
        self.watch(f"{_m}.declaredName", self.update_shapes)
        self.watch(f"{_m}[Feature].direction", self.update_shapes)
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type", self.update_shapes
        )
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type.declaredName",
            self.update_shapes,
        )
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
        # Rebuild the shape when the subject attaches or its owned members change, so
        # the feature compartments stay current (the event-driven rebuild every gaphor
        # item relies on -- a live view needs an event manager, as in the app).
        self.watch("subject[Element].ownedRelationship", self.update_shapes)
        # ... and when a CONTAINED member's name/direction/typing changes, so the
        # feature compartments do not go stale after member edits (nested watches).
        _m = "subject[Element].ownedRelationship[OwningMembership].memberElement"
        self.watch(f"{_m}.declaredName", self.update_shapes)
        self.watch(f"{_m}[Feature].direction", self.update_shapes)
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type", self.update_shapes
        )
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type.declaredName",
            self.update_shapes,
        )
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
        # Rebuild the shape when the subject attaches or its owned members change, so
        # the feature compartments stay current (the event-driven rebuild every gaphor
        # item relies on -- a live view needs an event manager, as in the app).
        self.watch("subject[Element].ownedRelationship", self.update_shapes)
        # ... and when a CONTAINED member's name/direction/typing changes, so the
        # feature compartments do not go stale after member edits (nested watches).
        _m = "subject[Element].ownedRelationship[OwningMembership].memberElement"
        self.watch(f"{_m}.declaredName", self.update_shapes)
        self.watch(f"{_m}[Feature].direction", self.update_shapes)
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type", self.update_shapes
        )
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type.declaredName",
            self.update_shapes,
        )
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
        # Rebuild the shape when the subject attaches or its owned members change, so
        # the feature compartments stay current (the event-driven rebuild every gaphor
        # item relies on -- a live view needs an event manager, as in the app).
        self.watch("subject[Element].ownedRelationship", self.update_shapes)
        # ... and when a CONTAINED member's name/direction/typing changes, so the
        # feature compartments do not go stale after member edits (nested watches).
        _m = "subject[Element].ownedRelationship[OwningMembership].memberElement"
        self.watch(f"{_m}.declaredName", self.update_shapes)
        self.watch(f"{_m}[Feature].direction", self.update_shapes)
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type", self.update_shapes
        )
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type.declaredName",
            self.update_shapes,
        )
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _name_box(self)


@represents(sysml2.ConcernDefinition)
class ConcernDefinitionItem(Named, ElementPresentation[sysml2.ConcernDefinition]):
    """A diagram view onto a SysML2 `ConcernDefinition` (Phase 6d).

    A ConcernDefinition IS a RequirementDefinition; the diagram registry is
    exact-type, so it needs its own item to project as itself."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self.watch("subject[Element].declaredName", self.update_shapes)
        self.watch("subject[Feature].direction", self.update_shapes)
        # Rebuild the shape when the subject attaches or its owned members change, so
        # the feature compartments stay current (the event-driven rebuild every gaphor
        # item relies on -- a live view needs an event manager, as in the app).
        self.watch("subject[Element].ownedRelationship", self.update_shapes)
        # ... and when a CONTAINED member's name/direction/typing changes, so the
        # feature compartments do not go stale after member edits (nested watches).
        _m = "subject[Element].ownedRelationship[OwningMembership].memberElement"
        self.watch(f"{_m}.declaredName", self.update_shapes)
        self.watch(f"{_m}[Feature].direction", self.update_shapes)
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type", self.update_shapes
        )
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type.declaredName",
            self.update_shapes,
        )
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
        # Rebuild the shape when the subject attaches or its owned members change, so
        # the feature compartments stay current (the event-driven rebuild every gaphor
        # item relies on -- a live view needs an event manager, as in the app).
        self.watch("subject[Element].ownedRelationship", self.update_shapes)
        # ... and when a CONTAINED member's name/direction/typing changes, so the
        # feature compartments do not go stale after member edits (nested watches).
        _m = "subject[Element].ownedRelationship[OwningMembership].memberElement"
        self.watch(f"{_m}.declaredName", self.update_shapes)
        self.watch(f"{_m}[Feature].direction", self.update_shapes)
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type", self.update_shapes
        )
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type.declaredName",
            self.update_shapes,
        )
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
        # Rebuild the shape when the subject attaches or its owned members change, so
        # the feature compartments stay current (the event-driven rebuild every gaphor
        # item relies on -- a live view needs an event manager, as in the app).
        self.watch("subject[Element].ownedRelationship", self.update_shapes)
        # ... and when a CONTAINED member's name/direction/typing changes, so the
        # feature compartments do not go stale after member edits (nested watches).
        _m = "subject[Element].ownedRelationship[OwningMembership].memberElement"
        self.watch(f"{_m}.declaredName", self.update_shapes)
        self.watch(f"{_m}[Feature].direction", self.update_shapes)
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type", self.update_shapes
        )
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type.declaredName",
            self.update_shapes,
        )
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
        # Rebuild the shape when the subject attaches or its owned members change, so
        # the feature compartments stay current (the event-driven rebuild every gaphor
        # item relies on -- a live view needs an event manager, as in the app).
        self.watch("subject[Element].ownedRelationship", self.update_shapes)
        # ... and when a CONTAINED member's name/direction/typing changes, so the
        # feature compartments do not go stale after member edits (nested watches).
        _m = "subject[Element].ownedRelationship[OwningMembership].memberElement"
        self.watch(f"{_m}.declaredName", self.update_shapes)
        self.watch(f"{_m}[Feature].direction", self.update_shapes)
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type", self.update_shapes
        )
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type.declaredName",
            self.update_shapes,
        )
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
        # Rebuild the shape when the subject attaches or its owned members change, so
        # the feature compartments stay current (the event-driven rebuild every gaphor
        # item relies on -- a live view needs an event manager, as in the app).
        self.watch("subject[Element].ownedRelationship", self.update_shapes)
        # ... and when a CONTAINED member's name/direction/typing changes, so the
        # feature compartments do not go stale after member edits (nested watches).
        _m = "subject[Element].ownedRelationship[OwningMembership].memberElement"
        self.watch(f"{_m}.declaredName", self.update_shapes)
        self.watch(f"{_m}[Feature].direction", self.update_shapes)
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type", self.update_shapes
        )
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type.declaredName",
            self.update_shapes,
        )
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
        # Rebuild the shape when the subject attaches or its owned members change, so
        # the feature compartments stay current (the event-driven rebuild every gaphor
        # item relies on -- a live view needs an event manager, as in the app).
        self.watch("subject[Element].ownedRelationship", self.update_shapes)
        # ... and when a CONTAINED member's name/direction/typing changes, so the
        # feature compartments do not go stale after member edits (nested watches).
        _m = "subject[Element].ownedRelationship[OwningMembership].memberElement"
        self.watch(f"{_m}.declaredName", self.update_shapes)
        self.watch(f"{_m}[Feature].direction", self.update_shapes)
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type", self.update_shapes
        )
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type.declaredName",
            self.update_shapes,
        )
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
        # Rebuild the shape when the subject attaches or its owned members change, so
        # the feature compartments stay current (the event-driven rebuild every gaphor
        # item relies on -- a live view needs an event manager, as in the app).
        self.watch("subject[Element].ownedRelationship", self.update_shapes)
        # ... and when a CONTAINED member's name/direction/typing changes, so the
        # feature compartments do not go stale after member edits (nested watches).
        _m = "subject[Element].ownedRelationship[OwningMembership].memberElement"
        self.watch(f"{_m}.declaredName", self.update_shapes)
        self.watch(f"{_m}[Feature].direction", self.update_shapes)
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type", self.update_shapes
        )
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type.declaredName",
            self.update_shapes,
        )
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
        # Rebuild the shape when the subject attaches or its owned members change, so
        # the feature compartments stay current (the event-driven rebuild every gaphor
        # item relies on -- a live view needs an event manager, as in the app).
        self.watch("subject[Element].ownedRelationship", self.update_shapes)
        # ... and when a CONTAINED member's name/direction/typing changes, so the
        # feature compartments do not go stale after member edits (nested watches).
        _m = "subject[Element].ownedRelationship[OwningMembership].memberElement"
        self.watch(f"{_m}.declaredName", self.update_shapes)
        self.watch(f"{_m}[Feature].direction", self.update_shapes)
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type", self.update_shapes
        )
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type.declaredName",
            self.update_shapes,
        )
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _name_box(self)


@represents(sysml2.ConcernUsage)
class ConcernUsageItem(Named, ElementPresentation[sysml2.ConcernUsage]):
    """A diagram view onto a SysML2 `ConcernUsage` (Phase 6d).

    A ConcernUsage IS a RequirementUsage; the diagram registry is exact-type, so
    it needs its own item to project as itself."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self.watch("subject[Element].declaredName", self.update_shapes)
        self.watch("subject[Feature].direction", self.update_shapes)
        # Rebuild the shape when the subject attaches or its owned members change, so
        # the feature compartments stay current (the event-driven rebuild every gaphor
        # item relies on -- a live view needs an event manager, as in the app).
        self.watch("subject[Element].ownedRelationship", self.update_shapes)
        # ... and when a CONTAINED member's name/direction/typing changes, so the
        # feature compartments do not go stale after member edits (nested watches).
        _m = "subject[Element].ownedRelationship[OwningMembership].memberElement"
        self.watch(f"{_m}.declaredName", self.update_shapes)
        self.watch(f"{_m}[Feature].direction", self.update_shapes)
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type", self.update_shapes
        )
        self.watch(
            f"{_m}[Feature].ownedRelationship[FeatureTyping].type.declaredName",
            self.update_shapes,
        )
        self.update_shapes()

    def update_shapes(self, event=None):
        self.shape = _name_box(self)


@represents(sysml2.PortUsage)
class PortUsageItem(Named, AttachedPresentation[sysml2.PortUsage]):
    """A SysML2 `PortUsage` as a small square attached to its owning part's boundary
    (spec 8.2.3.12), labelled `[direction] name [: Type]` (`~Original` when conjugated).

    Reuses gaphor's `AttachedPresentation` (the proxy-port/pin base): it provides the
    central boundary handle, the four edge `LinePort`s, the size constraints, and
    save/load/postload -- so the boundary attachment persists and reloads for free, and
    `update()` rebuilds the shape lazily (no event manager needed for the label). When
    its owner is not on the diagram it renders as a clearly-labelled standalone square,
    never a bare one."""

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id, width=16, height=16)
        # The label is late-evaluated (a lambda), so it re-renders on name/direction/
        # typing changes; a watch without a handler requests the redraw.
        self.watch("subject[Element].declaredName").watch("subject[Feature].direction")

    def update_shapes(self, event=None):
        self.shape = IconBox(
            Box(draw=draw_border),
            CssNode(
                "name",
                self.subject,
                Text(text=lambda: port_boundary_label(self.subject)),
            ),
        )


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


@represents(sysml2.InterfaceDefinition)
class InterfaceDefinitionItem(ConnectionDefinitionItem):
    """A diagram view onto a SysML2 `InterfaceDefinition` (a box).

    An InterfaceDefinition IS a ConnectionDefinition, so it reuses the connection
    definition box; registered for InterfaceDefinition so it wins over the
    inherited ConnectionDefinitionItem."""


@represents(
    sysml2.InterfaceUsage,
    head=kerml.Relationship.source,  # connector end 1
    tail=kerml.Relationship.target,  # connector end 2
)
class InterfaceUsageItem(ConnectionUsageItem):
    """A diagram view onto an `InterfaceUsage`: a line bound to its connector ends.

    An InterfaceUsage IS a ConnectionUsage, so it reuses the connection line (and,
    via MRO, the `ConnectionUsageConnect` connector); registered for InterfaceUsage
    with its own head/tail metadata so it wins over the inherited
    ConnectionUsageItem."""


@represents(
    sysml2.SuccessionAsUsage,
    head=kerml.Relationship.source,  # the `first` end
    tail=kerml.Relationship.target,  # the `then` end
)
class SuccessionAsUsageItem(ConnectionUsageItem):
    """A diagram view onto a `SuccessionAsUsage`: a line bound to its two step ends
    (head=source `first`, tail=target `then`). A binary connector usage, so it
    reuses the connection line via the same Relationship source/target ends
    (Phase 7). The diagram registry is exact-type, so it needs its own item."""


@represents(
    sysml2.FlowUsage,
    head=kerml.Relationship.source,  # the `from` end
    tail=kerml.Relationship.target,  # the `to` end
)
class FlowUsageItem(ConnectionUsageItem):
    """A diagram view onto a `FlowUsage`: a line bound to its two feature ends
    (head=source `from`, tail=target `to`). A FlowUsage IS an ActionUsage, but it is
    a binary connector, so it projects as the connection line, not the action box
    (registered for FlowUsage exactly so it wins) (Phase 7)."""


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
