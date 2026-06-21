"""Interface Definition/Usage (Phase 8c): the connection-level surface.

InterfaceDefinition/InterfaceUsage subclass ConnectionDefinition/ConnectionUsage,
so an interface reuses the connection machinery: typing by an InterfaceDefinition,
binary `connect a to b` ends (Phase 9), a feature direction prefix (Phase 8b),
its own diagram items and type page. Interface-end PORT bodies and flow are a
deferred dependency (the rows stay `alpha`).
"""

from __future__ import annotations

import pytest

from gaphor.core.modeling import Diagram, ElementFactory
from gaphor.diagram.drop import drop
from gaphor.diagram.propertypages import PropertyPages
from gaphor.diagram.tests.fixtures import find
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.diagramitems import (
    ConnectionUsageItem,
    InterfaceDefinitionItem,
    InterfaceUsageItem,
)
from gaphor.SysML2.export import export_namespace
from gaphor.SysML2.grammar import ast
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.kerml import FeatureDirectionKind as D
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.propertypages import (
    ConnectionUsageTypePropertyPage,
    InterfaceUsageTypePropertyPage,
    PartUsageTypePropertyPage,
)
from gaphor.SysML2.roundtrip import round_trip
from gaphor.SysML2.validation import has_errors, validate

# Importing registers the projection handlers, connectors, and property pages.
import gaphor.SysML2.drop  # noqa: F401, E402
import gaphor.SysML2.propertypages  # noqa: F401, E402


def _map(text: str):
    factory = ElementFactory()
    return factory, map_package(parse(text), factory)


def _iface(factory, name: str) -> sysml2.InterfaceUsage:
    return next(
        u for u in factory.select(sysml2.InterfaceUsage) if u.declaredName == name
    )


# --- parse / map -------------------------------------------------------------


def test_parse_interface_definition_and_usage():
    pkg = parse("interface def I;\ninterface i : I;")
    assert pkg.members == (
        ast.InterfaceDefinition(name="I"),
        ast.InterfaceUsage(name="i", type_name=("I",)),
    )


def test_interface_usage_typed_by_interface_definition():
    factory, result = _map("interface def I;\ninterface i : I;")
    assert not result.unresolved_types and not result.mistyped
    assert kk.feature_type(_iface(factory, "i")).declaredName == "I"


def test_interface_usage_is_a_connection_usage():
    factory, _ = _map("interface i;")
    assert isinstance(_iface(factory, "i"), sysml2.ConnectionUsage)


def test_interface_connect_ends_resolve_like_a_connection():
    factory, result = _map(
        "part a;\npart b;\ninterface def I;\ninterface i : I connect a to b;"
    )
    assert not result.unresolved_ends
    i = _iface(factory, "i")
    assert kk._single(i.source).declaredName == "a"
    assert kk._single(i.target).declaredName == "b"


def test_interface_typed_by_connection_definition_is_mistyped():
    # An interface must be typed by an InterfaceDefinition, not a plain
    # ConnectionDefinition (exact-kind), so this is recorded mistyped.
    factory, result = _map("connection def C;\ninterface i : C;")
    assert result.mistyped[_iface(factory, "i").id][0] == "C"


def test_interface_can_be_directed():
    factory, _ = _map("in interface i;")
    assert _iface(factory, "i").direction == D.in_


# --- export / round-trip -----------------------------------------------------


def test_export_emits_interface_keywords():
    _factory, result = _map(
        "part a;\npart b;\ninterface def I;\nin interface i : I connect a to b;"
    )
    text = export_namespace(result.root)
    assert "interface def I;" in text
    assert "in interface i : I connect a to b;" in text


def test_interface_round_trips():
    result = round_trip(
        "part a;\npart b;\ninterface def I;\ninterface i : I connect a to b;"
    )
    assert result.preserved
    assert result.valid


def test_interface_is_distinct_from_connection_in_canonical_form():
    assert round_trip("interface i;").source_form != round_trip(
        "connection i;"
    ).source_form
    assert round_trip("interface def I;").source_form != round_trip(
        "connection def I;"
    ).source_form


# --- validation --------------------------------------------------------------


def test_interface_broken_end_is_reported():
    factory, result = _map("part a;\ninterface i connect a to missing;")
    diagnostics = validate(
        factory, result.unresolved_types, result.mistyped, result.unresolved_ends
    )
    assert any(d.rule == "broken-connection-end" for d in diagnostics)


