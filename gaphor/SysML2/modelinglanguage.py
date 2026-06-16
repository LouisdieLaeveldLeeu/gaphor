"""Minimal SysML2 modeling language.

Exposes the generated, semantics-free element classes so Gaphor's storage layer
can resolve SysML2 element types by namespace on load. It looks up first in the
M1b KerML kernel (`kerml`), then in the M1a feasibility slice (`kerml_slice`).
It is intentionally minimal: it only provides element-type lookup. Toolbox,
diagram types, and UI integration come in later milestones.
"""

from __future__ import annotations

from gaphor.abc import ModelingLanguage
from gaphor.SysML2 import kerml, kerml_slice


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
        if ns in (None, "SysML2"):
            return getattr(kerml, name, None) or getattr(kerml_slice, name, None)
        return None
