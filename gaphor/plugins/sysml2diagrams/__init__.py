"""SysML v2 diagram-synthesis and browser-grooming actions (Phase 13).

Two Tools-menu actions on top of the GTK-free cores:

- **Synthesize SysML2 Diagrams** -- runs `synthesis.synthesize_diagrams` on the
  current model's root namespace, in one undoable transaction. Idempotent: re-running
  never duplicates an already-synthesized diagram.
- **Show Internal SysML2 Elements** -- a toggle that flips the model browser between
  the groomed view (user concepts only) and the internal/debug view (also relationship
  plumbing, proxies, and helper elements), via `TreeModel.set_show_internal`.

The synthesis/grooming logic lives in `gaphor.SysML2.synthesis` / `.treemodel` and is
unit-tested headless; this service is the thin GUI binding.
"""

from __future__ import annotations

from gaphor.abc import ActionProvider, Service
from gaphor.core import action, gettext
from gaphor.core.modeling import Diagram
from gaphor.event import Notification
from gaphor.SysML2 import kerml
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.synthesis import synthesize_diagrams
from gaphor.SysML2.treemodel import TreeModel
from gaphor.transaction import Transaction


class SysML2DiagramSynthesis(Service, ActionProvider):
    """Synthesize initial SysML2 diagrams and groom the model browser from the UI."""

    def __init__(self, event_manager, element_factory, tools_menu=None):
        self.event_manager = event_manager
        self.element_factory = element_factory
        self.tools_menu = tools_menu
        if tools_menu:
            tools_menu.add_actions(self)

    def shutdown(self):
        if self.tools_menu:
            self.tools_menu.remove_actions(self)

    # --- GTK-free cores (unit-tested headless) -------------------------------

    def model_root(self) -> kerml.Namespace | None:
        """The single bare SysML2 root namespace of the current model, or None."""
        return next(
            (
                ns
                for ns in self.element_factory.select(kerml.Namespace)
                if type(ns) is kerml.Namespace and kk.owning_namespace(ns) is None
            ),
            None,
        )

    def synthesize(self) -> list[Diagram]:
        """Synthesize diagrams for the current model in one transaction (idempotent)."""
        root = self.model_root()
        if root is None:
            return []
        with Transaction(self.event_manager):
            return synthesize_diagrams(root, event_manager=self.event_manager)

    # --- actions -------------------------------------------------------------

    @action(
        name="sysml2-synthesize-diagrams",
        label=gettext("Synthesize SysML2 Diagrams"),
    )
    def synthesize_action(self):
        diagrams = self.synthesize()
        self.event_manager.handle(
            Notification(
                gettext("Synthesized {count} SysML2 diagram(s).").format(
                    count=len(diagrams)
                )
            )
        )

    @action(
        name="sysml2-show-internal-elements",
        label=gettext("Show Internal SysML2 Elements"),
        state=False,
    )
    def show_internal_action(self, active: bool):
        TreeModel.set_show_internal(active)
