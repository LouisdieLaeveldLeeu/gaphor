"""SysML v2 toolbox and diagram metadata.

Phase A intentionally exposes the modeling-language UI foundation only. It does
not add per-construct toolbox entries; those land in the construct promotion
phases that also add property pages and conformance tests.
"""

from __future__ import annotations

from gaphor.diagram.diagramtoolbox import DiagramTypes, ToolboxDefinition, ToolSection
from gaphor.i18n import gettext, i18nize
from gaphor.SysML2.diagramtype import SysML2Diagram, SysML2DiagramType

sysml2 = ToolSection(gettext("SysML v2"), ())

sysml2_toolbox_actions: ToolboxDefinition = (sysml2,)

sysml2_diagram_types: DiagramTypes = (
    SysML2DiagramType(SysML2Diagram, i18nize("SysML v2 Diagram"), (sysml2,)),
)

sysml2_element_types = ()

kerml_toolbox_actions: ToolboxDefinition = ()
kerml_diagram_types: DiagramTypes = ()
kerml_element_types = ()
