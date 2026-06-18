"""SysML v2 modeling languages.

Two registered modeling languages back the generated layers so Gaphor's storage
and the code generator's supermodel resolution can look up element types by
namespace:

- `KerML` -> the generated KerML kernel (`kerml.py`). It is the supermodel the
  SysML2 layer generalizes, exactly as Core is the supermodel for UML.
- `SysML2` -> the generated SysML user concepts (`sysml2.py`), falling back to
  the M1a feasibility slice for its throwaway `Element`.

Phase A exposes the modeling-language UI foundation (toolbox metadata, diagram
types, element types, and a model-browser model). Per-construct toolbox entries
and property pages still land in later construct-promotion phases.
"""

from __future__ import annotations

from collections.abc import Iterable

from gaphor.abc import ModelingLanguage
from gaphor.diagram.diagramtoolbox import (
    DiagramType,
    ElementCreateInfo,
    ToolboxDefinition,
)
from gaphor.SysML2.toolbox import (
    kerml_diagram_types,
    kerml_element_types,
    kerml_toolbox_actions,
    sysml2_diagram_types,
    sysml2_element_types,
    sysml2_toolbox_actions,
)

# The SysML2/KerML generated classes share many names with legacy UML/Core
# (Class, Type, Feature, ...), and legacy `.gaphor` models persist those names
# unqualified (ns=None). To avoid hijacking legacy loads, these languages answer
# ONLY their explicit namespace and never participate in the unqualified
# fallback. This is sufficient: SysML2/KerML elements always persist with an
# explicit ns, and the code generator always passes a ns to lookup_element, so
# no SysML2/KerML resolution ever relies on the ns=None path. (The
# ModelingLanguageService passes ns through to the routed provider, so an
# explicit ns="SysML2"/"KerML" lookup reaches here intact.)


class KerMLModelingLanguage(ModelingLanguage):
    @property
    def name(self) -> str:
        return "KerML"

    @property
    def toolbox_definition(self) -> ToolboxDefinition:
        return kerml_toolbox_actions

    @property
    def diagram_types(self) -> Iterable[DiagramType]:
        yield from kerml_diagram_types

    @property
    def element_types(self) -> Iterable[ElementCreateInfo]:
        yield from kerml_element_types

    @property
    def model_browser_model(self):
        from gaphor.SysML2.treemodel import TreeModel

        return TreeModel

    def lookup_element(self, name, ns=None):
        if ns == "KerML":
            from gaphor.SysML2 import kerml

            return getattr(kerml, name, None)
        return None


class SysML2ModelingLanguage(ModelingLanguage):
    @property
    def name(self) -> str:
        return "SysML2"

    @property
    def toolbox_definition(self) -> ToolboxDefinition:
        return sysml2_toolbox_actions

    @property
    def diagram_types(self) -> Iterable[DiagramType]:
        yield from sysml2_diagram_types

    @property
    def element_types(self) -> Iterable[ElementCreateInfo]:
        yield from sysml2_element_types

    @property
    def model_browser_model(self):
        from gaphor.SysML2.treemodel import TreeModel

        return TreeModel

    def lookup_element(self, name, ns=None):
        # Everything under gaphor.SysML2 persists in the single "SysML2" runtime
        # namespace, so this resolver spans the SysML user concepts, the KerML
        # kernel, the M1a slice, and the diagram items (projections) -- but only
        # under an explicit ns.
        if ns == "SysML2":
            from gaphor.SysML2 import (
                diagramitems,
                diagramtype,
                kerml,
                kerml_slice,
                sysml2,
            )

            return (
                getattr(sysml2, name, None)
                or getattr(kerml, name, None)
                or getattr(kerml_slice, name, None)
                or getattr(diagramitems, name, None)
                or getattr(diagramtype, name, None)
            )
        return None
