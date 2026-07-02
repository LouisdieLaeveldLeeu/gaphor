"""On-demand SysML2 diagram synthesis (completion-roadmap Phase 13).

Synthesis turns an imported semantic model into initial diagrams without inventing
semantics: each item is a subject-bound view (invariant 4). These headless tests pin
the contract -- one diagram per package, subject binding, idempotency, persistence,
delete cascade, layout placement, and that a synthesized diagram is a browsable
SysML2Diagram.
"""

from __future__ import annotations

from gaphor.core.modeling import Diagram, ElementFactory
from gaphor.diagram.presentation import ElementPresentation, LinePresentation
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.diagramtype import SysML2Diagram
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.synthesis import (
    synthesize_diagram,
    synthesize_diagrams,
    synthesized_diagram_for,
)

_MODEL = "package P { part def Engine; part e : Engine; part w; connection c connect e to w; }"


def _map(text: str):
    factory = ElementFactory()
    return factory, map_package(parse(text), factory).root


def _root(factory) -> kerml.Namespace:
    return next(
        ns
        for ns in factory.select(kerml.Namespace)
        if type(ns) is kerml.Namespace and kk.owning_namespace(ns) is None
    )


def _diagram(factory, name: str) -> Diagram:
    return next(d for d in factory.select(Diagram) if d.name == name)


def test_synthesizes_a_diagram_per_package():
    factory, root = _map(_MODEL)
    synthesize_diagrams(root)
    names = {d.name for d in factory.select(Diagram)}
    assert names == {"Model (synthesized)", "P (synthesized)"}


def test_items_are_subject_bound_views_with_boxes_and_lines():
    factory, root = _map(_MODEL)
    synthesize_diagrams(root)
    items = list(_diagram(factory, "P (synthesized)").ownedPresentation)
    assert items and all(item.subject is not None for item in items)
    box_subjects = {
        type(i.subject).__name__ for i in items if isinstance(i, ElementPresentation)
    }
    line_subjects = {
        type(i.subject).__name__ for i in items if isinstance(i, LinePresentation)
    }
    assert {"PartDefinition", "PartUsage"} <= box_subjects  # Engine, e, w
    assert {"FeatureTyping", "ConnectionUsage"} <= line_subjects  # e:Engine, connect


def test_synthesized_diagrams_are_browsable_sysml2_diagrams():
    factory, root = _map(_MODEL)
    synthesize_diagrams(root)
    diagrams = list(factory.select(Diagram))
    assert diagrams and all(isinstance(d, SysML2Diagram) for d in diagrams)


def test_synthesis_is_idempotent():
    factory, root = _map(_MODEL)
    synthesize_diagrams(root)
    diagram_count = len(list(factory.select(Diagram)))
    item_counts = {d.id: len(list(d.ownedPresentation)) for d in factory.select(Diagram)}

    synthesize_diagrams(root)  # re-run
    assert len(list(factory.select(Diagram))) == diagram_count  # no new diagrams
    assert {
        d.id: len(list(d.ownedPresentation)) for d in factory.select(Diagram)
    } == item_counts  # no duplicated items
    assert synthesized_diagram_for(root) is not None


def test_empty_namespace_makes_no_diagram():
    factory, root = _map("package P { } package Q { part q; }")
    synthesize_diagrams(root)
    names = {d.name for d in factory.select(Diagram)}
    assert "P (synthesized)" not in names  # empty package -> no diagram
    assert "Q (synthesized)" in names


def test_layout_places_boxes_at_distinct_positions():
    factory, root = _map(_MODEL)
    synthesize_diagrams(root)
    boxes = [
        i
        for i in _diagram(factory, "P (synthesized)").ownedPresentation
        if isinstance(i, ElementPresentation)
    ]
    positions = {(round(i.matrix[4]), round(i.matrix[5])) for i in boxes}
    assert len(positions) == len(boxes)  # no two boxes overlap exactly
    assert positions != {(0.0, 0.0)}  # auto-layout moved them off the origin


def test_synthesis_persists_and_reloads(element_factory, saver, loader):
    map_package(parse(_MODEL), element_factory)
    synthesize_diagrams(_root(element_factory))
    before = {
        d.name: len(list(d.ownedPresentation)) for d in element_factory.select(Diagram)
    }
    loader(saver())
    after = {
        d.name: len(list(d.ownedPresentation)) for d in element_factory.select(Diagram)
    }
    assert before == after
    assert all(
        item.subject is not None
        for d in element_factory.select(Diagram)
        for item in d.ownedPresentation
    )


def test_deleting_a_subject_removes_its_synthesized_view():
    factory, root = _map(_MODEL)
    synthesize_diagrams(root)
    diagram = _diagram(factory, "P (synthesized)")
    usage = next(
        u for u in factory.select(sysml2.PartUsage) if u.declaredName == "w"
    )
    item = next(i for i in diagram.ownedPresentation if i.subject is usage)
    usage.unlink()
    assert item not in list(diagram.ownedPresentation)  # view cascades with its subject


def test_succession_and_flow_lines_anchor_to_their_step_items():
    # Successions/flows are binary connector lines; synthesis must anchor both
    # handles to the projected step items (they previously projected unanchored).
    factory, root = _map(
        "action def MakeTea { action heat; action steep; "
        "succession s1 first heat then steep; flow f1 from heat to steep; }"
    )
    action_def = next(
        a for a in factory.select(sysml2.ActionDefinition) if a.declaredName == "MakeTea"
    )
    diagram = synthesize_diagram(action_def, layout=False)
    lines = [
        i for i in diagram.ownedPresentation if isinstance(i, LinePresentation)
    ]
    assert {type(i).__name__ for i in lines} == {
        "SuccessionAsUsageItem",
        "FlowUsageItem",
    }
    for line in lines:
        for handle in (line.head, line.tail):
            cinfo = diagram.connections.get_connection(handle)
            assert cinfo is not None, f"{type(line).__name__} handle unanchored"
            assert cinfo.connected.subject.declaredName in ("heat", "steep")


def test_synthesize_diagram_returns_existing_when_already_synthesized():
    factory, root = _map(_MODEL)
    package = next(p for p in factory.select(kerml.Package))
    first = synthesize_diagram(package)
    again = synthesize_diagram(package)
    assert first is again and isinstance(first, SysML2Diagram)
