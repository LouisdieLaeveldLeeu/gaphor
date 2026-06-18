"""Property pages for the SysML v2 UI surface."""

from __future__ import annotations

from gi.repository import Gio

from gaphor.core import Transaction
from gaphor.diagram.propertypages import (
    LabelValue,
    PropertyPageBase,
    PropertyPages,
    handler_blocking,
    new_resource_builder,
    unsubscribe_all_on_destroy,
)
from gaphor.SysML2 import kerml
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2 import sysml2

new_builder = new_resource_builder("gaphor.SysML2")


@PropertyPages.register(kerml.Package)
@PropertyPages.register(sysml2.PartDefinition)
@PropertyPages.register(sysml2.PartUsage)
class DeclaredNamePropertyPage(PropertyPageBase):
    """Edit the KerML/SysML declared name."""

    order = 10

    def __init__(
        self,
        subject: kerml.Package | sysml2.PartDefinition | sysml2.PartUsage,
        event_manager,
    ):
        super().__init__()
        self.subject = subject
        self.event_manager = event_manager
        self.watcher = subject.watcher()

    def construct(self):
        builder = new_builder("declared-name-editor")

        entry = builder.get_object("declared-name")
        entry.set_text(self.subject.declaredName or "")

        @handler_blocking(entry, "changed", self._on_declared_name_changed)
        def text_handler(event):
            if (
                event.element is self.subject
                and (event.new_value or "") != entry.get_text()
            ):
                entry.set_text(event.new_value or "")

        self.watcher.watch("declaredName", text_handler)

        return unsubscribe_all_on_destroy(
            builder.get_object("declared-name-editor"), self.watcher
        )

    def _on_declared_name_changed(self, entry):
        with Transaction(self.event_manager, context="editing"):
            self.subject.declaredName = entry.get_text()


@PropertyPages.register(sysml2.PartUsage)
class PartUsageTypePropertyPage(PropertyPageBase):
    """Set the PartDefinition type for a PartUsage."""

    order = 20

    def __init__(self, subject: sysml2.PartUsage, event_manager):
        super().__init__()
        self.subject = subject
        self.event_manager = event_manager

    def construct(self):
        builder = new_builder("part-usage-type-editor")

        dropdown = builder.get_object("part-usage-type")
        model = list_of_part_definitions(self.subject.model)
        dropdown.set_model(model)

        if isinstance(type_ := kk.feature_type(self.subject), sysml2.PartDefinition):
            selected = next(
                (n for n, lv in enumerate(model) if lv.value == type_.id),
                None,
            )
            if selected is not None:
                dropdown.set_selected(selected)

        dropdown.connect("notify::selected", self._on_type_changed)

        return builder.get_object("part-usage-type-editor")

    def _on_type_changed(self, dropdown, _pspec):
        selected = dropdown.get_selected_item()
        with Transaction(self.event_manager, context="editing"):
            if selected and selected.value:
                type_ = self.subject.model.lookup(selected.value)
                assert isinstance(type_, sysml2.PartDefinition)
                kk.set_feature_type(self.subject, type_)
            else:
                kk.set_feature_type(self.subject, None)


def list_of_part_definitions(element_factory) -> Gio.ListStore:
    model = Gio.ListStore.new(LabelValue)
    model.append(LabelValue("", None))
    for part_definition in sorted(
        element_factory.select(sysml2.PartDefinition),
        key=_part_definition_label,
    ):
        label = _part_definition_label(part_definition)
        model.append(LabelValue(label, part_definition.id))
    return model


def _part_definition_label(part_definition: sysml2.PartDefinition) -> str:
    qualified_name = kk.qualified_name(part_definition).lstrip(
        kk.QUALIFIED_NAME_SEPARATOR
    )
    return qualified_name or part_definition.declaredName or type(part_definition).__name__
