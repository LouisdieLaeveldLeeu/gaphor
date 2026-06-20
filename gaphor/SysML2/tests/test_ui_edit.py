"""Phase B UI-edit surface for PartDefinition and PartUsage."""

from __future__ import annotations

import pytest

from gaphor.diagram.diagramtoolbox import get_tool_def
from gaphor.diagram.propertypages import PropertyPages
from gaphor.diagram.tests.fixtures import find
from gaphor.SysML2 import kerml, kerml_kernel as kk, sysml2
from gaphor.SysML2.diagramitems import (
    ActionDefinitionItem,
    ActionUsageItem,
    AttributeDefinitionItem,
    AttributeUsageItem,
    ConnectionDefinitionItem,
    ConnectionUsageItem,
    ConstraintDefinitionItem,
    ConstraintUsageItem,
    PackageItem,
    PartDefinitionItem,
    PartUsageItem,
    PortDefinitionItem,
    PortUsageItem,
    RequirementDefinitionItem,
    RequirementUsageItem,
)
from gaphor.SysML2.diagramtype import SysML2Diagram
from gaphor.SysML2.modelinglanguage import SysML2ModelingLanguage
from gaphor.SysML2.propertypages import (
    ActionUsageTypePropertyPage,
    AttributeUsageTypePropertyPage,
    ConnectionUsageTypePropertyPage,
    ConstraintRequirementTypePropertyPage,
    DeclaredNamePropertyPage,
    PartUsageTypePropertyPage,
    PortUsageTypePropertyPage,
)

# Importing the module registers the property pages through decorators.
import gaphor.SysML2.uicomponents  # noqa: F401, E402


def _toolbox_item(tool_id: str, diagram):
    tool = get_tool_def(SysML2ModelingLanguage(), tool_id)
    assert tool.item_factory
    return tool.item_factory(diagram, None)


def test_part_definition_toolbox_entry_creates_semantic_element_and_projection(
    element_factory,
):
    diagram = element_factory.create(SysML2Diagram)

    item = _toolbox_item("toolbox-part-definition", diagram)

    assert isinstance(item, PartDefinitionItem)
    assert isinstance(item.subject, sysml2.PartDefinition)
    assert item.subject.declaredName == "PartDefinition"
    assert item in diagram.ownedPresentation
    assert item in item.subject.presentation


def test_package_toolbox_entry_creates_semantic_element_and_projection(
    element_factory,
):
    diagram = element_factory.create(SysML2Diagram)

    item = _toolbox_item("toolbox-package", diagram)

    assert isinstance(item, PackageItem)
    assert isinstance(item.subject, kerml.Package)
    assert item.subject.declaredName == "Package"
    assert item in diagram.ownedPresentation
    assert item in item.subject.presentation


def test_part_usage_toolbox_entry_creates_semantic_element_and_projection(
    element_factory,
):
    diagram = element_factory.create(SysML2Diagram)

    item = _toolbox_item("toolbox-part-usage", diagram)

    assert isinstance(item, PartUsageItem)
    assert isinstance(item.subject, sysml2.PartUsage)
    assert item.subject.declaredName == "partUsage"
    assert item in diagram.ownedPresentation
    assert item in item.subject.presentation


def test_attribute_definition_toolbox_entry_creates_semantic_element_and_projection(
    element_factory,
):
    diagram = element_factory.create(SysML2Diagram)

    item = _toolbox_item("toolbox-attribute-definition", diagram)

    assert isinstance(item, AttributeDefinitionItem)
    assert isinstance(item.subject, sysml2.AttributeDefinition)
    assert item.subject.declaredName == "AttributeDefinition"
    assert item in diagram.ownedPresentation
    assert item in item.subject.presentation


def test_attribute_usage_toolbox_entry_creates_semantic_element_and_projection(
    element_factory,
):
    diagram = element_factory.create(SysML2Diagram)

    item = _toolbox_item("toolbox-attribute-usage", diagram)

    assert isinstance(item, AttributeUsageItem)
    assert isinstance(item.subject, sysml2.AttributeUsage)
    assert item.subject.declaredName == "attributeUsage"
    assert item in diagram.ownedPresentation
    assert item in item.subject.presentation


def test_action_definition_toolbox_entry_creates_semantic_element_and_projection(
    element_factory,
):
    diagram = element_factory.create(SysML2Diagram)

    item = _toolbox_item("toolbox-action-definition", diagram)

    assert isinstance(item, ActionDefinitionItem)
    assert isinstance(item.subject, sysml2.ActionDefinition)
    assert item.subject.declaredName == "ActionDefinition"
    assert item in diagram.ownedPresentation
    assert item in item.subject.presentation


