"""Model-browser grooming (completion-roadmap Phase 13).

The browser lists user CONCEPTS and hides internal plumbing (relationship/membership
edges, library value-type proxies, implicit bases, helper elements) by default; a
debug toggle (`TreeModel.set_show_internal`) reveals them. User usages that happen to
be relationships (a ConnectionUsage) stay visible.
"""

from __future__ import annotations

from gaphor.core.modeling import ElementFactory
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.treemodel import TreeModel, _is_browser_element, _is_plumbing

_MODEL = "package P { part def Engine; part e : Engine; attribute t : Real; connection c connect e to e; }"


def _map(text: str):
    factory = ElementFactory()
    return factory, map_package(parse(text), factory).root


def test_plumbing_predicate_classifies_edges_proxies_and_concepts():
    factory, _root = _map(_MODEL)
    typing = next(factory.select(kerml.FeatureTyping))
    membership = next(factory.select(kerml.OwningMembership))
    proxy = next(d for d in factory.select(kerml.DataType) if kk.is_library_proxy(d))
    package = next(factory.select(kerml.Package))
    connection = next(factory.select(sysml2.ConnectionUsage))

    assert _is_plumbing(typing) and _is_plumbing(membership) and _is_plumbing(proxy)
    assert not _is_plumbing(package)
    assert not _is_plumbing(connection)  # a user usage, even though it is a relationship


def test_browser_hides_plumbing_by_default_but_shows_it_when_internal():
    factory, _root = _map(_MODEL)
    typing = next(factory.select(kerml.FeatureTyping))
    package = next(factory.select(kerml.Package))
    connection = next(factory.select(sysml2.ConnectionUsage))

    assert _is_browser_element(package)  # concept: shown
    assert _is_browser_element(connection)  # user usage: shown
    assert not _is_browser_element(typing)  # plumbing: hidden by default
    assert _is_browser_element(typing, show_internal=True)  # revealed in debug view


def _root_types(model: TreeModel) -> set[str]:
    store = model.root
    return {
        type(store.get_item(i).element).__name__ for i in range(store.get_n_items())
    }


def test_tree_model_grooms_and_toggle_reveals_plumbing(event_manager, element_factory):
    map_package(parse(_MODEL), element_factory)
    model = TreeModel(event_manager, element_factory)
    try:
        groomed = _root_types(model)
        assert "Package" in groomed and "PartUsage" in groomed
        assert "FeatureTyping" not in groomed and "OwningMembership" not in groomed

        TreeModel.set_show_internal(True)
        internal = _root_types(model)
        assert "FeatureTyping" in internal and "OwningMembership" in internal
    finally:
        TreeModel.set_show_internal(False)  # reset the class-level flag
        model.shutdown()
