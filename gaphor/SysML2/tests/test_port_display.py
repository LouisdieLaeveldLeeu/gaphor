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
from gaphor.diagram.presentation import connect
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


def test_boundary_attachment_persists_across_save_reload():
    # A BOUNDARY diagram with an attached port square reloads with the square still
    # attached to its owner (parent + boundary connection restored).
    factory, diagram = _synthesize(PortDisplayMode.BOUNDARY)
    square = _squares(diagram)[0]
    owner = _engine_box(diagram)
    assert square.parent is owner
    square_id, owner_id = square.id, owner.id

    buffer = io.StringIO()
    storage.save(buffer, factory)
    reloaded = ElementFactory()
    buffer.seek(0)
    storage.load(
        buffer, element_factory=reloaded, modeling_language=_modeling_language()
    )
    reloaded.lookup(diagram.id).postload()  # rebuild connections (as the app does)

    square2 = reloaded.lookup(square_id)
    owner2 = reloaded.lookup(owner_id)
    assert isinstance(square2, PortUsageItem)
    assert square2.parent is owner2  # still visually nested under its owner
    # ... AND the boundary HANDLE connection itself is restored (the parent relation
    # persists independently, so it alone does not prove the attachment reloaded).
    cinfo = square2.diagram.connections.get_connection(square2._handle)
    assert cinfo is not None and cinfo.connected is owner2


# --- finding fixes -----------------------------------------------------------


def test_port_cannot_attach_to_a_non_owning_part():
    # A port owned by Engine must not be attachable to another part's box: the
    # connector rejects it, so a persisted diagram cannot misrepresent ownership.
    from gaphor.SysML2.connectors import PortUsageBoundaryConnector
    from gaphor.SysML2.diagramitems import PartDefinitionItem
    from gaphor.SysML2.diagramtype import SysML2Diagram

    factory = _wired_factory()
    map_package(
        parse("package P { part def Engine { port p; } part def Other; }"), factory
    )
    engine = next(
        d for d in factory.select(sysml2.PartDefinition) if d.declaredName == "Engine"
    )
    other = next(
        d for d in factory.select(sysml2.PartDefinition) if d.declaredName == "Other"
    )
    port = next(factory.select(sysml2.PortUsage))
    diagram = factory.create(SysML2Diagram)
    engine_item = diagram.create(PartDefinitionItem)
    engine_item.subject = engine
    other_item = diagram.create(PartDefinitionItem)
    other_item.subject = other
    port_item = diagram.create(PortUsageItem)
    port_item.subject = port

    assert PortUsageBoundaryConnector(engine_item, port_item).allow(port_item._handle, None)
    wrong = PortUsageBoundaryConnector(other_item, port_item)
    assert not wrong.allow(port_item._handle, None)  # Other does not own p
    assert wrong.connect(port_item._handle, None) is False
    assert port_item.parent is not other_item  # never re-parented to the wrong owner

    # The REAL path: the aspect layer physically glues the handle BEFORE the adapter
    # runs and ignores its return value, so the adapter must actively sever a
    # wrong-owner connection. `connect()` here is the same helper drop/synthesis use.
    connect(port_item, port_item._handle, other_item)
    assert diagram.connections.get_connection(port_item._handle) is None  # severed
    assert port_item.parent is None

    connect(port_item, port_item._handle, engine_item)  # the true owner still works
    cinfo = diagram.connections.get_connection(port_item._handle)
    assert cinfo is not None and cinfo.connected is engine_item
    assert port_item.parent is engine_item


def test_hiding_ports_removes_every_square_including_duplicates():
    from gaphor.diagram.drop import drop

    factory, diagram = _synthesize(PortDisplayMode.BOUNDARY)
    port = next(factory.select(sysml2.PortUsage))
    drop(port, diagram, 0, 0)  # a SECOND square for the same port
    assert len(_squares(diagram)) == 2

    set_port_display_mode(diagram, PortDisplayMode.COMPARTMENT)
    assert _squares(diagram) == []  # ALL squares removed, not just one