def test_action_usage_toolbox_entry_creates_semantic_element_and_projection(
    element_factory,
):
    diagram = element_factory.create(SysML2Diagram)

    item = _toolbox_item("toolbox-action-usage", diagram)

    assert isinstance(item, ActionUsageItem)
    assert isinstance(item.subject, sysml2.ActionUsage)
    assert item.subject.declaredName == "actionUsage"
    assert item in diagram.ownedPresentation
    assert item in item.subject.presentation


@pytest.mark.parametrize(
    ("tool_id", "item_cls", "element_cls", "default_name"),
    [
        (
            "toolbox-constraint-definition",
            ConstraintDefinitionItem,
            sysml2.ConstraintDefinition,
            "ConstraintDefinition",
        ),
        (
            "toolbox-constraint-usage",
            ConstraintUsageItem,
            sysml2.ConstraintUsage,
            "constraintUsage",
        ),
        (
            "toolbox-requirement-definition",
            RequirementDefinitionItem,
            sysml2.RequirementDefinition,
            "RequirementDefinition",
        ),
        (
            "toolbox-requirement-usage",
            RequirementUsageItem,
            sysml2.RequirementUsage,
            "requirementUsage",
        ),
    ],
)
def test_requirement_constraint_toolbox_entries_create_element_and_projection(
    element_factory, tool_id, item_cls, element_cls, default_name
):
    diagram = element_factory.create(SysML2Diagram)

    item = _toolbox_item(tool_id, diagram)

    assert isinstance(item, item_cls)
    assert isinstance(item.subject, element_cls)
    assert item.subject.declaredName == default_name
    assert item in diagram.ownedPresentation
    assert item in item.subject.presentation


@pytest.mark.parametrize(
    ("tool_id", "item_cls", "element_cls", "default_name"),
    [
        (
            "toolbox-port-definition",
            PortDefinitionItem,
            sysml2.PortDefinition,
            "PortDefinition",
        ),
        (
            "toolbox-port-usage",
            PortUsageItem,
            sysml2.PortUsage,
            "portUsage",
        ),
    ],
)
def test_port_toolbox_entries_create_element_and_projection(
    element_factory, tool_id, item_cls, element_cls, default_name
):
    diagram = element_factory.create(SysML2Diagram)

    item = _toolbox_item(tool_id, diagram)

    assert isinstance(item, item_cls)
    assert isinstance(item.subject, element_cls)
    assert item.subject.declaredName == default_name
    assert item in diagram.ownedPresentation
    assert item in item.subject.presentation


@pytest.mark.parametrize(
    ("tool_id", "item_cls", "element_cls", "default_name"),
    [
        (
            "toolbox-connection-definition",
            ConnectionDefinitionItem,
            sysml2.ConnectionDefinition,
            "ConnectionDefinition",
        ),
        (
            "toolbox-connection-usage",
            ConnectionUsageItem,
            sysml2.ConnectionUsage,
            "connectionUsage",
        ),
    ],
)
def test_connection_toolbox_entries_create_element_and_projection(
    element_factory, tool_id, item_cls, element_cls, default_name
):
    diagram = element_factory.create(SysML2Diagram)

    item = _toolbox_item(tool_id, diagram)

    # ConnectionUsage subclasses PartUsage; the tool must create exactly the
    # connection item/element, not the part one.
    assert type(item) is item_cls
    assert type(item.subject) is element_cls
    assert item.subject.declaredName == default_name
    assert item in diagram.ownedPresentation
    assert item in item.subject.presentation


