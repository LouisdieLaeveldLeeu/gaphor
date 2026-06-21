"""Requirement reqId / actor / stakeholder (Phase 6c).

A requirement's `reqId` is its KerML `declaredShortName` (written `<id>` or
`<'id'>`); `actor`/`stakeholder` are parameter features related by an
`ActorMembership` / `StakeholderMembership` (both KerML ParameterMemberships),
kept in declaration order. Covers parse, map, scoped parameter-type validation,
membership integrity, export, round-trip, persistence, and the reqId UI-edit.

Also pins the grammar fix that made these reachable: a requirement/constraint
USAGE with a type AND a body (`requirement r : R { ... }`) used to mis-lex the
`{` as a greedy body terminal; constraint bodies are now built from literal
braces so the parser disambiguates by context. Rows stay `alpha`.
"""

from __future__ import annotations

import pytest

from gaphor.core.modeling import ElementFactory
from gaphor.diagram.tests.fixtures import find
from gaphor.SysML2 import constraints, kerml, requirements, shortnames, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.export import export_namespace
from gaphor.SysML2.grammar import ast
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.propertypages import RequirementReqIdPropertyPage
from gaphor.SysML2.roundtrip import round_trip
from gaphor.SysML2.validation import has_errors, validate

import gaphor.SysML2.propertypages  # noqa: F401, E402


def _map(text: str):
    factory = ElementFactory()
    return factory, map_package(parse(text), factory)


def _req_def(factory, name):
    return next(
        d for d in factory.select(sysml2.RequirementDefinition) if d.declaredName == name
    )


# --- parse -------------------------------------------------------------------


def test_parse_reqid_bare_and_quoted():
    (bare,) = parse("requirement def <R1> R;").members
    assert bare.reqId == "R1"
    # A dotted/special id is written quoted; the quotes are not part of the value.
    (quoted,) = parse("requirement def <'1.1.3'> R;").members
    assert quoted.reqId == "1.1.3"


def test_parse_actor_and_stakeholder_clauses_in_order():
    (member,) = parse(
        "requirement def R { actor u : Person; stakeholder s; actor v; }"
    ).members
    assert member.actors == (
        ast.ActorClause(name="u", type_name=("Person",)),
        ast.ActorClause(name="v"),
    )
    assert member.stakeholders == (ast.StakeholderClause(name="s"),)


def test_parse_full_requirement_body():
    (member,) = parse(
        "requirement def <'1.1'> R { subject v : Vehicle; actor a; stakeholder s; "
        "assume constraint {x} require constraint {y} }"
    ).members
    assert member.reqId == "1.1"
    assert member.subject == ast.SubjectClause(name="v", type_name=("Vehicle",))
    assert member.actors == (ast.ActorClause(name="a"),)
    assert member.stakeholders == (ast.StakeholderClause(name="s"),)
    assert member.assume == ("x",) and member.require == ("y",)


def test_requirement_usage_with_type_and_body_parses():
    # Regression: a usage with a type AND a body used to mis-lex `{` as a greedy
    # constraint-body terminal.
    (member,) = parse("requirement r : R { actor a; }").members
    assert isinstance(member, ast.RequirementUsage)
    assert member.type_name == ("R",) and member.actors == (ast.ActorClause(name="a"),)


def test_constraint_usage_with_type_and_body_parses():
    # Same latent lexing issue for a plain constraint usage with a type + body.
    (member,) = parse("constraint c : C { x > 0 }").members
    assert isinstance(member, ast.ConstraintUsage)
    assert member.type_name == ("C",) and member.body == " x > 0 "


# --- map ---------------------------------------------------------------------


def test_reqid_mapped_to_declared_short_name():
    factory, _ = _map("requirement def <'1.1.3'> R;")
    R = _req_def(factory, "R")
    assert R.declaredShortName == "1.1.3"
    assert requirements.reqId(R) == "1.1.3"


def test_actor_and_stakeholder_mapped_via_memberships_in_order():
    factory, _ = _map(
        "part def Person;\n"
        "requirement def R { actor driver : Person; actor inspector; stakeholder owner; }"
    )
    R = _req_def(factory, "R")
    actors = list(requirements.actors(R))
    stakeholders = list(requirements.stakeholders(R))
    assert [a.declaredName for a in actors] == ["driver", "inspector"]
    assert [s.declaredName for s in stakeholders] == ["owner"]
    assert kk.feature_type(actors[0]).declaredName == "Person"
    assert len(list(factory.select(sysml2.ActorMembership))) == 2
    assert len(list(factory.select(sysml2.StakeholderMembership))) == 1