def test_port_display_mode_property_page_switches_the_diagram():
    # The diagram property page (shown when the diagram is selected in the browser)
    # switches the mode via its dropdown -- reconciling the presentation, never the
    # model.
    from gaphor.SysML2.propertypages import PortDisplayModePropertyPage

    factory, diagram = _synthesize(PortDisplayMode.BOUNDARY)
    assert len(_squares(diagram)) == 1

    page = PortDisplayModePropertyPage(diagram, factory.event_manager)
    widget = page.construct()
    dropdown = widget.get_first_child().get_next_sibling()  # box: [label, dropdown]
    assert dropdown.get_selected() == 0  # reflects the current BOUNDARY mode

    dropdown.set_selected(1)  # Compartment text
    assert port_display_mode(diagram) is PortDisplayMode.COMPARTMENT
    assert _squares(diagram) == []  # squares removed (presentation only)...
    assert _port_count(factory) == 1  # ...the model is untouched

    dropdown.set_selected(2)  # Both (debug)
    assert port_display_mode(diagram) is PortDisplayMode.BOTH_DEBUG
    assert len(_squares(diagram)) == 1
    assert _port_count(factory) == 1


def test_port_display_mode_dropdown_syncs_on_undo_redo():
    # The dropdown must follow the model: undo/redo of portDisplayMode reconciles the
    # presentations AND updates the control (a one-way page would show a stale mode).
    from gaphor.SysML2.propertypages import PortDisplayModePropertyPage
    from gaphor.services.undomanager import UndoManager

    factory, diagram = _synthesize(PortDisplayMode.BOUNDARY)
    undo_manager = UndoManager(factory.event_manager, factory)
    try:
        page = PortDisplayModePropertyPage(diagram, factory.event_manager)
        widget = page.construct()
        dropdown = widget.get_first_child().get_next_sibling()

        dropdown.set_selected(1)  # user -> Compartment (a recorded transaction)
        assert port_display_mode(diagram) is PortDisplayMode.COMPARTMENT
        assert dropdown.get_selected() == 1

        undo_manager.undo_transaction()
        assert port_display_mode(diagram) is PortDisplayMode.BOUNDARY
        assert dropdown.get_selected() == 0  # THE FIX: control follows the model
        assert len(_squares(diagram)) == 1  # presentations restored too
        assert _port_count(factory) == 1

        undo_manager.redo_transaction()
        assert port_display_mode(diagram) is PortDisplayMode.COMPARTMENT
        assert dropdown.get_selected() == 1
        assert _squares(diagram) == []
        assert _port_count(factory) == 1
    finally:
        undo_manager.shutdown()


def test_compartment_refreshes_when_a_member_is_renamed():
    from gaphor.SysML2.diagramitems import PartDefinitionItem
    from gaphor.SysML2.diagramtype import PortDisplayMode as _PDM
    from gaphor.SysML2.diagramtype import SysML2Diagram

    factory = _wired_factory()
    map_package(parse("part def Engine { attribute power; }"), factory)
    engine = next(
        d for d in factory.select(sysml2.PartDefinition) if d.declaredName == "Engine"
    )
    attr = next(a for a in factory.select(sysml2.AttributeUsage))
    diagram = factory.create(SysML2Diagram)
    diagram.portDisplayMode = _PDM.COMPARTMENT.value
    item = diagram.create(PartDefinitionItem)
    item.subject = engine
    assert "power" in _texts(item.shape)
    shape_before = item.shape

    attr.declaredName = "torque"  # rename a contained member
    # PROOF of invalidation: the nested watch must have re-run update_shapes, which
    # builds a NEW shape object. (Merely reading the late-bound text lambda would
    # show the new name even without any watcher -- that is not enough: without the
    # rebuild the item is never marked dirty, so the canvas would not repaint.)
    assert item.shape is not shape_before
    assert "torque" in _texts(item.shape)  # the owner box refreshed
    assert "power" not in _texts(item.shape)
