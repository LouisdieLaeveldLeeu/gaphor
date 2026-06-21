"""Property pages for the SysML v2 UI surface."""

from __future__ import annotations

from gi.repository import Gio

from gaphor.core import Transaction
from gaphor.i18n import gettext
from gaphor.diagram.propertypages import (
    LabelValue,
    PropertyPageBase,
    PropertyPages,
    handler_blocking,
    new_resource_builder,
    unsubscribe_all_on_destroy,
)
from gaphor.SysML2 import conjugation
from gaphor.SysML2 import constraints
from gaphor.SysML2 import kerml
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2 import mapping
from gaphor.SysML2 import sysml2

_LIBRARY_PREFIX = "library:"

new_builder = new_resource_builder("gaphor.SysML2")


@PropertyPages.register(kerml.Package)
@PropertyPages.register(sysml2.AttributeDefinition)
@PropertyPages.register(sysml2.AttributeUsage)
@PropertyPages.register(sysml2.ActionDefinition)
@PropertyPages.register(sysml2.ActionUsage)
@PropertyPages.register(sysml2.ConstraintDefinition)
@PropertyPages.register(sysml2.ConstraintUsage)
@PropertyPages.register(sysml2.RequirementDefinition)
@PropertyPages.register(sysml2.RequirementUsage)
@PropertyPages.register(sysml2.PortDefinition)
@PropertyPages.register(sysml2.PortUsage)
@PropertyPages.register(sysml2.PartDefinition)
@PropertyPages.register(sysml2.PartUsage)
class DeclaredNamePropertyPage(PropertyPageBase):
    """Edit the KerML/SysML declared name.

    ConnectionDefinition/ConnectionUsage are not registered separately: they
    subclass PartDefinition/PartUsage, so `PropertyPages.find` (isinstance) already
    yields this page for them. Registering them again would show two name editors.
    """

    order = 10

    def __init__(
        self,
        subject: (
            kerml.Package
            | sysml2.AttributeDefinition
            | sysml2.AttributeUsage
            | sysml2.ActionDefinition
            | sysml2.ActionUsage
            | sysml2.ConstraintDefinition
            | sysml2.ConstraintUsage
            | sysml2.RequirementDefinition
            | sysml2.RequirementUsage
            | sysml2.PortDefinition
            | sysml2.PortUsage
            | sysml2.PartDefinition
            | sysml2.PartUsage
        ),
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
@PropertyPages.register(sysml2.AttributeUsage)
@PropertyPages.register(sysml2.ActionUsage)
@PropertyPages.register(sysml2.ConstraintUsage)
@PropertyPages.register(sysml2.PortUsage)
class FeatureDirectionPropertyPage(PropertyPageBase):
    """Set a usage's feature direction (`in` / `out` / `inout`, or undirected).

    Maps to KerML `Feature::direction` (Phase 8b). Registered on the base usage
    classes only: ConnectionUsage (a PartUsage) and RequirementUsage (a
    ConstraintUsage) are matched by `PropertyPages.find` (isinstance), so
    registering them again would show two direction editors. Definitions are
    Classifiers (not Features) and get no direction editor.
    """

    order = 15

    # (label, stored value) -- value is the FeatureDirectionKind string, or None
    # for the undirected (unset) state.
    _CHOICES = (
        ("(undirected)", None),
        ("in", "in"),
        ("out", "out"),
        ("inout", "inout"),
    )

    def __init__(
        self,
        subject: (
            sysml2.PartUsage
            | sysml2.AttributeUsage
            | sysml2.ActionUsage
            | sysml2.ConstraintUsage
            | sysml2.PortUsage
        ),
        event_manager,
    ):
        super().__init__()
        self.subject = subject
        self.event_manager = event_manager

    def construct(self):
        builder = new_builder("feature-direction-editor")

        dropdown = builder.get_object("feature-direction")
        model = Gio.ListStore.new(LabelValue)
        for label, value in self._CHOICES:
            model.append(LabelValue(label, value))
        dropdown.set_model(model)

        current = self.subject.direction
        current_value = str(current) if current is not None else None
        selected = next(
            (n for n, (_, v) in enumerate(self._CHOICES) if v == current_value),
            0,
        )
        dropdown.set_selected(selected)
        dropdown.connect("notify::selected", self._on_direction_changed)

        return builder.get_object("feature-direction-editor")

    def _on_direction_changed(self, dropdown, _pspec):
        selected = dropdown.get_selected_item()
        value = selected.value if selected else None
        with Transaction(self.event_manager, context="editing"):
            self.subject.direction = (
                kerml.FeatureDirectionKind(value) if value is not None else None
            )


@PropertyPages.register(sysml2.PartUsage)
class PartUsageTypePropertyPage(PropertyPageBase):
    """Set the PartDefinition type for a PartUsage."""

    order = 20

    def __init__(self, subject: sysml2.PartUsage, event_manager):
        super().__init__()
        self.subject = subject
        self.event_manager = event_manager

    def construct(self):
        # ConnectionUsage subclasses PartUsage, so this page is also matched for
        # it by isinstance. A ConnectionUsage is typed by a ConnectionDefinition,
        # not a PartDefinition, and gets its own ConnectionUsageTypePropertyPage,
        # so this page defers (returns no widget) to avoid a second, wrong-kind
        # dropdown on a connection.
        if isinstance(self.subject, sysml2.ConnectionUsage):
            return None

        builder = new_builder("part-usage-type-editor")

        dropdown = builder.get_object("part-usage-type")
        model = list_of_definitions(self.subject.model, sysml2.PartDefinition)
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


@PropertyPages.register(sysml2.AttributeUsage)
class AttributeUsageTypePropertyPage(PropertyPageBase):
    """Set the type for an AttributeUsage: an in-model AttributeDefinition or a
    read-only standard-library value type (Real, String, ...)."""

    order = 20

    def __init__(self, subject: sysml2.AttributeUsage, event_manager):
        super().__init__()
        self.subject = subject
        self.event_manager = event_manager

    def construct(self):
        builder = new_builder("attribute-usage-type-editor")

        dropdown = builder.get_object("attribute-usage-type")
        model = list_of_definitions(self.subject.model, sysml2.AttributeDefinition)
        for name in mapping.library_value_type_names():
            model.append(LabelValue(f"{name} (library)", f"{_LIBRARY_PREFIX}{name}"))
        dropdown.set_model(model)

        selected_value = self._current_value()
        if selected_value is not None:
            selected = next(
                (n for n, lv in enumerate(model) if lv.value == selected_value),
                None,
            )
            if selected is not None:
                dropdown.set_selected(selected)

        dropdown.connect("notify::selected", self._on_type_changed)

        return builder.get_object("attribute-usage-type-editor")

    def _current_value(self) -> str | None:
        type_ = kk.feature_type(self.subject)
        if isinstance(type_, sysml2.AttributeDefinition):
            return type_.id
        # A bare DataType is a library value-type proxy.
        if type(type_) is kerml.DataType:
            return f"{_LIBRARY_PREFIX}{type_.declaredName}"
        return None

    def _on_type_changed(self, dropdown, _pspec):
        selected = dropdown.get_selected_item()
        with Transaction(self.event_manager, context="editing"):
            if selected and selected.value:
                value = selected.value
                if value.startswith(_LIBRARY_PREFIX):
                    mapping.set_attribute_library_type(
                        self.subject, value[len(_LIBRARY_PREFIX):]
                    )
                else:
                    type_ = self.subject.model.lookup(value)
                    assert isinstance(type_, sysml2.AttributeDefinition)
                    kk.set_feature_type(self.subject, type_)
            else:
                kk.set_feature_type(self.subject, None)


@PropertyPages.register(sysml2.ActionUsage)
class ActionUsageTypePropertyPage(PropertyPageBase):
    """Set the ActionDefinition type for an ActionUsage."""

    order = 20

    def __init__(self, subject: sysml2.ActionUsage, event_manager):
        super().__init__()
        self.subject = subject
        self.event_manager = event_manager

    def construct(self):
        builder = new_builder("action-usage-type-editor")

        dropdown = builder.get_object("action-usage-type")
        model = list_of_definitions(self.subject.model, sysml2.ActionDefinition)
        dropdown.set_model(model)

        if isinstance(type_ := kk.feature_type(self.subject), sysml2.ActionDefinition):
            selected = next(
                (n for n, lv in enumerate(model) if lv.value == type_.id),
                None,
            )
            if selected is not None:
                dropdown.set_selected(selected)

        dropdown.connect("notify::selected", self._on_type_changed)

        return builder.get_object("action-usage-type-editor")

    def _on_type_changed(self, dropdown, _pspec):
        selected = dropdown.get_selected_item()
        with Transaction(self.event_manager, context="editing"):
            if selected and selected.value:
                type_ = self.subject.model.lookup(selected.value)
                assert isinstance(type_, sysml2.ActionDefinition)
                kk.set_feature_type(self.subject, type_)
            else:
                kk.set_feature_type(self.subject, None)


@PropertyPages.register(sysml2.ConstraintUsage)
class ConstraintRequirementTypePropertyPage(PropertyPageBase):
    """Set the definition type for a Constraint or Requirement usage.

    RequirementUsage is a ConstraintUsage subclass, so a single page (registered
    on ConstraintUsage, matched for both by isinstance) handles both -- it would
    be wrong to register two pages and show a RequirementUsage two dropdowns. The
    definition kind is chosen from the subject's own type: a RequirementUsage is
    typed by a RequirementDefinition, any other ConstraintUsage by a
    ConstraintDefinition.
    """

    order = 20

    def __init__(self, subject: sysml2.ConstraintUsage, event_manager):
        super().__init__()
        self.subject = subject
        self.event_manager = event_manager
        self._definition_type: type[
            sysml2.ConstraintDefinition | sysml2.RequirementDefinition
        ] = (
            sysml2.RequirementDefinition
            if isinstance(subject, sysml2.RequirementUsage)
            else sysml2.ConstraintDefinition
        )

    def construct(self):
        builder = new_builder("constraint-usage-type-editor")

        dropdown = builder.get_object("constraint-usage-type")
        label = builder.get_object("constraint-usage-type-label")
        label.set_text(
            gettext("Requirement Definition Type")
            if self._definition_type is sysml2.RequirementDefinition
            else gettext("Constraint Definition Type")
        )
        model = list_of_definitions(self.subject.model, self._definition_type)
        dropdown.set_model(model)

        if isinstance(type_ := kk.feature_type(self.subject), self._definition_type):
            selected = next(
                (n for n, lv in enumerate(model) if lv.value == type_.id),
                None,
            )
            if selected is not None:
                dropdown.set_selected(selected)

        dropdown.connect("notify::selected", self._on_type_changed)

        return builder.get_object("constraint-usage-type-editor")

    def _on_type_changed(self, dropdown, _pspec):
        selected = dropdown.get_selected_item()
        with Transaction(self.event_manager, context="editing"):
            if selected and selected.value:
                type_ = self.subject.model.lookup(selected.value)
                assert isinstance(type_, self._definition_type)
                kk.set_feature_type(self.subject, type_)
            else:
                kk.set_feature_type(self.subject, None)


@PropertyPages.register(sysml2.PortUsage)
class PortUsageTypePropertyPage(PropertyPageBase):
    """Set the PortDefinition type for a PortUsage, optionally conjugated (`~`).

    A conjugated port (`port p : ~Fuel`) is typed by the CONJUGATE of the chosen
    PortDefinition through a ConjugatedPortTyping (see `conjugation`); unchecking
    conjugation re-types the port by the definition directly. The dropdown lists
    plain PortDefinitions only (the exact-kind filter excludes the implicit
    conjugate), so a conjugated typing always names its original definition.
    """

    order = 20

    def __init__(self, subject: sysml2.PortUsage, event_manager):
        super().__init__()
        self.subject = subject
        self.event_manager = event_manager

    def construct(self):
        builder = new_builder("port-usage-type-editor")

        dropdown = builder.get_object("port-usage-type")
        model = list_of_definitions(self.subject.model, sysml2.PortDefinition)
        dropdown.set_model(model)
        conjugate_toggle = builder.get_object("port-usage-conjugated")

        # A conjugated typing names its ORIGINAL definition; a plain typing names
        # the definition directly. Preselect by whichever applies.
        is_conjugated = conjugation.conjugated_typing(self.subject) is not None
        if is_conjugated:
            current = conjugation.conjugated_type_name(self.subject)
        else:
            current = kk.feature_type(self.subject)
            if not isinstance(current, sysml2.PortDefinition):
                current = None

        if current is not None:
            selected = next(
                (n for n, lv in enumerate(model) if lv.value == current.id),
                None,
            )
            if selected is not None:
                dropdown.set_selected(selected)
        conjugate_toggle.set_active(is_conjugated)

        # Connect AFTER setting the initial state so it does not self-trigger.
        dropdown.connect("notify::selected", self._on_changed)
        conjugate_toggle.connect("notify::active", self._on_changed)
        self._dropdown = dropdown
        self._conjugate_toggle = conjugate_toggle

        return builder.get_object("port-usage-type-editor")

    def _on_changed(self, _widget, _pspec):
        selected = self._dropdown.get_selected_item()
        conjugated = self._conjugate_toggle.get_active()
        with Transaction(self.event_manager, context="editing"):
            if selected and selected.value:
                type_ = self.subject.model.lookup(selected.value)
                assert isinstance(type_, sysml2.PortDefinition)
                if conjugated:
                    conjugation.set_conjugated_port_type(self.subject, type_)
                else:
                    kk.set_feature_type(self.subject, type_)
            else:
                # No type selected -> no typing, conjugated or not.
                kk.set_feature_type(self.subject, None)


@PropertyPages.register(sysml2.ConnectionUsage)
class ConnectionUsageTypePropertyPage(PropertyPageBase):
    """Set the ConnectionDefinition type for a ConnectionUsage.

    ConnectionUsage subclasses PartUsage, so PartUsageTypePropertyPage also
    matches it; that page defers (returns no widget) for a ConnectionUsage, and
    this page provides the correct ConnectionDefinition dropdown -- so a
    ConnectionUsage gets exactly one type editor, of the right kind.
    """

    order = 20

    def __init__(self, subject: sysml2.ConnectionUsage, event_manager):
        super().__init__()
        self.subject = subject
        self.event_manager = event_manager

    def construct(self):
        # InterfaceUsage subclasses ConnectionUsage, so this page is also matched
        # for it by isinstance. An InterfaceUsage is typed by an
        # InterfaceDefinition, not a ConnectionDefinition, and gets its own
        # InterfaceUsageTypePropertyPage, so this page defers (returns no widget)
        # to avoid a second, wrong-kind dropdown on an interface.
        if isinstance(self.subject, sysml2.InterfaceUsage):
            return None

        builder = new_builder("connection-usage-type-editor")

        dropdown = builder.get_object("connection-usage-type")
        model = list_of_definitions(self.subject.model, sysml2.ConnectionDefinition)
        dropdown.set_model(model)

        if isinstance(
            type_ := kk.feature_type(self.subject), sysml2.ConnectionDefinition
        ):
            selected = next(
                (n for n, lv in enumerate(model) if lv.value == type_.id),
                None,
            )
            if selected is not None:
                dropdown.set_selected(selected)

        dropdown.connect("notify::selected", self._on_type_changed)

        return builder.get_object("connection-usage-type-editor")

    def _on_type_changed(self, dropdown, _pspec):
        selected = dropdown.get_selected_item()
        with Transaction(self.event_manager, context="editing"):
            if selected and selected.value:
                type_ = self.subject.model.lookup(selected.value)
                assert isinstance(type_, sysml2.ConnectionDefinition)
                kk.set_feature_type(self.subject, type_)
            else:
                kk.set_feature_type(self.subject, None)


@PropertyPages.register(sysml2.ConstraintDefinition)
@PropertyPages.register(sysml2.ConstraintUsage)
class ConstraintBodyPropertyPage(PropertyPageBase):
    """Edit a constraint's preserved body text (Phase 6a).

    The body is opaque text stored as a `TextualRepresentation` (see
    `constraints`); clearing the field removes it. Defers for requirements
    (RequirementDefinition/Usage subclass the constraint classes, so they match by
    isinstance): requirement bodies are Phase 6b and the export path does not yet
    emit them, so a body must not be authorable on a requirement here.
    """

    order = 30

    def __init__(
        self,
        subject: sysml2.ConstraintDefinition | sysml2.ConstraintUsage,
        event_manager,
    ):
        super().__init__()
        self.subject = subject
        self.event_manager = event_manager

    def construct(self):
        if isinstance(
            self.subject,
            (sysml2.RequirementDefinition, sysml2.RequirementUsage),
        ):
            return None

        builder = new_builder("constraint-body-editor")
        entry = builder.get_object("constraint-body")
        entry.set_text(constraints.body_text(self.subject) or "")
        entry.connect("changed", self._on_body_changed)
        return builder.get_object("constraint-body-editor")

    def _on_body_changed(self, entry):
        with Transaction(self.event_manager, context="editing"):
            # The body is preserved VERBATIM (whitespace kept); only a
            # whitespace-only field clears it (None) rather than storing an empty
            # body.
            text = entry.get_text()
            constraints.set_body_text(self.subject, text if text.strip() else None)


@PropertyPages.register(sysml2.InterfaceUsage)
class InterfaceUsageTypePropertyPage(PropertyPageBase):
    """Set the InterfaceDefinition type for an InterfaceUsage.

    InterfaceUsage subclasses ConnectionUsage (and PartUsage), so both their type
    pages also match it; each defers for an InterfaceUsage, and this page provides
    the InterfaceDefinition dropdown -- so an InterfaceUsage gets exactly one type
    editor, of the right kind. The list is exact-kind, so it offers only
    InterfaceDefinitions (never plain ConnectionDefinitions).
    """

    order = 20

    def __init__(self, subject: sysml2.InterfaceUsage, event_manager):
        super().__init__()
        self.subject = subject
        self.event_manager = event_manager

    def construct(self):
        builder = new_builder("interface-usage-type-editor")

        dropdown = builder.get_object("interface-usage-type")
        model = list_of_definitions(self.subject.model, sysml2.InterfaceDefinition)
        dropdown.set_model(model)

        if isinstance(
            type_ := kk.feature_type(self.subject), sysml2.InterfaceDefinition
        ):
            selected = next(
                (n for n, lv in enumerate(model) if lv.value == type_.id),
                None,
            )
            if selected is not None:
                dropdown.set_selected(selected)

        dropdown.connect("notify::selected", self._on_type_changed)

        return builder.get_object("interface-usage-type-editor")

    def _on_type_changed(self, dropdown, _pspec):
        selected = dropdown.get_selected_item()
        with Transaction(self.event_manager, context="editing"):
            if selected and selected.value:
                type_ = self.subject.model.lookup(selected.value)
                assert isinstance(type_, sysml2.InterfaceDefinition)
                kk.set_feature_type(self.subject, type_)
            else:
                kk.set_feature_type(self.subject, None)


def list_of_definitions(
    element_factory,
    definition_type: type[
        sysml2.PartDefinition
        | sysml2.AttributeDefinition
        | sysml2.ActionDefinition
        | sysml2.ConstraintDefinition
        | sysml2.RequirementDefinition
        | sysml2.PortDefinition
        | sysml2.ConnectionDefinition
    ],
) -> Gio.ListStore:
    # Exact-kind filter (type(d) is definition_type), not isinstance: a usage is
    # typed by exactly its definition kind, so a ConstraintUsage's dropdown must
    # list ConstraintDefinitions only and NOT RequirementDefinitions (which
    # subclass ConstraintDefinition). This mirrors the mapper's typing contract,
    # so the UI cannot create a cross-kind mismatch the importer would reject.
    model = Gio.ListStore.new(LabelValue)
    model.append(LabelValue("", None))
    definitions = [
        d
        for d in element_factory.select(definition_type)
        if type(d) is definition_type
    ]
    for definition in sorted(definitions, key=_definition_label):
        label = _definition_label(definition)
        model.append(LabelValue(label, definition.id))
    return model


def _definition_label(
    definition: sysml2.PartDefinition
    | sysml2.AttributeDefinition
    | sysml2.ActionDefinition
    | sysml2.ConstraintDefinition
    | sysml2.RequirementDefinition
    | sysml2.PortDefinition
    | sysml2.ConnectionDefinition,
) -> str:
    qualified_name = kk.qualified_name(definition).lstrip(kk.QUALIFIED_NAME_SEPARATOR)
    return qualified_name or definition.declaredName or type(definition).__name__
