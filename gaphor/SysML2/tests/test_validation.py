"""M2 sub-step 4: scoped structural + typing validation for the tracer."""

from __future__ import annotations

import pytest

from gaphor.core.modeling import ElementFactory
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.validation import Severity, has_errors, validate


def _rules(diagnostics):
    return {d.rule for d in diagnostics}


def test_valid_tracer_model_has_no_errors(element_factory):
    result = map_package(
        parse("part def Engine;\npart vehicleEngine : Engine;"), element_factory
    )
    diagnostics = validate(element_factory, result.unresolved_types)
    assert not has_errors(diagnostics)


def test_unresolved_type_is_reported(element_factory):
    result = map_package(parse("part p : Missing;"), element_factory)
    diagnostics = validate(element_factory, result.unresolved_types)
    assert "usage-without-valid-type" in _rules(diagnostics)
    assert has_errors(diagnostics)


def test_duplicate_name_is_reported(element_factory):
    result = map_package(
        parse("part def Engine;\npart def Engine;"), element_factory
    )
    diagnostics = validate(element_factory, result.unresolved_types)
    assert "duplicate-name" in _rules(diagnostics)
    assert has_errors(diagnostics)


def test_unresolved_import_is_reported(element_factory):
    ns = element_factory.create(kerml.Namespace)
    ns.declaredName = "Client"
    imp = element_factory.create(kerml.Import)
    # An import owned by the namespace but with no target element.
    ns.ownedRelationship = imp
    imp.owningRelatedElement = ns

    diagnostics = validate(element_factory)
    assert "unresolved-import" in _rules(diagnostics)
    assert has_errors(diagnostics)


def test_resolved_import_is_not_reported(element_factory):
    importer = element_factory.create(kerml.Namespace)
    imported = element_factory.create(kerml.Element)
    imp = element_factory.create(kerml.Import)
    kk.add_import(importer, imported, imp)

    diagnostics = validate(element_factory)
    assert "unresolved-import" not in _rules(diagnostics)


def test_missing_owner_is_reported(element_factory):
    # An OwningMembership that references a member but is not wired to any
    # namespace (no owningRelatedElement), so the member has no owning namespace.
    membership = element_factory.create(kerml.OwningMembership)
    member = element_factory.create(kerml.Element)
    member.declaredName = "Orphan"
    membership.memberElement = member
    member.owningRelationship = membership  # owned, but no owning namespace

    diagnostics = validate(element_factory)
    assert "missing-owner" in _rules(diagnostics)
    assert has_errors(diagnostics)


def test_attribute_usage_unresolved_type_is_reported(element_factory):
    # Regression: the rule must cover AttributeUsage, not only PartUsage.
    result = map_package(parse("attribute m : Missing;"), element_factory)
    diagnostics = validate(element_factory, result.unresolved_types)
    assert "usage-without-valid-type" in _rules(diagnostics)
    assert has_errors(diagnostics)


def test_valid_action_tracer_model_has_no_errors(element_factory):
    result = map_package(
        parse("action def Brake;\naction emergencyBrake : Brake;"), element_factory
    )
    diagnostics = validate(element_factory, result.unresolved_types)
    assert not has_errors(diagnostics)


def test_action_usage_unresolved_type_is_reported(element_factory):
    # The usage-without-valid-type rule must cover ActionUsage too.
    result = map_package(parse("action a : Missing;"), element_factory)
    diagnostics = validate(element_factory, result.unresolved_types)
    assert "usage-without-valid-type" in _rules(diagnostics)
    assert has_errors(diagnostics)


def test_valid_requirement_tracer_model_has_no_errors(element_factory):
    result = map_package(
        parse(
            "constraint def Limit;\nconstraint c : Limit;\n"
            "requirement def MassReq;\nrequirement r : MassReq;"
        ),
        element_factory,
    )
    diagnostics = validate(element_factory, result.unresolved_types)
    assert not has_errors(diagnostics)


def test_requirement_usage_unresolved_type_is_reported(element_factory):
    # The usage-without-valid-type rule must cover RequirementUsage too.
    result = map_package(parse("requirement r : Missing;"), element_factory)
    diagnostics = validate(element_factory, result.unresolved_types)
    assert "usage-without-valid-type" in _rules(diagnostics)
    assert has_errors(diagnostics)


def test_constraint_usage_unresolved_type_is_reported(element_factory):
    result = map_package(parse("constraint c : Missing;"), element_factory)
    diagnostics = validate(element_factory, result.unresolved_types)
    assert "usage-without-valid-type" in _rules(diagnostics)
    assert has_errors(diagnostics)


def test_typing_by_non_type_is_reported_not_crashed():
    # Regression: a name that resolves to a non-Type (a Package) must be a
    # diagnostic, not a TypeError crash in the mapper.
    for src in ("package P; attribute m : P;", "package P; part p : P;"):
        f = ElementFactory()
        result = map_package(parse(src), f)  # must not raise
        diagnostics = validate(f, result.unresolved_types)
        assert "usage-without-valid-type" in _rules(diagnostics), src
        assert has_errors(diagnostics), src


def test_broken_typing_in_persisted_model_is_reported(element_factory):
    # Model-derived rule (no mapping context): deleting the definition leaves an
    # orphaned FeatureTyping with an empty `type`, which must be reported.
    result = map_package(
        parse("part def Engine;\npart vehicleEngine : Engine;"), element_factory
    )
    engine = result.elements_by_name["Engine"]
    engine.unlink()

    # No mapping context passed -- this must be caught from the model alone.
    diagnostics = validate(element_factory)
    assert "usage-without-valid-type" in _rules(diagnostics)
    assert has_errors(diagnostics)