def test_property_pages_are_registered_for_part_constructs(element_factory):
    package = element_factory.create(kerml.Package)
    attribute_definition = element_factory.create(sysml2.AttributeDefinition)
    attribute_usage = element_factory.create(sysml2.AttributeUsage)
    action_definition = element_factory.create(sysml2.ActionDefinition)
    action_usage = element_factory.create(sysml2.ActionUsage)
    constraint_definition = element_factory.create(sysml2.ConstraintDefinition)
    constraint_usage = element_factory.create(sysml2.ConstraintUsage)
    requirement_definition = element_factory.create(sysml2.RequirementDefinition)
    requirement_usage = element_factory.create(sysml2.RequirementUsage)
    port_definition = element_factory.create(sysml2.PortDefinition)
    port_usage = element_factory.create(sysml2.PortUsage)
    connection_definition = element_factory.create(sysml2.ConnectionDefinition)
    connection_usage = element_factory.create(sysml2.ConnectionUsage)
    part_definition = element_factory.create(sysml2.PartDefinition)
    part_usage = element_factory.create(sysml2.PartUsage)

    package_pages = set(PropertyPages.find(package))
    attribute_definition_pages = set(PropertyPages.find(attribute_definition))
    attribute_usage_pages = set(PropertyPages.find(attribute_usage))
    action_definition_pages = set(PropertyPages.find(action_definition))
    action_usage_pages = set(PropertyPages.find(action_usage))
    constraint_definition_pages = set(PropertyPages.find(constraint_definition))
    constraint_usage_pages = set(PropertyPages.find(constraint_usage))
    requirement_definition_pages = set(PropertyPages.find(requirement_definition))
    requirement_usage_pages = set(PropertyPages.find(requirement_usage))
    port_definition_pages = set(PropertyPages.find(port_definition))
    port_usage_pages = set(PropertyPages.find(port_usage))
    connection_definition_pages = set(PropertyPages.find(connection_definition))
    connection_usage_pages = set(PropertyPages.find(connection_usage))
    definition_pages = set(PropertyPages.find(part_definition))
    usage_pages = set(PropertyPages.find(part_usage))

    assert DeclaredNamePropertyPage in package_pages
    assert DeclaredNamePropertyPage in attribute_definition_pages
    assert DeclaredNamePropertyPage in attribute_usage_pages
    assert DeclaredNamePropertyPage in action_definition_pages
    assert DeclaredNamePropertyPage in action_usage_pages
    assert DeclaredNamePropertyPage in constraint_definition_pages
    assert DeclaredNamePropertyPage in constraint_usage_pages
    assert DeclaredNamePropertyPage in requirement_definition_pages
    assert DeclaredNamePropertyPage in requirement_usage_pages
    assert DeclaredNamePropertyPage in port_definition_pages
    assert DeclaredNamePropertyPage in port_usage_pages
    assert DeclaredNamePropertyPage in connection_definition_pages
    assert DeclaredNamePropertyPage in connection_usage_pages
    assert DeclaredNamePropertyPage in definition_pages
    assert DeclaredNamePropertyPage in usage_pages
    # ConnectionUsage subclasses PartUsage, but DeclaredNamePropertyPage is
    # registered only on the part classes (not re-registered for connection), so
    # find yields it exactly once -- no duplicate name editor.
    assert (
        sum(
            1
            for p in PropertyPages.find(connection_usage)
            if p is DeclaredNamePropertyPage
        )
        == 1
    )
    # ConnectionUsage gets its own type page, NOT the constraint/requirement one.
    assert ConnectionUsageTypePropertyPage in connection_usage_pages
    assert ConnectionUsageTypePropertyPage not in connection_definition_pages
    assert ConnectionUsageTypePropertyPage not in usage_pages
    assert ConnectionUsageTypePropertyPage not in port_usage_pages
    assert AttributeUsageTypePropertyPage in attribute_usage_pages
    assert AttributeUsageTypePropertyPage not in attribute_definition_pages
    assert AttributeUsageTypePropertyPage not in usage_pages
    assert ActionUsageTypePropertyPage in action_usage_pages
    assert ActionUsageTypePropertyPage not in action_definition_pages
    assert ActionUsageTypePropertyPage not in usage_pages
    assert ActionUsageTypePropertyPage not in attribute_usage_pages
    # One type page covers both constraint and requirement usages (the latter is
    # a ConstraintUsage subclass): a RequirementUsage must NOT get two dropdowns.
    assert ConstraintRequirementTypePropertyPage in constraint_usage_pages
    assert ConstraintRequirementTypePropertyPage in requirement_usage_pages
    assert ConstraintRequirementTypePropertyPage not in constraint_definition_pages
    assert ConstraintRequirementTypePropertyPage not in requirement_definition_pages
    assert ConstraintRequirementTypePropertyPage not in usage_pages
    type_pages_for_requirement = [
        p
        for p in PropertyPages.find(requirement_usage)
        if p is ConstraintRequirementTypePropertyPage
    ]
    assert len(type_pages_for_requirement) == 1
    assert PortUsageTypePropertyPage in port_usage_pages
    assert PortUsageTypePropertyPage not in port_definition_pages
    assert PortUsageTypePropertyPage not in usage_pages
    assert PortUsageTypePropertyPage not in constraint_usage_pages
    assert ConstraintRequirementTypePropertyPage not in port_usage_pages
    assert PartUsageTypePropertyPage in usage_pages
    assert PartUsageTypePropertyPage not in definition_pages
    assert PartUsageTypePropertyPage not in attribute_usage_pages
    assert PartUsageTypePropertyPage not in action_usage_pages
    assert PartUsageTypePropertyPage not in requirement_usage_pages
    assert PartUsageTypePropertyPage not in port_usage_pages


