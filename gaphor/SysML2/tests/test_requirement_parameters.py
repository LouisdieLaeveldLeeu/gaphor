"""Requirement parameters (Phase 6b): subject / assume / require.

A requirement body's `subject`, `assume`, and `require` parts are modeled
faithfully on the normative memberships (SubjectMembership;
RequirementConstraintMembership with a kind). assume/require constraints reuse the
Phase 6a opaque body mechanism. Rows stay `alpha`. Covers parse, map, scoped
subject-type validation, export, round-trip, persistence, and membership
integrity.
"""

from __future__ import annotations

from gaphor.core.modeling import ElementFactory
from gaphor.SysML2 import kerml, requirements, sysml2
from gaphor.SysML2 import constraints
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.export import export_namespace
from gaphor.SysML2.grammar import ast
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.roundtrip import round_trip
from gaphor.SysML2.validation import has_errors, validate


def _map(text: str):
    factory = ElementFactory()
    return factory, map_package(parse(text), factory)


def _req_def(factory, name):
    return next(
        d
        for d in factory.select(sysml2.RequirementDefinition)
        if d.declaredName == name
    )


# --- parse -------------------------------------------------------------------


def test_parse_requirement_with_parts():
    pkg = parse(
        "requirement def R { subject v : Vehicle; "
        "assume constraint {a} require constraint {b} require constraint {c} }"
    )
    assert pkg.members == (
        ast.RequirementDefinition(
            name="R",
            subject=ast.SubjectClause(name="v", type_name=("Vehicle",)),
            assume=("a",),
            require=("b", "c"),
        ),
    )


def test_requirement_without_body_has_no_parts():
    (member,) = parse("requirement r : R;").members
    assert member.subject is None and member.assume == () and member.require == ()


# --- map ---------------------------------------------------------------------


def test_subject_mapped_via_subject_membership():
    factory, _ = _map("part def Vehicle;\nrequirement def R { subject v : Vehicle; }")
    R = _req_def(factory, "R")
    subj = requirements.subject(R)
    assert isinstance(subj, kerml.Feature)
    assert subj.declaredName == "v"
    assert kk.feature_type(subj).declaredName == "Vehicle"
    assert len(list(factory.select(sysml2.SubjectMembership))) == 1


def test_assume_require_mapped_via_constraint_memberships():
    factory, _ = _map(
        "requirement def R { assume constraint {x > 0} require constraint {y < 1} }"
    )
    R = _req_def(factory, "R")
    assumed = list(requirements.requirement_constraints(R, requirements.Assumption))
    required = list(requirements.requirement_constraints(R, requirements.Requirement))
    assert [constraints.body_text(c) for c in assumed] == ["x > 0"]
    assert [constraints.body_text(c) for c in required] == ["y < 1"]
    # assume/require are ConstraintUsages distinguished by membership kind.
    assert all(isinstance(c, sysml2.ConstraintUsage) for c in assumed + required)


def test_requirement_usage_can_have_parts():
    factory, _ = _map("requirement r { require constraint {ok} }")
    r = next(iter(factory.select(sysml2.RequirementUsage)))
    assert [
        constraints.body_text(c)
        for c in requirements.requirement_constraints(r, requirements.Requirement)
    ] == ["ok"]


# --- validation (scoped subject reference) -----------------------------------


def test_resolved_subject_type_is_valid():
    factory, result = _map(
        "part def Vehicle;\nrequirement def R { subject v : Vehicle; }"
    )
    assert not result.unresolved_types
    assert not has_errors(validate(factory))


def test_unresolved_subject_type_is_reported():
    factory, result = _map("requirement def R { subject v : Missing; }")
    R = _req_def(factory, "R")
    subj = requirements.subject(R)
    assert result.unresolved_types.get(subj.id) == "Missing"
    diagnostics = validate(factory, result.unresolved_types, result.mistyped)
    assert any(d.rule == "usage-without-valid-type" for d in diagnostics)


def test_broken_subject_membership_is_reported_model_derived():
    # A SubjectMembership whose member is not a feature (here via API mutation) is
    # caught model-derived.
    factory, _ = _map("requirement def R { subject v; }")
    membership = next(iter(factory.select(sysml2.SubjectMembership)))
    # Replace the subject feature with a non-feature element.
    pkg = factory.create(kerml.Package)
    for old in list(membership.memberElement):
        kerml.OwningMembership.memberElement.delete(membership, old)
    membership.memberElement = pkg
    assert any(
        d.rule == "broken-requirement-parameter" for d in validate(factory)
    )


# --- export / round-trip -----------------------------------------------------


def test_export_emits_subject_assume_require():
    _factory, result = _map(
        "part def Vehicle;\nrequirement def R { subject v : Vehicle; "
        "assume constraint {v.mass > 0} require constraint {v.mass <= maxMass} }"
    )
    text = export_namespace(result.root)
    assert (
        "requirement def R { subject v : Vehicle; "
        "assume constraint {v.mass > 0} require constraint {v.mass <= maxMass} }"
    ) in text


def test_requirement_parameters_round_trip():
    result = round_trip(
        "part def Vehicle;\nrequirement def R { subject v : Vehicle; "
        "assume constraint {v.mass > 0} require constraint {v.mass <= maxMass} }\n"
        "requirement r : R;"
    )
    assert result.preserved
    assert result.valid


def test_parts_vs_no_parts_are_distinct_fingerprints():
    assert round_trip("requirement r;").source_form != round_trip(
        "requirement r { require constraint {x} }"
    ).source_form


def test_two_required_constraints_round_trip():
    result = round_trip(
        "requirement def R { require constraint {a} require constraint {b} }"
    )
    assert result.preserved
    assert result.valid


# --- persistence -------------------------------------------------------------


def test_parts_survive_save_reload(element_factory, saver, loader):
    map_package(
        parse(
            "part def Vehicle;\nrequirement def R { subject v : Vehicle; "
            "assume constraint {x > 0} }"
        ),
        element_factory,
    )
    R_id = _req_def(element_factory, "R").id

    loader(saver())

    R = element_factory.lookup(R_id)
    assert requirements.subject(R).declaredName == "v"
    assert [
        constraints.body_text(c)
        for c in requirements.requirement_constraints(R, requirements.Assumption)
    ] == ["x > 0"]
