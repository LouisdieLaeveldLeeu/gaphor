"""SysML v2 modeling languages.

Two registered modeling languages back the generated layers so Gaphor's storage
and the code generator's supermodel resolution can look up element types by
namespace:

- `KerML` -> the generated KerML kernel (`kerml.py`). It is the supermodel the
  SysML2 layer generalizes, exactly as Core is the supermodel for UML.
- `SysML2` -> the generated SysML user concepts (`sysml2.py`), falling back to
  the M1a feasibility slice for its throwaway `Element`.

Both are intentionally minimal: element-type lookup only. Toolbox, diagram
types, and UI integration come in later milestones.
"""

from __future__ import annotations

from gaphor.abc import ModelingLanguage


class KerMLModelingLanguage(ModelingLanguage):
    @property
    def name(self) -> str:
        return "KerML"

    @property
    def toolbox_definition(self):
        raise ValueError("No toolbox for KerML yet.")

    @property
    def diagram_types(self):
        return ()

    @property
    def element_types(self):
        return ()

    @property
    def model_browser_model(self):
        raise ValueError("No model browser model for KerML yet.")

    def lookup_element(self, name, ns=None):
        if ns in (None, "KerML"):
            from gaphor.SysML2 import kerml

            return getattr(kerml, name, None)
        return None


class SysML2ModelingLanguage(ModelingLanguage):
    @property
    def name(self) -> str:
        return "SysML2"

    @property
    def toolbox_definition(self):
        raise ValueError("No toolbox for SysML2 yet.")

    @property
    def diagram_types(self):
        return ()

    @property
    def element_types(self):
        return ()

    @property
    def model_browser_model(self):
        raise ValueError("No model browser model for SysML2 yet.")

    def lookup_element(self, name, ns=None):
        # Everything under the gaphor.SysML2 package persists in the single
        # "SysML2" runtime namespace (its `__modeling_language__`), so this
        # resolver spans the SysML user concepts, the KerML kernel, and the M1a
        # slice. (The "KerML" supermodel name is a code-generation concern, not a
        # persistence namespace.)
        if ns in (None, "SysML2"):
            from gaphor.SysML2 import kerml, kerml_slice, sysml2

            return (
                getattr(sysml2, name, None)
                or getattr(kerml, name, None)
                or getattr(kerml_slice, name, None)
            )
        return None