def test_declared_name_property_page_renames_part_definition(
    element_factory,
    event_manager,
):
    part_definition = element_factory.create(sysml2.PartDefinition)
    property_page = DeclaredNamePropertyPage(part_definition, event_manager)

    widget = property_page.construct()
    entry = find(widget, "declared-name")
    entry.set_text("Engine")

    assert part_definition.declaredName == "Engine"


def test_declared_name_property_page_renames_package(
    element_factory,
    event_manager,
):
    package = element_factory.create(kerml.Package)
    property_page = DeclaredNamePropertyPage(package, event_manager)

    widget = property_page.construct()
    entry = find(widget, "declared-name")
    entry.set_text("Vehicles")

    assert package.declaredName == "Vehicles"


def test_declared_name_property_page_renames_attribute_definition(
    element_factory,
    event_manager,
):
    attribute_definition = element_factory.create(sysml2.AttributeDefinition)
    property_page = DeclaredNamePropertyPage(attribute_definition, event_manager)

    widget = property_page.construct()
    entry = find(widget, "declared-name")
    entry.set_text("Mass")

    assert attribute_definition.declaredName == "Mass"


def test_declared_name_property_page_renames_attribute_usage(
    element_factory,
    event_manager,
):
    attribute_usage = element_factory.create(sysml2.AttributeUsage)
    property_page = DeclaredNamePropertyPage(attribute_usage, event_manager)

    widget = property_page.construct()
    entry = find(widget, "declared-name")
    entry.set_text("m")

    assert attribute_usage.declaredName == "m"


def test_declared_name_property_page_renames_action_definition(
    element_factory,
    event_manager,
):
    action_definition = element_factory.create(sysml2.ActionDefinition)
    property_page = DeclaredNamePropertyPage(action_definition, event_manager)

    widget = property_page.construct()
    entry = find(widget, "declared-name")
    entry.set_text("Brake")

    assert action_definition.declaredName == "Brake"


def test_declared_name_property_page_renames_action_usage(
    element_factory,
    event_manager,
):
    action_usage = element_factory.create(sysml2.ActionUsage)
    property_page = DeclaredNamePropertyPage(action_usage, event_manager)

    widget = property_page.construct()
    entry = find(widget, "declared-name")
    entry.set_text("emergencyBrake")

    assert action_usage.declaredName == "emergencyBrake"


@pytest.mark.parametrize(
    ("element_cls", "new_name"),
    [
        (sysml2.ConstraintDefinition, "Limit"),
        (sysml2.ConstraintUsage, "c"),
        (sysml2.RequirementDefinition, "MassReq"),
        (sysml2.RequirementUsage, "r"),
    ],
)
def test_declared_name_property_page_renames_requirement_constraint(
    element_factory, event_manager, element_cls, new_name
):
    element = element_factory.create(element_cls)
    property_page = DeclaredNamePropertyPage(element, event_manager)

    widget = property_page.construct()
    entry = find(widget, "declared-name")
    entry.set_text(new_name)

    assert element.declaredName == new_name


def test_part_usage_type_property_page_sets_and_replaces_type(
    element_factory,
    event_manager,
):
    engine = element_factory.create(sysml2.PartDefinition)
    engine.declaredName = "Engine"
    motor = element_factory.create(sysml2.PartDefinition)
    motor.declaredName = "Motor"
    usage = element_factory.create(sysml2.PartUsage)
    usage.declaredName = "vehicleEngine"
    property_page = PartUsageTypePropertyPage(usage, event_manager)

    widget = property_page.construct()
    dropdown = find(widget, "part-usage-type")

    engine_index = next(
        n for n, lv in enumerate(dropdown.get_model()) if lv.value == engine.id
    )
    dropdown.set_selected(engine_index)

    assert kk.feature_type(usage) is engine
    assert len(element_factory.lselect(kerml.FeatureTyping)) == 1

    motor_index = next(
        n for n, lv in enumerate(dropdown.get_model()) if lv.value == motor.id
    )
    dropdown.set_selected(motor_index)

    assert kk.feature_type(usage) is motor
    assert len(element_factory.lselect(kerml.FeatureTyping)) == 1


