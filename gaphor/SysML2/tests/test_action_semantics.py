"""Action semantics (Phase 7): action bodies, nested steps, directed parameters,
succession, and flow.

An action definition/usage may carry a BODY of nested members -- steps (nested
action usages), directed `in`/`out` parameters, other usages, plus successions
(`succession [name] first A then B`) and flows (`flow [name] from A to B`) -- owned
as the action's FEATURES via FeatureMembership. Succession/flow are binary
connector usages (SuccessionAsUsage -> KerML Succession; FlowUsage -> KerML Flow)
that reuse the connector source/target ends. Covers parse, map, scoped end
resolution, validation, export, round-trip, persistence, and diagram projection.
Advanced action nodes (if/for/fork/join/accept/send/assign), `flow def`, and item
payloads are out of scope; the Action rows stay `alpha`.
"""

from __future__ import annotations

import pytest

from gaphor.core.modeling import Diagram, ElementFactory
from gaphor.diagram.drop import drop
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.export import export_namespace
from gaphor.SysML2.grammar import ast
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.roundtrip import round_trip
from gaphor.SysML2.validation import has_errors, validate

import gaphor.SysML2.diagramitems  # noqa: F401, E402
import gaphor.SysML2.drop  # noqa: F401, E402


def _map(text: str):
    factory = ElementFactory()
    return factory, map_package(parse(text), factory)


def _action_def(factory, name):
    return next(
        a for a in factory.select(sysml2.ActionDefinition) if a.declaredName == name
    )


def _validate(factory, result):
    return validate(
        factory,
        result.unresolved_types,
        result.mistyped,
        result.unresolved_ends,
        result.unresolved_frame_refs,
    )


# --- parse -------------------------------------------------------------------


def test_parse_action_body_with_members():
    (member,) = parse(
        "action def Boil { in attribute t; action heat; action stir : Sub; }"
    ).members
    assert isinstance(member, ast.ActionDefinition)
    assert [type(m).__name__ for m in member.members] == [
        "AttributeUsage",
        "ActionUsage",
        "ActionUsage",
    ]
    assert member.members[0].direction == "in"


def test_parse_succession_and_flow():
    (member,) = parse(
        "action def A { action h; action s; "
        "succession x first h then s; flow from h to s; }"
    ).members
    succ, flow = member.members[2], member.members[3]
    assert isinstance(succ, ast.SuccessionUsage)
    assert succ.name == "x" and succ.source == ("h",) and succ.target == ("s",)
    assert isinstance(flow, ast.FlowUsage)
    assert flow.name is None and flow.source == ("h",) and flow.target == ("s",)


def test_empty_action_def_has_no_body():
    (member,) = parse("action def A;").members
    assert member.members == ()


# --- map ---------------------------------------------------------------------


def test_action_body_members_owned_as_features():
    factory, _ = _map(
        "action def Sub;\naction def Boil { in attribute t; action heat; action stir : Sub; }"
    )
    Boil = _action_def(factory, "Boil")
    members = {m.declaredName: m for m in kk.members(Boil)}
    assert set(members) == {"t", "heat", "stir"}
    # owned via FeatureMembership (the action's features), not plain OwningMembership
    assert all(
        isinstance(r, kerml.FeatureMembership)
        for r in Boil.ownedRelationship
        if isinstance(r, kerml.OwningMembership)
    )
    assert members["t"].direction == kerml.FeatureDirectionKind("in")
    assert kk.feature_type(members["stir"]).declaredName == "Sub"


def test_succession_and_flow_ends_resolve_in_action_scope():
    factory, result = _map(
        "action def A { action h; action s; "
        "succession first h then s; flow from h to s; }"
    )
    succ = next(iter(factory.select(sysml2.SuccessionAsUsage)))
    flow = next(iter(factory.select(sysml2.FlowUsage)))
    assert kk._single(succ.source).declaredName == "h"
    assert kk._single(succ.target).declaredName == "s"
    assert kk._single(flow.source).declaredName == "h"
    assert kk._single(flow.target).declaredName == "s"
    assert not result.unresolved_ends


def test_well_formed_action_validates_clean():
    factory, result = _map(
        "action def Sub;\naction def Boil { action heat; action stir : Sub; "
        "succession first heat then stir; }"
    )
    assert not result.unresolved_types and not result.unresolved_ends
    assert not has_errors(_validate(factory, result))


# --- validation --------------------------------------------------------------


