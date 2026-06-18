"""SysML v2 diagram type.

This is UI infrastructure, not a generated SysML/KerML metamodel class. It gives
the modeling-language service a concrete diagram class with a stable
``diagramType`` id so Phase A can expose a real SysML2 diagram type without
claiming per-construct UI editing.
"""

from __future__ import annotations

from gaphor.core.modeling import Diagram
from gaphor.core.modeling.properties import attribute
from gaphor.diagram.diagramtoolbox import DiagramType


class SysML2Diagram(Diagram):
    diagramType: attribute[str] = attribute("diagramType", str, default="sysml2")


class SysML2DiagramType(DiagramType):
    def create(self, element_factory, element):
        diagram = element_factory.create(self.diagram_type)
        diagram.name = diagram.gettext(self.name)
        diagram.diagramType = self.id
        return diagram