def test_untyped_usage_is_not_an_error(element_factory):
    result = map_package(parse("part p;"), element_factory)
    diagnostics = validate(element_factory, result.unresolved_types)
    assert not has_errors(diagnostics)


def test_severity_vocabulary_is_the_conformance_split(element_factory):
    result = map_package(parse("part p : Missing;"), element_factory)
    diagnostics = validate(element_factory, result.unresolved_types)
    assert all(isinstance(d.severity, Severity) for d in diagnostics)
    # All four M2 rules are ERROR-class per the conformance policy.
    assert all(d.severity is Severity.ERROR for d in diagnostics)


# --- cross-kind typing: a usage typed by the wrong definition kind -----------


@pytest.mark.parametrize(
    "src",
    [
        "part def PD;\nattribute a : PD;",
        "attribute def AD;\npart p : AD;",
        "part def PD;\naction a : PD;",
        "action def AcD;\npart p : AcD;",
        "requirement def RD;\nconstraint c : RD;",
        "constraint def CD;\nrequirement r : CD;",
        "attribute def AD;\nconstraint c : AD;",
        "part def PD;\nport p : PD;",
        "port def Fuel;\npart p : Fuel;",
    ],
)
def test_cross_kind_typing_is_reported_not_accepted(element_factory, src):
    # A usage typed by a resolvable Type of the WRONG kind must be a
    # type-kind-mismatch error, and must NOT create a FeatureTyping.
    result = map_package(parse(src), element_factory)
    diagnostics = validate(
        element_factory, result.unresolved_types, result.mistyped
    )
    assert "type-kind-mismatch" in _rules(diagnostics)
    assert has_errors(diagnostics)
    assert element_factory.lselect(kerml.FeatureTyping) == []


@pytest.mark.parametrize(
    "src",
    [
        "part def PD;\npart p : PD;",
        "attribute def AD;\nattribute a : AD;",
        "action def AcD;\naction a : AcD;",
        "constraint def CD;\nconstraint c : CD;",
        "requirement def RD;\nrequirement r : RD;",
        "port def Fuel;\nport p : Fuel;",
    ],
)
def test_same_kind_typing_is_accepted(element_factory, src):
    result = map_package(parse(src), element_factory)
    diagnostics = validate(
        element_factory, result.unresolved_types, result.mistyped
    )
    assert "type-kind-mismatch" not in _rules(diagnostics)
    assert not has_errors(diagnostics)
    assert len(element_factory.lselect(kerml.FeatureTyping)) == 1


def test_cross_kind_typing_creates_no_typing_in_mapper(element_factory):
    # Mapper-level: the wrong-kind type is recorded in `mistyped`, not stored.
    result = map_package(
        parse("attribute def AD;\npart p : AD;"), element_factory
    )
    assert element_factory.lselect(kerml.FeatureTyping) == []
    p = result.elements_by_name["p"]
    assert p.id in result.mistyped
    assert result.mistyped[p.id][1] == "AttributeDefinition"


# --- model-derived: a wrong-kind FeatureTyping already present in the model ---


def test_model_derived_check_catches_wrong_kind_typing_via_api(element_factory):
    # A wrong-kind typing injected through the kernel API (or a hand-edited /
    # persisted .gaphor) must be caught by validate(factory) WITHOUT any mapping
    # context -- the mapping-context rule alone would miss it.
    attribute_definition = element_factory.create(sysml2.AttributeDefinition)
    part_usage = element_factory.create(sysml2.PartUsage)
    part_usage.declaredName = "p"
    kk.set_feature_type(part_usage, attribute_definition)

    diagnostics = validate(element_factory)  # no mapping context

    assert "type-kind-mismatch" in _rules(diagnostics)
    assert has_errors(diagnostics)


def test_model_derived_check_accepts_right_kind_typing_via_api(element_factory):
    part_definition = element_factory.create(sysml2.PartDefinition)
    part_usage = element_factory.create(sysml2.PartUsage)
    kk.set_feature_type(part_usage, part_definition)

    diagnostics = validate(element_factory)

    assert not has_errors(diagnostics)


def test_model_derived_check_ignores_bare_kernel_feature_typing(element_factory):
    # A bare kernel Feature typed by a Type is outside the SysML usage-kind
    # contract, so it must NOT be flagged (no false positive).
    type_ = element_factory.create(kerml.Type)
    feature = element_factory.create(kerml.Feature)
    kk.set_feature_type(feature, type_)

    diagnostics = validate(element_factory)

    assert "type-kind-mismatch" not in _rules(diagnostics)


def test_wrong_kind_typing_survives_reload_and_is_still_caught(
    element_factory, saver, loader
):
    # The model-derived verdict must persist: a wrong-kind typing saved to
    # .gaphor is still an error after reload (no mapping context either way).
    attribute_definition = element_factory.create(sysml2.AttributeDefinition)
    part_usage = element_factory.create(sysml2.PartUsage)
    part_usage.declaredName = "p"
    kk.set_feature_type(part_usage, attribute_definition)

    loader(saver())

    diagnostics = validate(element_factory)
    assert "type-kind-mismatch" in _rules(diagnostics)
    assert has_errors(diagnostics)
