"""Phase B UI-edit surface for PartDefinition and PartUsage."""

from __future__ import annotations

from gaphor.diagram.diagramtoolbox import get_tool_def
from gaphor.diagram.propertypages import PropertyPages
from gaphor.diagram.tests.fixtures import find
from gaphor.SysML2 import kerml, kerml_kernel as kk, sysml2
from gaphor.SysML2.diagramitems import PartDefinitionItem, PartUsageItem
from gaphor.SysML2.diagramtype import SysML2Diagram
from gaphor.SysML2.modelinglanguage import SysML2ModelingLanguage
from gaphor.SysML2.propertypages import (
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


def test_property_pages_are_registered_for_part_constructs(element_factory):
    part_definition = element_factory.create(sysml2.PartDefinition)
    part_usage = element_factory.create(sysml2.PartUsage)

    definition_pages = set(PropertyPages.find(part_definition))
    usage_pages = set(PropertyPages.find(part_usage))

    assert DeclaredNamePropertyPage in definition_pages
    assert DeclaredNamePropertyPage in usage_pages
    assert PartUsageTypePropertyPage in usage_pages
    assert PartUsageTypePropertyPage not in definition_pages


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