def test_actor_and_stakeholder_are_part_usages():
    # Per the pinned XMI, ActorMembership/StakeholderMembership own a PartUsage
    # parameter (not a bare Feature).
    factory, _ = _map("requirement def R { actor a; stakeholder s; }")
    R = _req_def(factory, "R")
    assert all(isinstance(a, sysml2.PartUsage) for a in requirements.actors(R))
    assert all(isinstance(s, sysml2.PartUsage) for s in requirements.stakeholders(R))


def test_actor_part_usage_typed_by_non_part_definition_is_reported():
    # An actor is a PartUsage, so its type must be a PartDefinition; an
    # attribute-definition type is the WRONG kind and is reported (not accepted as
    # "any Type"), via the shared kind-checked typing path.
    factory, result = _map(
        "attribute def Color;\nrequirement def R { actor a : Color; }"
    )
    assert result.mistyped  # recorded during mapping, no FeatureTyping created
    diagnostics = validate(factory, result.unresolved_types, result.mistyped)
    assert any(d.rule == "type-kind-mismatch" for d in diagnostics)


# --- validation --------------------------------------------------------------


def test_unresolved_actor_type_is_reported():
    factory, result = _map("requirement def R { actor a : Missing; }")
    R = _req_def(factory, "R")
    (actor,) = list(requirements.actors(R))
    assert result.unresolved_types.get(actor.id) == "Missing"
    diagnostics = validate(factory, result.unresolved_types, result.mistyped)
    assert any(d.rule == "usage-without-valid-type" for d in diagnostics)


@pytest.mark.parametrize(
    "membership_type",
    [sysml2.ActorMembership, sysml2.StakeholderMembership],
)
def test_appended_parameter_member_is_reported_model_derived(membership_type):
    # `memberElement` is relation-many; an APPENDED extra member (the correct
    # feature stays first) must be reported -- a first-value check would miss it.
    keyword = "actor" if membership_type is sysml2.ActorMembership else "stakeholder"
    factory, _ = _map(f"requirement def R {{ {keyword} a; }}")
    membership = next(iter(factory.select(membership_type)))
    membership.memberElement = factory.create(kerml.Package)  # appends a 2nd value
    assert len(list(membership.memberElement)) == 2
    assert any(d.rule == "broken-requirement-parameter" for d in validate(factory))


@pytest.mark.parametrize(
    "membership_type",
    [sysml2.ActorMembership, sysml2.StakeholderMembership],
)
def test_bare_feature_actor_stakeholder_member_is_reported(membership_type):
    # An actor/stakeholder member that is a bare Feature (not a PartUsage) is the
    # WRONG kind per the XMI and must be reported -- a Feature check would miss it.
    keyword = "actor" if membership_type is sysml2.ActorMembership else "stakeholder"
    factory, _ = _map(f"requirement def R {{ {keyword} a; }}")
    membership = next(iter(factory.select(membership_type)))
    for old in list(membership.memberElement):
        kerml.OwningMembership.memberElement.delete(membership, old)
    membership.memberElement = factory.create(kerml.Feature)  # not a PartUsage
    assert any(d.rule == "broken-requirement-parameter" for d in validate(factory))


def test_well_formed_requirement_validates_clean():
    factory, result = _map(
        "part def Person;\nrequirement def <'1.1'> R { actor a : Person; stakeholder s; }"
    )
    assert not result.unresolved_types
    assert not has_errors(validate(factory))


# --- export / round-trip -----------------------------------------------------


def test_export_emits_reqid_actor_stakeholder():
    _factory, result = _map(
        "part def Person;\nrequirement def <'1.1.3'> R "
        "{ actor a : Person; stakeholder s; }\n"
        "requirement <R2> r : R;"
    )
    text = export_namespace(result.root)
    assert (
        "requirement def <'1.1.3'> R { actor a : Person; stakeholder s; }" in text
    )
    # A reqId that is a bare identifier is emitted unquoted.
    assert "requirement <R2> r : R;" in text


def test_full_requirement_round_trips():
    result = round_trip(
        "part def Vehicle;\npart def Person;\n"
        "requirement def <'1.1.3'> MassReq { subject v : Vehicle; "
        "actor driver : Person; actor inspector; stakeholder owner : Person; "
        "assume constraint {v.mass > 0} require constraint {v.mass < maxMass} }\n"
        "requirement <R2> r : MassReq;"
    )
    assert result.preserved
    assert result.valid


def test_reqid_changes_the_fingerprint():
    assert round_trip("requirement r;").source_form != round_trip(
        "requirement <R1> r;"
    ).source_form


