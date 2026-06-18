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
    ConstraintDefinitionItem,
    ConstraintUsageItem,
    PackageItem,
    PartDefinitionItem,
    PartUsageItem,
    RequirementDefinitionItem,
    RequirementUsageItem,
)
from gaphor.SysML2.diagramtype import SysML2Diagram
from gaphor.SysML2.modelinglanguage import SysML2ModelingLanguage
from gaphor.SysML2.propertypages import (
    ActionUsageTypePropertyPage,
    AttributeUsageTypePropertyPage,
    ConstraintRequirementTypePropertyPage,
    DeclaredNamePropertyPage,
    PartUsageTypePropertyPage,
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
    assert DeclaredNamePropertyPage in definition_pages
    assert DeclaredNamePropertyPage in usage_pages
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
    assert PartUsageTypePropertyPage in usage_pages
    assert PartUsageTypePropertyPage not in definition_pages
    assert PartUsageTypePropertyPage not in attribute_usage_pages
    assert PartUsageTypePropertyPage not in action_usage_pages
    assert PartUsageTypePropertyPage not in requirement_usage_pages


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