@pytest.mark.parametrize(
    "src",
    [
        "action def A { action h; succession first h then missing; }",
        "action def A { action h; flow from h to missing; }",
    ],
)
def test_unresolved_succession_flow_end_is_reported(src):
    factory, result = _map(src)
    assert result.unresolved_ends
    assert any(d.rule == "broken-connection-end" for d in _validate(factory, result))


def test_incomplete_succession_is_reported_model_derived():
    # A one-ended succession (here via API mutation) has no valid textual form.
    factory, _ = _map("action def A { action h; action s; succession first h then s; }")
    succ = next(iter(factory.select(sysml2.SuccessionAsUsage)))
    for old in list(succ.target):
        kerml.Relationship.target.delete(succ, old)
    assert any(d.rule == "incomplete-connection" for d in validate(factory))


def test_non_feature_flow_end_is_reported_model_derived():
    factory, _ = _map("action def A { action h; action s; flow from h to s; }")
    flow = next(iter(factory.select(sysml2.FlowUsage)))
    for old in list(flow.target):
        kerml.Relationship.target.delete(flow, old)
    flow.target = factory.create(kerml.Package)  # a non-feature end
    assert any(d.rule == "non-feature-connection-end" for d in validate(factory))


# --- export / round-trip -----------------------------------------------------


def test_export_emits_action_body_succession_flow():
    _factory, result = _map(
        "attribute def Real;\naction def Sub;\n"
        "action def Boil { in attribute t : Real; action heat; action stir : Sub; "
        "succession s1 first heat then stir; flow from heat to stir; }"
    )
    text = export_namespace(result.root)
    assert "action def Boil {" in text
    assert "in attribute t : Real;" in text
    assert "action stir : Sub;" in text
    assert "succession s1 first heat then stir;" in text
    assert "flow from heat to stir;" in text


def test_action_semantics_round_trip():
    result = round_trip(
        "package P {\n"
        "  attribute def Real;\n"
        "  action def Sub;\n"
        "  action def Boil {\n"
        "    in attribute t : Real;\n"
        "    out part result;\n"
        "    action heat;\n"
        "    action stir : Sub;\n"
        "    succession s1 first heat then stir;\n"
        "    flow from heat to stir;\n"
        "  }\n"
        "  action a : Boil;\n"
        "}"
    )
    assert result.preserved
    assert result.valid


def test_body_vs_no_body_distinct_fingerprints():
    assert round_trip("action def A;").source_form != round_trip(
        "action def A { action s; }"
    ).source_form


def test_succession_vs_flow_distinct_fingerprints():
    assert round_trip(
        "action def A { action h; action s; succession first h then s; }"
    ).source_form != round_trip(
        "action def A { action h; action s; flow from h to s; }"
    ).source_form


# --- persistence -------------------------------------------------------------


def test_action_body_survives_save_reload(element_factory, saver, loader):
    map_package(
        parse(
            "action def Sub;\naction def Boil { in attribute t; action heat; "
            "action stir : Sub; succession first heat then stir; flow from heat to stir; }"
        ),
        element_factory,
    )
    Boil_id = _action_def(element_factory, "Boil").id

    loader(saver())

    Boil = element_factory.lookup(Boil_id)
    members = list(kk.members(Boil))
    # named steps/parameters plus the anonymous succession + flow
    assert {m.declaredName for m in members if m.declaredName} == {"t", "heat", "stir"}
    assert any(isinstance(m, sysml2.SuccessionAsUsage) for m in members)
    assert any(isinstance(m, sysml2.FlowUsage) for m in members)
    succ = next(iter(element_factory.select(sysml2.SuccessionAsUsage)))
    assert kk._single(succ.source).declaredName == "heat"
    assert kk._single(succ.target).declaredName == "stir"


# --- diagram -----------------------------------------------------------------


@pytest.mark.parametrize(
    "src,cls",
    [
        ("action def Boil { action heat; }", sysml2.ActionDefinition),
        (
            "action def Boil { action h; action s; succession first h then s; }",
            sysml2.SuccessionAsUsage,
        ),
        (
            "action def Boil { action h; action s; flow from h to s; }",
            sysml2.FlowUsage,
        ),
    ],
)
def test_action_constructs_project_and_survive_reload(
    element_factory, saver, loader, src, cls
):
    map_package(parse(src), element_factory)
    element = next(iter(element_factory.select(cls)))
    diagram = element_factory.create(Diagram)
    item = drop(element, diagram, 0, 0)
    assert item is not None and item.subject is element
    eid = element.id

    loader(saver())

    assert element_factory.lookup(eid) is not None
