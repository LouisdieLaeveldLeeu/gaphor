"""Phase A UI foundation for the SysML2 modeling languages."""

from __future__ import annotations

from gaphor.core.modeling import ElementFactory
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2.diagramitems import PartDefinitionItem
from gaphor.SysML2.diagramtype import SysML2Diagram
from gaphor.SysML2.modelinglanguage import (
    KerMLModelingLanguage,
    SysML2ModelingLanguage,
)


def test_sysml2_modeling_language_exposes_ui_foundation():
    language = SysML2ModelingLanguage()

    assert language.toolbox_definition
    assert list(language.element_types) == []

    diagram_types = list(language.diagram_types)
    assert len(diagram_types) == 1
    assert diagram_types[0].id == "sysml2"
    assert diagram_types[0].diagram_type is SysML2Diagram

    assert language.model_browser_model.__name__ == "TreeModel"
    assert language.lookup_element("SysML2Diagram", ns="SysML2") is SysML2Diagram


def test_kerml_modeling_language_ui_foundation_is_empty_but_real():
    language = KerMLModelingLanguage()

    assert language.toolbox_definition == ()
    assert list(language.diagram_types) == []
    assert list(language.element_types) == []
    assert language.model_browser_model.__name__ == "TreeModel"


def test_sysml2_diagram_type_creates_and_reloads(element_factory, saver, loader):
    diagram_type = list(SysML2ModelingLanguage().diagram_types)[0]

    diagram = diagram_type.create(element_factory, None)
    diagram_id = diagram.id

    assert isinstance(diagram, SysML2Diagram)
    assert diagram.diagramType == "sysml2"
    assert diagram.name == "SysML v2 Diagram"

    loader(saver())

    reloaded = element_factory.lookup(diagram_id)
    assert isinstance(reloaded, SysML2Diagram)
    assert reloaded.diagramType == "sysml2"
    assert reloaded.name == "SysML v2 Diagram"


def test_sysml2_tree_model_lists_elements_but_not_projection_items(event_manager):
    factory = ElementFactory(event_manager)
    try:
        package = factory.create(kerml.Package)
        package.declaredName = "Pkg"
        part = factory.create(sysml2.PartDefinition)
        part.declaredName = "Engine"
        diagram = factory.create(SysML2Diagram)
        diagram.name = "View"
        diagram.create(PartDefinitionItem, subject=part)

        model = SysML2ModelingLanguage().model_browser_model(event_manager, factory)
        try:
            root_names = {item.readonly_text for item in model.root}
            root_types = {type(item.element) for item in model.root}

            assert root_names == {"Pkg", "Engine", "View"}
            assert PartDefinitionItem not in root_types
        finally:
            model.shutdown()
    finally:
        factory.shutdown()
