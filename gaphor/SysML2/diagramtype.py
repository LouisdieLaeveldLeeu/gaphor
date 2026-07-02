"""SysML v2 diagram type.

This is UI infrastructure, not a generated SysML/KerML metamodel class. It gives
the modeling-language service a concrete diagram class with a stable
``diagramType`` id so Phase A can expose a real SysML2 diagram type without
claiming per-construct UI editing.
"""

from __future__ import annotations

import enum

from gaphor.core.modeling import Diagram
from gaphor.core.modeling.properties import attribute
from gaphor.diagram.diagramtoolbox import DiagramType


class PortDisplayMode(enum.StrEnum):
    """How a SysML2 diagram presents a part's ports (Phase 15).

    A PortUsage is ONE semantic element; this is a per-DIAGRAM presentation choice
    (stored on `SysML2Diagram`, never on the model), so switching it never creates,
    deletes, or duplicates a PortUsage. `BOUNDARY` (the default) shows ports as
    boundary squares only; `COMPARTMENT` as text in the owner's `ports` compartment
    only; `BOTH_DEBUG` shows both (mainly for diagnostics)."""

    BOUNDARY = "boundary"
    COMPARTMENT = "compartment"
    BOTH_DEBUG = "both_debug"


class SysML2Diagram(Diagram):
    diagramType: attribute[str] = attribute("diagramType", str, default="sysml2")
    #: The port presentation mode (see PortDisplayMode); persisted, defaults BOUNDARY.
    portDisplayMode: attribute[str] = attribute(
        "portDisplayMode", str, default=PortDisplayMode.BOUNDARY.value
    )


def port_display_mode(diagram) -> PortDisplayMode:
    """The diagram's PortDisplayMode (BOUNDARY for a non-SysML2 diagram or an
    unset/unknown value), so callers always get a safe default."""
    value = getattr(diagram, "portDisplayMode", None)
    try:
        return PortDisplayMode(value) if value else PortDisplayMode.BOUNDARY
    except ValueError:
        return PortDisplayMode.BOUNDARY


def show_ports_compartment(diagram) -> bool:
    """Whether a part box lists its ports as compartment text on this diagram."""
    return port_display_mode(diagram) in (
        PortDisplayMode.COMPARTMENT,
        PortDisplayMode.BOTH_DEBUG,
    )


def show_boundary_ports(diagram) -> bool:
    """Whether synthesis draws boundary port squares on this diagram."""
    return port_display_mode(diagram) in (
        PortDisplayMode.BOUNDARY,
        PortDisplayMode.BOTH_DEBUG,
    )


class SysML2DiagramType(DiagramType):
    def create(self, element_factory, element):
        diagram = element_factory.create(self.diagram_type)
        diagram.name = diagram.gettext(self.name)
        diagram.diagramType = self.id
        return diagram
