"""SysML2 port display modes (completion-roadmap Phase 15, spec 8.2.3.12).

A PortUsage is ONE semantic element; the SysML2 DIAGRAM's PortDisplayMode chooses how
it is presented -- boundary squares, compartment text, or both -- and switching the
mode changes only the presentation, never the model (no port is created, deleted, or
duplicated). These tests pin that contract, the three rendering modes, boundary
attachment to the owner, the default (boundary), and persistence of the mode.
"""

from __future__ import annotations

import io

import gaphor.storage as storage
from gaphor.core.eventmanager import EventManager
from gaphor.core.modeling import ElementFactory
from gaphor.core.modeling.elementdispatcher import ElementDispatcher
from gaphor.core.modeling.modelinglanguage import (
    CoreModelingLanguage,
    MockModelingLanguage,
)
from gaphor.diagram.shapes import Text
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2.diagramitems import PartDefinitionItem, PortUsageItem
from gaphor.SysML2.diagramtype import PortDisplayMode, port_display_mode
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.modelinglanguage import (
    KerMLModelingLanguage,
    SysML2ModelingLanguage,
)
from gaphor.SysML2.synthesis import set_port_display_mode, synthesize_diagram

_MODEL = "package P { part def Engine { port p; } }"


def _modeling_language():
    return MockModelingLanguage(
        CoreModelingLanguage(), KerMLModelingLanguage(), SysML2ModelingLanguage()
    )


def _wired_factory() -> ElementFactory:
    event_manager = EventManager()
    return ElementFactory(
        event_manager, ElementDispatcher(event_manager, _modeling_language())
    )


def _synthesize(mode=None):
    factory = _wired_factory()
    map_package(parse(_MODEL), factory)
    package = next(p for p in factory.select(kerml.Package))
    diagram = synthesize_diagram(
        package, event_manager=factory.event_manager, layout=False, port_display_mode=mode
    )
    diagram.update(diagram.ownedPresentation)
    return factory, diagram


def _texts(shape):
    out, stack = [], [shape]
    while stack:
        node = stack.pop()
        if isinstance(node, Text):
            out.append(node.text())
        else:
            try:
                stack.extend(list(node))
            except TypeError:
                pass
    return out


def _squares(diagram):
    return [i for i in diagram.ownedPresentation if isinstance(i, PortUsageItem)]


def _engine_box(diagram):
    return next(i for i in diagram.ownedPresentation if isinstance(i, PartDefinitionItem))


def _port_count(factory):
    return len(list(factory.select(sysml2.PortUsage)))


def _ports_compartment_shown(diagram):
    diagram.update(diagram.ownedPresentation)
    return "ports" in _texts(_engine_box(diagram).shape)


# --- default + per-mode rendering --------------------------------------------


def test_default_mode_is_boundary():
    factory, diagram = _synthesize()  # no explicit mode
    assert port_display_mode(diagram) is PortDisplayMode.BOUNDARY
    assert len(_squares(diagram)) == 1
    assert not _ports_compartment_shown(diagram)


def test_boundary_mode_shows_squares_not_compartment():
    factory, diagram = _synthesize(PortDisplayMode.BOUNDARY)
    assert len(_squares(diagram)) == 1
    assert not _ports_compartment_shown(diagram)


def test_compartment_mode_shows_compartment_not_squares():
    factory, diagram = _synthesize(PortDisplayMode.COMPARTMENT)
    assert _squares(diagram) == []
    assert _ports_compartment_shown(diagram)


def test_both_debug_mode_shows_squares_and_compartment():
    factory, diagram = _synthesize(PortDisplayMode.BOTH_DEBUG)
    assert len(_squares(diagram)) == 1
    assert _ports_compartment_shown(diagram)


# --- boundary attachment -----------------------------------------------------


def test_boundary_port_is_attached_to_its_owner():
    factory, diagram = _synthesize(PortDisplayMode.BOUNDARY)
    assert _squares(diagram)[0].parent is _engine_box(diagram)


# --- semantic safety when switching modes ------------------------------------


def test_switching_modes_never_changes_the_model():
    factory, diagram = _synthesize(PortDisplayMode.BOUNDARY)
    for mode in (
        PortDisplayMode.COMPARTMENT,
        PortDisplayMode.BOTH_DEBUG,
        PortDisplayMode.BOUNDARY,
        PortDisplayMode.COMPARTMENT,
    ):
        set_port_display_mode(diagram, mode)
        assert _port_count(factory) == 1  # exactly one PortUsage, always
        squares = _squares(diagram)
        # the presentation matches the mode
        from gaphor.SysML2.diagramtype import show_boundary_ports, show_ports_compartment

        assert bool(squares) == show_boundary_ports(diagram)
        assert _ports_compartment_shown(diagram) == show_ports_compartment(diagram)


# --- persistence -------------------------------------------------------------


def test_mode_and_ports_persist_across_save_reload():
    factory, diagram = _synthesize(PortDisplayMode.COMPARTMENT)
    diagram_id = diagram.id

    buffer = io.StringIO()
    storage.save(buffer, factory)
    reloaded = ElementFactory()
    buffer.seek(0)
    storage.load(
        buffer, element_factory=reloaded, modeling_language=_modeling_language()
    )

    diagram2 = reloaded.lookup(diagram_id)
    assert port_display_mode(diagram2) is PortDisplayMode.COMPARTMENT  # mode preserved
    assert len(list(reloaded.select(sysml2.PortUsage))) == 1  # one PortUsage