def test_part_usage_type_property_page_can_clear_type(
    element_factory,
    event_manager,
):
    engine = element_factory.create(sysml2.PartDefinition)
    usage = element_factory.create(sysml2.PartUsage)
    kk.set_feature_type(usage, engine)
    property_page = PartUsageTypePropertyPage(usage, event_manager)

    widget = property_page.construct()
    dropdown = find(widget, "part-usage-type")
    dropdown.set_selected(0)

    assert kk.feature_type(usage) is None
    assert element_factory.lselect(kerml.FeatureTyping) == []


def test_attribute_usage_type_property_page_sets_and_replaces_type(
    element_factory,
    event_manager,
):
    mass = element_factory.create(sysml2.AttributeDefinition)
    mass.declaredName = "Mass"
    temperature = element_factory.create(sysml2.AttributeDefinition)
    temperature.declaredName = "Temperature"
    engine = element_factory.create(sysml2.PartDefinition)
    engine.declaredName = "Engine"
    usage = element_factory.create(sysml2.AttributeUsage)
    usage.declaredName = "m"
    property_page = AttributeUsageTypePropertyPage(usage, event_manager)

    widget = property_page.construct()
    dropdown = find(widget, "attribute-usage-type")
    values = {lv.value for lv in dropdown.get_model()}
    assert mass.id in values
    assert temperature.id in values
    assert engine.id not in values

    mass_index = next(
        n for n, lv in enumerate(dropdown.get_model()) if lv.value == mass.id
    )
    dropdown.set_selected(mass_index)

    assert kk.feature_type(usage) is mass
    assert len(element_factory.lselect(kerml.FeatureTyping)) == 1

    temperature_index = next(
        n for n, lv in enumerate(dropdown.get_model()) if lv.value == temperature.id
    )
    dropdown.set_selected(temperature_index)

    assert kk.feature_type(usage) is temperature
    assert len(element_factory.lselect(kerml.FeatureTyping)) == 1


def test_attribute_usage_type_property_page_offers_library_value_types(
    element_factory,
    event_manager,
):
    root = element_factory.create(kerml.Namespace)
    usage = element_factory.create(sysml2.AttributeUsage)
    usage.declaredName = "speed"
    kk.add_owned_member(root, usage, element_factory.create(kerml.OwningMembership))
    property_page = AttributeUsageTypePropertyPage(usage, event_manager)

    widget = property_page.construct()
    dropdown = find(widget, "attribute-usage-type")
    values = {lv.value for lv in dropdown.get_model()}
    assert "library:Real" in values

    real_index = next(
        n for n, lv in enumerate(dropdown.get_model()) if lv.value == "library:Real"
    )
    dropdown.set_selected(real_index)

    typed = kk.feature_type(usage)
    assert type(typed) is kerml.DataType
    assert typed.declaredName == "Real"
    assert kk.owning_namespace(typed) is root


def test_attribute_usage_type_property_page_can_clear_type(
    element_factory,
    event_manager,
):
    mass = element_factory.create(sysml2.AttributeDefinition)
    usage = element_factory.create(sysml2.AttributeUsage)
    kk.set_feature_type(usage, mass)
    property_page = AttributeUsageTypePropertyPage(usage, event_manager)

    widget = property_page.construct()
    dropdown = find(widget, "attribute-usage-type")
    dropdown.set_selected(0)

    assert kk.feature_type(usage) is None
    assert element_factory.lselect(kerml.FeatureTyping) == []


def test_action_usage_type_property_page_sets_and_replaces_type(
    element_factory,
    event_manager,
):
    brake = element_factory.create(sysml2.ActionDefinition)
    brake.declaredName = "Brake"
    accelerate = element_factory.create(sysml2.ActionDefinition)
    accelerate.declaredName = "Accelerate"
    engine = element_factory.create(sysml2.PartDefinition)
    engine.declaredName = "Engine"
    usage = element_factory.create(sysml2.ActionUsage)
    usage.declaredName = "emergencyBrake"
    property_page = ActionUsageTypePropertyPage(usage, event_manager)

    widget = property_page.construct()
    dropdown = find(widget, "action-usage-type")
    # The dropdown lists ActionDefinitions only -- not PartDefinitions.
    values = {lv.value for lv in dropdown.get_model()}
    assert brake.id in values
    assert accelerate.id in values
    assert engine.id not in values

    brake_index = next(
        n for n, lv in enumerate(dropdown.get_model()) if lv.value == brake.id
    )
    dropdown.set_selected(brake_index)

    assert kk.feature_type(usage) is brake
    assert len(element_factory.lselect(kerml.FeatureTyping)) == 1

    accelerate_index = next(
        n for n, lv in enumerate(dropdown.get_model()) if lv.value == accelerate.id
    )
    dropdown.set_selected(accelerate_index)

    # Re-typing replaces the stored FeatureTyping (no duplicate accumulation).
    assert kk.feature_type(usage) is accelerate
    assert len(element_factory.lselect(kerml.FeatureTyping)) == 1


