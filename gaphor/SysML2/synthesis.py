"""On-demand SysML2 diagram synthesis (completion-roadmap Phase 13).

Turn an already-imported semantic model into useful INITIAL diagrams, so a human
evaluator does not have to drag every element by hand. Synthesis creates ONE diagram
per package/namespace and PROJECTS its content -- it never invents semantics: each
diagram item is a subject-bound view of an element that already exists (invariant 4),
reusing the same `drop` projection primitives the UI uses.

Two passes per diagram (so relationship lines find their endpoints):

1. project each groomable member as a box item (definitions and usages);
2. project the relationships among them as lines -- `FeatureTyping`s and connector
   usages -- which materialize ONLY when both ends are already on the diagram.

Then Gaphor's own auto-layout (graphviz) places the items. Synthesis is IDEMPOTENT:
a namespace already has its synthesized diagram (matched by a qualified-name-based
name) is returned as-is, never duplicated. Library proxies and relationship/membership
plumbing are never projected as boxes.
"""

from __future__ import annotations

from gaphor.core.modeling import Diagram
from gaphor.diagram.drop import drop
from gaphor.diagram.presentation import ElementPresentation
from gaphor.diagram.support import get_diagram_item
from gaphor.SysML2 import kerml
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2 import sysml2
from gaphor.SysML2.diagramtype import (
    PortDisplayMode,
    SysML2Diagram,
    show_boundary_ports,
)

# Importing drop/connectors/diagramitems runs the registration decorators, so
# synthesis works on the dispatch path without going through the GUI components.
from gaphor.SysML2 import connectors, diagramitems, drop as _drop_handlers  # noqa: F401

#: Appended to a synthesized diagram's name; also the idempotency marker.
SYNTHESIZED_SUFFIX = " (synthesized)"


def _box_item_class(element: kerml.Element):
    """The element's registered diagram item if it is a BOX (not a line), else None."""
    item_class = get_diagram_item(type(element))
    if item_class is not None and issubclass(item_class, ElementPresentation):
        return item_class
    return None


def _diagram_name(namespace: kerml.Namespace) -> str:
    base = kk.qualified_name(namespace) or kk.effective_name(namespace) or "Model"
    base = base.removeprefix("::")  # drop the unnamed-root qualifier
    return f"{base or 'Model'}{SYNTHESIZED_SUFFIX}"


def synthesized_diagram_for(namespace: kerml.Namespace) -> Diagram | None:
    """The existing synthesized diagram for `namespace`, or None (idempotency key)."""
    name = _diagram_name(namespace)
    return next(
        (d for d in namespace.model.select(Diagram) if d.name == name), None
    )


def _projectable_members(namespace: kerml.Namespace) -> list[kerml.Element]:
    return [
        m
        for m in kk.members(namespace)
        if not kk.is_library_proxy(m) and get_diagram_item(type(m)) is not None
    ]


def synthesize_diagram(
    namespace: kerml.Namespace,
    *,
    event_manager=None,
    layout: bool = True,
    port_display_mode: PortDisplayMode | str | None = None,
) -> Diagram | None:
    """Synthesize (or return the existing) diagram for `namespace`.

    Returns None when the namespace has no projectable members (no empty diagram is
    created). Idempotent: an existing synthesized diagram is returned unchanged.
    `port_display_mode` sets how ports are shown (defaults to the diagram default,
    BOUNDARY).
    """
    existing = synthesized_diagram_for(namespace)
    if existing is not None:
        return existing

    factory = namespace.model
    members = _projectable_members(namespace)
    if not members:
        return None

    # A SysML2Diagram (not a bare core Diagram) so the synthesized view is a
    # first-class SysML2 diagram -- browsable in the model tree, with the SysML2
    # toolbox/diagram type.
    diagram = factory.create(SysML2Diagram)
    diagram.name = _diagram_name(namespace)
    if port_display_mode is not None:
        diagram.portDisplayMode = PortDisplayMode(port_display_mode).value

    # Pass 1: box members (so relationship endpoints exist for pass 2).
    boxes = [m for m in members if _box_item_class(m) is not None]
    for member in boxes:
        drop(member, diagram, 0, 0)

    # Pass 1.5: boundary ports -- attach each boxed owner's PortUsage members to its
    # box as boundary squares (spec 8.2.3.12), when this diagram shows boundary ports.
    # The owners are already boxed (Pass 1), so drop_port_usage attaches each square.
    if show_boundary_ports(diagram):
        for owner in boxes:
            for port in [
                m for m in kk.members(owner) if isinstance(m, sysml2.PortUsage)
            ]:
                drop(port, diagram, 0, 0)

    # Pass 2a: typing lines -- a FeatureTyping materializes only when BOTH its ends
    # are already on this diagram (drop_feature_typing enforces that). Snapshot the
    # selection first, since `drop` creates presentation elements as it runs.
    for typing in list(factory.select(kerml.FeatureTyping)):
        drop(typing, diagram, 0, 0)
    # Pass 2b: connector/line members (ConnectionUsage, InterfaceUsage, ...).
    for member in members:
        if _box_item_class(member) is None:
            drop(member, diagram, 0, 0)

    if layout:
        _auto_layout(diagram, event_manager)
    return diagram


def synthesize_diagrams(root: kerml.Namespace, *, event_manager=None) -> list[Diagram]:
    """Synthesize a diagram for the root namespace and every (non-proxy) package.

    One diagram per namespace that has projectable members; idempotent across the
    whole set, so re-running adds only diagrams for namespaces that gained content.
    """
    factory = root.model
    namespaces: list[kerml.Namespace] = [root]
    namespaces += [
        p
        for p in list(factory.select(kerml.Package))
        if not kk.is_library_proxy(p) and p is not root
    ]
    diagrams = []
    for namespace in namespaces:
        diagram = synthesize_diagram(namespace, event_manager=event_manager)
        if diagram is not None:
            diagrams.append(diagram)
    return diagrams


def set_port_display_mode(diagram: Diagram, mode: PortDisplayMode | str) -> None:
    """Switch a diagram's PortDisplayMode and RECONCILE its presentation only.

    Model-safe (invariant 4): the same PortUsage elements are untouched -- this only
    adds/removes boundary port SQUARES (presentations) and rebuilds the box
    compartments. Boundary modes add a square for every boxed owner's ports that lacks
    one; non-boundary mode unlinks the squares; then the ports compartment is rebuilt
    to appear/disappear per the mode. Idempotent.
    """
    diagram.portDisplayMode = PortDisplayMode(mode).value
    existing = {
        item.subject: item
        for item in diagram.ownedPresentation
        if isinstance(item, diagramitems.PortUsageItem)
    }
    if show_boundary_ports(diagram):
        owners = [
            item
            for item in list(diagram.ownedPresentation)
            if isinstance(item, ElementPresentation) and isinstance(item.subject, kerml.Type)
        ]
        for owner_item in owners:
            for port in [
                m
                for m in kk.members(owner_item.subject)
                if isinstance(m, sysml2.PortUsage) and m not in existing
            ]:
                drop(port, diagram, 0, 0)
    else:
        for item in list(existing.values()):
            item.unlink()
    # Rebuild box compartments so the `ports` compartment reflects the new mode.
    for item in list(diagram.ownedPresentation):
        if isinstance(item, ElementPresentation):
            item.update_shapes()


def _auto_layout(diagram: Diagram, event_manager) -> None:
    from gaphor.plugins.autolayout.pydot import AutoLayout

    diagram.update(diagram.ownedPresentation)
    AutoLayout(event_manager).layout(diagram)
