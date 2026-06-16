"""Minimal SysML2 modeling language for the M1a generator spike.

This exposes the generated, semantics-free `kerml_slice` module so Gaphor's
storage layer can resolve SysML2 element types by namespace on load. It is
intentionally minimal: M1a only needs element-type lookup for the persist/reload
spike. Toolbox, diagram types, and UI integration come in later milestones.
"""

from __future__ import annotations

from gaphor.abc import ModelingLanguage
from gaphor.SysML2 import kerml_slice


class SysML2ModelingLanguage(ModelingLanguage):
    @property
    def name(self) -> str:
        return "SysML2"

    @property
    def toolbox_definition(self):
        raise ValueError("No toolbox for SysML2 yet (M1a spike).")

    @property
    def diagram_types(self):
        return ()

    @property
    def element_types(self):
        return ()

    @property
    def model_browser_model(self):
        raise ValueError("No model browser model for SysML2 yet (M1a spike).")

    def lookup_element(self, name, ns=None):
        if ns in (None, "SysML2"):
            return getattr(kerml_slice, name, None)
        return None