def test_action_usage_type_property_page_can_clear_type(
    element_factory,
    event_manager,
):
    brake = element_factory.create(sysml2.ActionDefinition)
    usage = element_factory.create(sysml2.ActionUsage)
    kk.set_feature_type(usage, brake)
    property_page = ActionUsageTypePropertyPage(usage, event_manager)

    widget = property_page.construct()
    dropdown = find(widget, "action-usage-type")
    dropdown.set_selected(0)

    assert kk.feature_type(usage) is None
    assert element_factory.lselect(kerml.FeatureTyping) == []


def test_constraint_usage_type_property_page_sets_and_replaces_type(
    element_factory,
    event_manager,
):
    limit = element_factory.create(sysml2.ConstraintDefinition)
    limit.declaredName = "Limit"
    other = element_factory.create(sysml2.ConstraintDefinition)
    other.declaredName = "Other"
    usage = element_factory.create(sysml2.ConstraintUsage)
    usage.declaredName = "c"
    property_page = ConstraintRequirementTypePropertyPage(usage, event_manager)

    widget = property_page.construct()
    dropdown = find(widget, "constraint-usage-type")
    values = {lv.value for lv in dropdown.get_model()}
    assert limit.id in values
    assert other.id in values

    limit_index = next(
        n for n, lv in enumerate(dropdown.get_model()) if lv.value == limit.id
    )
    dropdown.set_selected(limit_index)
    assert kk.feature_type(usage) is limit
    assert len(element_factory.lselect(kerml.FeatureTyping)) == 1

    other_index = next(
        n for n, lv in enumerate(dropdown.get_model()) if lv.value == other.id
    )
    dropdown.set_selected(other_index)
    assert kk.feature_type(usage) is other
    assert len(element_factory.lselect(kerml.FeatureTyping)) == 1


def test_requirement_usage_type_property_page_lists_requirement_definitions(
    element_factory,
    event_manager,
):
    mass_req = element_factory.create(sysml2.RequirementDefinition)
    mass_req.declaredName = "MassReq"
    plain_constraint = element_factory.create(sysml2.ConstraintDefinition)
    plain_constraint.declaredName = "PlainConstraint"
    usage = element_factory.create(sysml2.RequirementUsage)
    usage.declaredName = "r"
    property_page = ConstraintRequirementTypePropertyPage(usage, event_manager)

    widget = property_page.construct()
    dropdown = find(widget, "constraint-usage-type")
    values = {lv.value for lv in dropdown.get_model()}
    # A RequirementUsage is typed by a RequirementDefinition; a plain
    # ConstraintDefinition (not a requirement) must not appear.
    assert mass_req.id in values
    assert plain_constraint.id not in values

    index = next(
        n for n, lv in enumerate(dropdown.get_model()) if lv.value == mass_req.id
    )
    dropdown.set_selected(index)
    assert kk.feature_type(usage) is mass_req
    assert len(element_factory.lselect(kerml.FeatureTyping)) == 1


def test_constraint_usage_type_property_page_can_clear_type(
    element_factory,
    event_manager,
):
    limit = element_factory.create(sysml2.ConstraintDefinition)
    usage = element_factory.create(sysml2.ConstraintUsage)
    kk.set_feature_type(usage, limit)
    property_page = ConstraintRequirementTypePropertyPage(usage, event_manager)

    widget = property_page.construct()
    dropdown = find(widget, "constraint-usage-type")
    dropdown.set_selected(0)

    assert kk.feature_type(usage) is None
    assert element_factory.lselect(kerml.FeatureTyping) == []


def test_constraint_usage_dropdown_excludes_requirement_definitions(
    element_factory,
    event_manager,
):
    # Regression: RequirementDefinition subclasses ConstraintDefinition, but a
    # plain ConstraintUsage must NOT be offered a RequirementDefinition (which
    # the importer would reject as a cross-kind mismatch).
    plain_constraint = element_factory.create(sysml2.ConstraintDefinition)
    plain_constraint.declaredName = "Limit"
    requirement_def = element_factory.create(sysml2.RequirementDefinition)
    requirement_def.declaredName = "MassReq"
    usage = element_factory.create(sysml2.ConstraintUsage)
    usage.declaredName = "c"
    property_page = ConstraintRequirementTypePropertyPage(usage, event_manager)

    widget = property_page.construct()
    dropdown = find(widget, "constraint-usage-type")
    values = {lv.value for lv in dropdown.get_model()}
    assert plain_constraint.id in values
    assert requirement_def.id not in values