def test_actor_order_changes_the_fingerprint():
    assert round_trip(
        "requirement def R { actor a; actor b; }"
    ).source_form != round_trip(
        "requirement def R { actor b; actor a; }"
    ).source_form


def test_actor_vs_stakeholder_are_distinct_fingerprints():
    assert round_trip(
        "requirement def R { actor x; }"
    ).source_form != round_trip(
        "requirement def R { stakeholder x; }"
    ).source_form


# --- persistence -------------------------------------------------------------


def test_reqid_actor_stakeholder_survive_save_reload(element_factory, saver, loader):
    map_package(
        parse(
            "part def Person;\nrequirement def <'1.1.3'> R "
            "{ actor a : Person; stakeholder s; }"
        ),
        element_factory,
    )
    R_id = _req_def(element_factory, "R").id

    loader(saver())

    R = element_factory.lookup(R_id)
    assert requirements.reqId(R) == "1.1.3"
    assert [a.declaredName for a in requirements.actors(R)] == ["a"]
    assert [s.declaredName for s in requirements.stakeholders(R)] == ["s"]


# --- UI-edit (reqId) ---------------------------------------------------------


def test_reqid_property_page_sets_and_clears(element_factory, event_manager):
    R = element_factory.create(sysml2.RequirementDefinition)
    R.declaredName = "R"
    page = RequirementReqIdPropertyPage(R, event_manager)

    entry = find(page.construct(), "requirement-reqid")
    entry.set_text("1.1.3")
    assert requirements.reqId(R) == "1.1.3"

    entry.set_text("")  # clearing removes the reqId
    assert requirements.reqId(R) is None


def test_reqid_property_page_reflects_existing(element_factory, event_manager):
    R = element_factory.create(sysml2.RequirementUsage)
    requirements.set_reqId(R, "R7")
    page = RequirementReqIdPropertyPage(R, event_manager)

    entry = find(page.construct(), "requirement-reqid")
    assert entry.get_text() == "R7"


def test_reqid_property_page_accepts_special_chars(element_factory, event_manager):
    # The UI accepts any non-blank reqId; escaping on export makes it representable
    # (no boundary rejection needed), so a quote round-trips through export+parse.
    R = element_factory.create(sysml2.RequirementDefinition)
    R.declaredName = "R"
    page = RequirementReqIdPropertyPage(R, event_manager)
    entry = find(page.construct(), "requirement-reqid")
    entry.set_text("A'B")
    assert requirements.reqId(R) == "A'B"


# --- reqId short-name escaping (Phase 6c findings fix) ------------------------


@pytest.mark.parametrize(
    "value", ["R1", "1.1.3", "A'B", "A\\B", "a'b\\c", "with space", "a\\\\b"]
)
def test_short_name_encode_decode_round_trips(value):
    # `shortnames` is the single encode/decode authority: decode(encode(x)) == x.
    assert shortnames.decode(shortnames.encode(value)) == value


def test_identifier_reqid_is_unquoted_others_quoted():
    assert shortnames.encode("R1") == "R1"
    assert shortnames.encode("1.1.3") == "'1.1.3'"
    assert shortnames.encode("A'B") == "'A\\'B'"  # quote escaped
    assert shortnames.encode("A\\B") == "'A\\\\B'"  # backslash escaped


@pytest.mark.parametrize("value", ["A'B", "A\\B", "1.1.3", "x'y\\z"])
def test_reqid_with_special_chars_parses_maps_and_round_trips(value):
    src = f"requirement def <{shortnames.encode(value)}> Rx;"
    (member,) = parse(src).members
    assert member.reqId == value

    factory, result = _map(src)
    assert requirements.reqId(_req_def(factory, "Rx")) == value
    # full export -> re-parse keeps the value
    (reparsed,) = parse(export_namespace(result.root)).members
    assert reparsed.reqId == value


def test_reqid_with_quote_exports_escaped():
    factory, result = _map("requirement def R;")
    requirements.set_reqId(_req_def(factory, "R"), "A'B")
    assert "<'A\\'B'>" in export_namespace(result.root)


def test_unterminated_short_name_escape_is_syntax_error():
    # `<'A\'>` -- the `\'` escapes the closing quote, leaving the name unterminated.
    with pytest.raises(SyntaxError):
        parse("requirement def <'A\\'> R;")


def test_blank_reqid_clears_to_none():
    factory, _ = _map("requirement def R;")
    R = _req_def(factory, "R")
    requirements.set_reqId(R, "X")
    assert requirements.reqId(R) == "X"
    requirements.set_reqId(R, "")  # blank clears
    assert requirements.reqId(R) is None
