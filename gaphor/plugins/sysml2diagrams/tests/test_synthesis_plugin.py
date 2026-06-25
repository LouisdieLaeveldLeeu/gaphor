"""GUI binding for SysML2 diagram synthesis + browser grooming (Phase 13).

The synthesis/grooming logic is tested headless elsewhere; these smoke tests cover the
thin service: it synthesizes on the current model (idempotently, in a transaction),
no-ops on an empty model, and the toggle flips the browser's internal-view flag.
"""

from __future__ import annotations

from gaphor.core.modeling import Diagram
from gaphor.plugins.sysml2diagrams import SysML2DiagramSynthesis
from gaphor.SysML2.diagramtype import SysML2Diagram
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.treemodel import TreeModel

_MODEL = "package P { part def Engine; part e : Engine; }"


def test_service_synthesizes_current_model(event_manager, element_factory):
    service = SysML2DiagramSynthesis(event_manager, element_factory)
    map_package(parse(_MODEL), element_factory)

    diagrams = service.synthesize()
    assert diagrams and all(isinstance(d, SysML2Diagram) for d in diagrams)

    count = len(list(element_factory.select(Diagram)))
    service.synthesize()  # idempotent: no new diagrams
    assert len(list(element_factory.select(Diagram))) == count


def test_service_no_model_root_is_a_no_op(event_manager, element_factory):
    service = SysML2DiagramSynthesis(event_manager, element_factory)
    assert service.synthesize() == []
    assert not list(element_factory.select(Diagram))


def test_show_internal_toggle_action_flips_browser_flag(event_manager, element_factory):
    service = SysML2DiagramSynthesis(event_manager, element_factory)
    try:
        service.show_internal_action(True)
        assert TreeModel.show_internal is True
        service.show_internal_action(False)
        assert TreeModel.show_internal is False
    finally:
        TreeModel.set_show_internal(False)