@pytest.mark.parametrize(
    ("element_cls", "new_name"),
    [
        (sysml2.PortDefinition, "Fuel"),
        (sysml2.PortUsage, "p"),
    ],
)
def test_declared_name_property_page_renames_port(
    element_factory, event_manager, element_cls, new_name
):
    element = element_factory.create(element_cls)
    property_page = DeclaredNamePropertyPage(element, event_manager)

    widget = property_page.construct()
    entry = find(widget, "declared-name")
    entry.set_text(new_name)

    assert element.declaredName == new_name


def test_port_usage_type_property_page_sets_and_replaces_type(
    element_factory,
    event_manager,
):
    fuel = element_factory.create(sysml2.PortDefinition)
    fuel.declaredName = "Fuel"
    power = element_factory.create(sysml2.PortDefinition)
    power.declaredName = "Power"
    engine = element_factory.create(sysml2.PartDefinition)
    engine.declaredName = "Engine"
    usage = element_factory.create(sysml2.PortUsage)
    usage.declaredName = "p"
    property_page = PortUsageTypePropertyPage(usage, event_manager)

    widget = property_page.construct()
    dropdown = find(widget, "port-usage-type")
    # The dropdown lists PortDefinitions only -- not PartDefinitions.
    values = {lv.value for lv in dropdown.get_model()}
    assert fuel.id in values
    assert power.id in values
    assert engine.id not in values

    fuel_index = next(
        n for n, lv in enumerate(dropdown.get_model()) if lv.value == fuel.id
    )
    dropdown.set_selected(fuel_index)
    assert kk.feature_type(usage) is fuel
    assert len(element_factory.lselect(kerml.FeatureTyping)) == 1

    power_index = next(
        n for n, lv in enumerate(dropdown.get_model()) if lv.value == power.id
    )
    dropdown.set_selected(power_index)
    assert kk.feature_type(usage) is power
    assert len(element_factory.lselect(kerml.FeatureTyping)) == 1


def test_port_usage_type_property_page_can_clear_type(
    element_factory,
    event_manager,
):
    fuel = element_factory.create(sysml2.PortDefinition)
    usage = element_factory.create(sysml2.PortUsage)
    kk.set_feature_type(usage, fuel)
    property_page = PortUsageTypePropertyPage(usage, event_manager)

    widget = property_page.construct()
    dropdown = find(widget, "port-usage-type")
    dropdown.set_selected(0)

    assert kk.feature_type(usage) is None
    assert element_factory.lselect(kerml.FeatureTyping) == []


def test_port_usage_type_property_page_sets_conjugated_typing(
    element_factory,
    event_manager,
):
    from gaphor.SysML2 import conjugation

    fuel = element_factory.create(sysml2.PortDefinition)
    fuel.declaredName = "Fuel"
    usage = element_factory.create(sysml2.PortUsage)
    usage.declaredName = "p"
    property_page = PortUsageTypePropertyPage(usage, event_manager)

    widget = property_page.construct()
    dropdown = find(widget, "port-usage-type")
    conjugated = find(widget, "port-usage-conjugated")

    fuel_index = next(
        n for n, lv in enumerate(dropdown.get_model()) if lv.value == fuel.id
    )
    dropdown.set_selected(fuel_index)
    # Plain typing first.
    assert kk.feature_type(usage) is fuel
    assert conjugation.conjugated_typing(usage) is None

    # Toggling conjugation re-types by the conjugate of Fuel, with no duplicate.
    conjugated.set_active(True)
    typing = conjugation.conjugated_typing(usage)
    assert typing is not None
    assert conjugation.conjugated_type_name(usage) is fuel
    assert len(element_factory.lselect(sysml2.ConjugatedPortTyping)) == 1

    # Toggling it back off restores the plain typing.
    conjugated.set_active(False)
    assert conjugation.conjugated_typing(usage) is None
    assert kk.feature_type(usage) is fuel