def test_interface_non_feature_end_is_reported_model_derived():
    # The connection-end integrity rule selects ConnectionUsage, which includes
    # InterfaceUsage -- so a non-feature end is caught for interfaces too.
    factory, _ = _map("part def D;\npart a;\ninterface i;")
    i = _iface(factory, "i")
    i.source = next(iter(factory.select(sysml2.PartDefinition)))  # non-feature
    i.target = next(iter(factory.select(sysml2.PartUsage)))
    assert any(d.rule == "non-feature-connection-end" for d in validate(factory))


# --- diagram -----------------------------------------------------------------


def test_interface_definition_projects_as_its_own_box(element_factory):
    map_package(parse("interface def I;"), element_factory)
    i = next(iter(element_factory.select(sysml2.InterfaceDefinition)))
    diagram = element_factory.create(Diagram)

    item = drop(i, diagram, 0, 0)

    # Its own item wins over the inherited ConnectionDefinitionItem.
    assert type(item) is InterfaceDefinitionItem
    assert item.subject is i


def test_interface_usage_projects_as_its_own_line_bound_to_ends(element_factory):
    map_package(
        parse("part a;\npart b;\ninterface i connect a to b;"), element_factory
    )
    a = next(u for u in element_factory.select(sysml2.PartUsage) if u.declaredName == "a")
    b = next(u for u in element_factory.select(sysml2.PartUsage) if u.declaredName == "b")
    i = _iface(element_factory, "i")
    diagram = element_factory.create(Diagram)
    a_item = drop(a, diagram, 0, 0)
    b_item = drop(b, diagram, 100, 0)

    i_item = drop(i, diagram, 50, 0)

    assert type(i_item) is InterfaceUsageItem
    assert isinstance(i_item, ConnectionUsageItem)  # reuses the connection line
    head = diagram.connections.get_connection(i_item.head)
    tail = diagram.connections.get_connection(i_item.tail)
    assert head is not None and head.connected is a_item
    assert tail is not None and tail.connected is b_item
    assert len(list(element_factory.select(sysml2.InterfaceUsage))) == 1


# --- UI-edit -----------------------------------------------------------------


def test_interface_usage_type_page_lists_interface_definitions(
    element_factory, event_manager
):
    i_def = element_factory.create(sysml2.InterfaceDefinition)
    i_def.declaredName = "I"
    c_def = element_factory.create(sysml2.ConnectionDefinition)
    c_def.declaredName = "C"
    usage = element_factory.create(sysml2.InterfaceUsage)
    page = InterfaceUsageTypePropertyPage(usage, event_manager)

    widget = page.construct()
    dropdown = find(widget, "interface-usage-type")
    values = {lv.value for lv in dropdown.get_model()}
    assert i_def.id in values  # InterfaceDefinitions offered
    assert c_def.id not in values  # plain ConnectionDefinitions are not

    index = next(n for n, lv in enumerate(dropdown.get_model()) if lv.value == i_def.id)
    dropdown.set_selected(index)
    assert kk.feature_type(usage) is i_def


def test_interface_usage_gets_exactly_one_type_page(element_factory):
    pages = list(PropertyPages.find(element_factory.create(sysml2.InterfaceUsage)))
    # The InterfaceUsage type page is present; the inherited ConnectionUsage and
    # PartUsage type pages defer (no duplicate/wrong-kind dropdown).
    assert pages.count(InterfaceUsageTypePropertyPage) == 1
    iface = element_factory.create(sysml2.InterfaceUsage)
    iface.declaredName = "i"
    for page_cls in (ConnectionUsageTypePropertyPage, PartUsageTypePropertyPage):
        assert page_cls(iface, None).construct() is None


# --- toolbox -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("tool_id", "item_cls", "element_cls", "default_name"),
    [
        (
            "toolbox-interface-definition",
            InterfaceDefinitionItem,
            sysml2.InterfaceDefinition,
            "InterfaceDefinition",
        ),
        (
            "toolbox-interface-usage",
            InterfaceUsageItem,
            sysml2.InterfaceUsage,
            "interfaceUsage",
        ),
    ],
)
def test_interface_toolbox_entries_create_element_and_projection(
    element_factory, tool_id, item_cls, element_cls, default_name
):
    from gaphor.diagram.diagramtoolbox import get_tool_def
    from gaphor.SysML2.diagramtype import SysML2Diagram
    from gaphor.SysML2.modelinglanguage import SysML2ModelingLanguage

    diagram = element_factory.create(SysML2Diagram)
    tool = get_tool_def(SysML2ModelingLanguage(), tool_id)
    assert tool.item_factory
    item = tool.item_factory(diagram, None)

    # InterfaceUsage subclasses ConnectionUsage/PartUsage; the tool must create
    # exactly the interface item/element, not an ancestor's.
    assert type(item) is item_cls
    assert type(item.subject) is element_cls
    assert item.subject.declaredName == default_name
    assert item in diagram.ownedPresentation