def test_port_usage_type_property_page_reflects_existing_conjugation(
    element_factory,
    event_manager,
):
    from gaphor.SysML2 import conjugation

    fuel = element_factory.create(sysml2.PortDefinition)
    fuel.declaredName = "Fuel"
    usage = element_factory.create(sysml2.PortUsage)
    usage.declaredName = "p"
    conjugation.set_conjugated_port_type(usage, fuel)

    property_page = PortUsageTypePropertyPage(usage, event_manager)
    widget = property_page.construct()
    dropdown = find(widget, "port-usage-type")
    conjugated = find(widget, "port-usage-conjugated")

    # The page preselects the ORIGINAL definition and shows conjugation on.
    assert conjugated.get_active() is True
    selected = dropdown.get_selected_item()
    assert selected is not None and selected.value == fuel.id


@pytest.mark.parametrize(
    ("element_cls", "new_name"),
    [
        (sysml2.ConnectionDefinition, "C"),
        (sysml2.ConnectionUsage, "c"),
    ],
)
def test_declared_name_property_page_renames_connection(
    element_factory, event_manager, element_cls, new_name
):
    element = element_factory.create(element_cls)
    property_page = DeclaredNamePropertyPage(element, event_manager)

    widget = property_page.construct()
    entry = find(widget, "declared-name")
    entry.set_text(new_name)

    assert element.declaredName == new_name


def test_part_usage_type_property_page_defers_for_connection_usage(
    element_factory, event_manager
):
    # PartUsageTypePropertyPage matches a ConnectionUsage by isinstance, but must
    # produce NO widget for it (the dedicated connection page handles it), so a
    # ConnectionUsage never gets a second, wrong-kind (PartDefinition) dropdown.
    connection_usage = element_factory.create(sysml2.ConnectionUsage)
    property_page = PartUsageTypePropertyPage(connection_usage, event_manager)

    assert property_page.construct() is None


def test_connection_usage_type_property_page_sets_and_replaces_type(
    element_factory,
    event_manager,
):
    c1 = element_factory.create(sysml2.ConnectionDefinition)
    c1.declaredName = "Flow"
    c2 = element_factory.create(sysml2.ConnectionDefinition)
    c2.declaredName = "Link"
    engine = element_factory.create(sysml2.PartDefinition)
    engine.declaredName = "Engine"
    usage = element_factory.create(sysml2.ConnectionUsage)
    usage.declaredName = "c"
    property_page = ConnectionUsageTypePropertyPage(usage, event_manager)

    widget = property_page.construct()
    dropdown = find(widget, "connection-usage-type")
    # The dropdown lists ConnectionDefinitions only -- not PartDefinitions (even
    # though ConnectionDefinition subclasses PartDefinition, the exact-kind filter
    # keeps a plain PartDefinition out, and keeps ConnectionDefinitions in).
    values = {lv.value for lv in dropdown.get_model()}
    assert c1.id in values
    assert c2.id in values
    assert engine.id not in values

    c1_index = next(
        n for n, lv in enumerate(dropdown.get_model()) if lv.value == c1.id
    )
    dropdown.set_selected(c1_index)
    assert kk.feature_type(usage) is c1
    assert len(element_factory.lselect(kerml.FeatureTyping)) == 1

    c2_index = next(
        n for n, lv in enumerate(dropdown.get_model()) if lv.value == c2.id
    )
    dropdown.set_selected(c2_index)
    assert kk.feature_type(usage) is c2
    assert len(element_factory.lselect(kerml.FeatureTyping)) == 1


def test_part_usage_type_dropdown_excludes_connection_definitions(
    element_factory, event_manager
):
    # Conversely, a plain PartUsage must not be offered a ConnectionDefinition
    # (which subclasses PartDefinition) -- exact-kind filtering keeps it out.
    plain_part = element_factory.create(sysml2.PartDefinition)
    plain_part.declaredName = "Engine"
    connection_def = element_factory.create(sysml2.ConnectionDefinition)
    connection_def.declaredName = "Flow"
    usage = element_factory.create(sysml2.PartUsage)
    usage.declaredName = "p"
    property_page = PartUsageTypePropertyPage(usage, event_manager)

    widget = property_page.construct()
    dropdown = find(widget, "part-usage-type")
    values = {lv.value for lv in dropdown.get_model()}
    assert plain_part.id in values
    assert connection_def.id not in values


def test_connection_usage_type_property_page_can_clear_type(
    element_factory,
    event_manager,
):
    flow = element_factory.create(sysml2.ConnectionDefinition)
    usage = element_factory.create(sysml2.ConnectionUsage)
    kk.set_feature_type(usage, flow)
    property_page = ConnectionUsageTypePropertyPage(usage, event_manager)

    widget = property_page.construct()
    dropdown = find(widget, "connection-usage-type")
    dropdown.set_selected(0)

    assert kk.feature_type(usage) is None
    assert element_factory.lselect(kerml.FeatureTyping) == []
