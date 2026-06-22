"""The Concern construct and a requirement's framed concern (Phase 6d-1).

A ConcernDefinition IS a RequirementDefinition and a ConcernUsage IS a
RequirementUsage, so both reuse the requirement body (subject/assume/require/
actor/stakeholder/frame). A requirement's `frame concern <name> [: <C>]` owns a
ConcernUsage via a FramedConcernMembership (a RequirementConstraintMembership with
kind=requirement). The reference form (`frame <existing>`) is Phase 6d-2. Covers
parse, map, scoped typing, membership integrity, export, round-trip, persistence,
diagram projection, and UI-edit. Rows stay `alpha`.
"""

from __future__ import annotations

import pytest

from gaphor.core.modeling import Diagram, ElementFactory
from gaphor.diagram.drop import drop
from gaphor.diagram.tests.fixtures import find
from gaphor.SysML2 import kerml, requirements, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.export import export_namespace
from gaphor.SysML2.grammar import ast
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.propertypages import (
    ConstraintRequirementTypePropertyPage,
    RequirementReqIdPropertyPage,
)
from gaphor.SysML2.roundtrip import round_trip
from gaphor.SysML2.validation import has_errors, validate

import gaphor.SysML2.diagramitems  # noqa: F401, E402
import gaphor.SysML2.drop  # noqa: F401, E402
import gaphor.SysML2.propertypages  # noqa: F401, E402


def _map(text: str):
    factory = ElementFactory()
    return factory, map_package(parse(text), factory)


def _req_def(factory, name):
    return next(
        d for d in factory.select(sysml2.RequirementDefinition) if d.declaredName == name
    )


# --- parse -------------------------------------------------------------------


def test_parse_concern_definition_and_usage():
    pkg = parse("concern def <C1> Safety { stakeholder s; }\nconcern c : Safety;")
    cdef, cusage = pkg.members
    assert isinstance(cdef, ast.ConcernDefinition)
    assert cdef.reqId == "C1" and cdef.stakeholders == (ast.StakeholderClause("s"),)
    assert isinstance(cusage, ast.ConcernUsage)
    assert cusage.type_name == ("Safety",)


def test_parse_frame_clause_declare_forms():
    (member,) = parse(
        "requirement def R { frame concern safety : Safety; frame concern adhoc; }"
    ).members
    assert member.framedConcerns == (
        ast.FrameClause(name="safety", type_name=("Safety",)),
        ast.FrameClause(name="adhoc"),
    )


# --- map ---------------------------------------------------------------------


def test_concern_definition_and_usage_mapped_and_typed():
    factory, result = _map("concern def Safety;\nconcern c : Safety;")
    assert any(
        d.declaredName == "Safety" for d in factory.select(sysml2.ConcernDefinition)
    )
    usage = next(iter(factory.select(sysml2.ConcernUsage)))
    assert kk.feature_type(usage).declaredName == "Safety"
    assert not result.unresolved_types and not result.mistyped


def test_frame_builds_concern_usage_via_framed_concern_membership():
    factory, _ = _map(
        "concern def Safety;\n"
        "requirement def R { frame concern safety : Safety; frame concern adhoc; }"
    )
    R = _req_def(factory, "R")
    framed = list(requirements.framed_concerns(R))
    assert [c.declaredName for c in framed] == ["safety", "adhoc"]
    assert all(isinstance(c, sysml2.ConcernUsage) for c in framed)
    assert kk.feature_type(framed[0]).declaredName == "Safety"
    membership = next(iter(factory.select(sysml2.FramedConcernMembership)))
    assert membership.kind == sysml2.RequirementConstraintKind.requirement


def test_frame_is_not_read_as_a_require_constraint():
    # FramedConcernMembership IS a RequirementConstraintMembership (kind=requirement),
    # but a framed concern must NOT show up among the `require` constraints.
    factory, _ = _map(
        "concern def Safety;\n"
        "requirement def R { frame concern safety : Safety; "
        "require constraint { x > 0 } }"
    )
    R = _req_def(factory, "R")
    assert [c.declaredName for c in requirements.framed_concerns(R)] == ["safety"]
    requires = list(requirements.requirement_constraints(R, requirements.Requirement))
    assert len(requires) == 1
    assert not isinstance(requires[0], sysml2.ConcernUsage)


def test_concern_reuses_requirement_body():
    factory, _ = _map(
        "part def Vehicle;\nconcern def Safety { subject v : Vehicle; stakeholder s; }"
    )
    Safety = next(iter(factory.select(sysml2.ConcernDefinition)))
    assert requirements.subject(Safety).declaredName == "v"
    assert [s.declaredName for s in requirements.stakeholders(Safety)] == ["s"]


# --- validation --------------------------------------------------------------


def test_well_formed_concern_and_frame_validate_clean():
    factory, result = _map(
        "concern def Safety;\nrequirement def R { frame concern safety : Safety; }"
    )
    assert not result.unresolved_types and not result.mistyped
    assert not has_errors(validate(factory))


def test_frame_typed_by_non_concern_definition_is_reported():
    # A framed concern is a ConcernUsage, so its type must be a ConcernDefinition;
    # a RequirementDefinition is the wrong kind.
    factory, result = _map(
        "requirement def Other;\nrequirement def R { frame concern fc : Other; }"
    )
    assert result.mistyped
    diagnostics = validate(factory, result.unresolved_types, result.mistyped)
    assert any(d.rule == "type-kind-mismatch" for d in diagnostics)


def test_concern_usage_typed_by_non_concern_definition_is_reported():
    factory, result = _map("requirement def Other;\nconcern c : Other;")
    assert result.mistyped
    diagnostics = validate(factory, result.unresolved_types, result.mistyped)
    assert any(d.rule == "type-kind-mismatch" for d in diagnostics)


def test_framed_concern_with_non_concern_member_is_reported_model_derived():
    factory, _ = _map(
        "concern def Safety;\nrequirement def R { frame concern fc : Safety; }"
    )
    membership = next(iter(factory.select(sysml2.FramedConcernMembership)))
    for old in list(membership.memberElement):
        kerml.OwningMembership.memberElement.delete(membership, old)
    membership.memberElement = factory.create(sysml2.ConstraintUsage)  # not a concern
    assert any(d.rule == "broken-requirement-parameter" for d in validate(factory))


def test_framed_concern_wrong_kind_is_reported_model_derived():
    factory, _ = _map(
        "concern def Safety;\nrequirement def R { frame concern fc : Safety; }"
    )
    membership = next(iter(factory.select(sysml2.FramedConcernMembership)))
    membership.kind = sysml2.RequirementConstraintKind.assumption  # must be requirement
    diagnostics = validate(factory)
    assert any(
        d.rule == "broken-requirement-parameter" and "framed concern kind" in d.message
        for d in diagnostics
    )


# --- export / round-trip -----------------------------------------------------


def test_export_emits_concern_and_frame():
    _factory, result = _map(
        "concern def <C1> Safety { stakeholder s; }\n"
        "requirement def R { frame concern safety : Safety; frame concern adhoc; }"
    )
    text = export_namespace(result.root)
    assert "concern def <C1> Safety { stakeholder s; }" in text
    assert (
        "requirement def R { frame concern safety : Safety; frame concern adhoc; }"
        in text
    )


def test_concern_and_frame_round_trip():
    result = round_trip(
        "part def Vehicle;\nconcern def <C1> Safety { subject v : Vehicle; stakeholder s; }\n"
        "requirement def <R1> SafetyReq { subject v : Vehicle; "
        "frame concern safety : Safety; frame concern adhoc; "
        "require constraint { v.mass < 1000 } }\n"
        "concern c : Safety;"
    )
    assert result.preserved
    assert result.valid


def test_frame_vs_no_frame_are_distinct_fingerprints():
    assert round_trip("requirement def R;").source_form != round_trip(
        "concern def C;\nrequirement def R { frame concern fc : C; }"
    ).source_form


def test_concern_def_vs_requirement_def_are_distinct_fingerprints():
    assert round_trip("requirement def R;").source_form != round_trip(
        "concern def R;"
    ).source_form


def test_frame_order_changes_the_fingerprint():
    assert round_trip(
        "concern def A;\nconcern def B;\n"
        "requirement def R { frame concern x : A; frame concern y : B; }"
    ).source_form != round_trip(
        "concern def A;\nconcern def B;\n"
        "requirement def R { frame concern y : B; frame concern x : A; }"
    ).source_form


# --- persistence -------------------------------------------------------------


def test_concern_and_frame_survive_save_reload(element_factory, saver, loader):
    map_package(
        parse(
            "concern def <C1> Safety { stakeholder s; }\n"
            "requirement def R { frame concern safety : Safety; }"
        ),
        element_factory,
    )
    R_id = _req_def(element_factory, "R").id

    loader(saver())

    R = element_factory.lookup(R_id)
    framed = list(requirements.framed_concerns(R))
    assert [c.declaredName for c in framed] == ["safety"]
    assert isinstance(framed[0], sysml2.ConcernUsage)
    assert requirements.reqId(
        next(iter(element_factory.select(sysml2.ConcernDefinition)))
    ) == "C1"


# --- diagram -----------------------------------------------------------------


@pytest.mark.parametrize(
    "src,cls",
    [
        ("concern def Safety;", sysml2.ConcernDefinition),
        ("concern c : Safety;", sysml2.ConcernUsage),
    ],
)
def test_concern_projects_and_survives_reload(element_factory, saver, loader, src, cls):
    map_package(parse("concern def Safety;\n" + src), element_factory)
    element = next(
        e for e in element_factory.select(cls)
    )
    diagram = element_factory.create(Diagram)
    item = drop(element, diagram, 0, 0)
    assert item is not None and item.subject is element
    eid = element.id

    loader(saver())

    assert element_factory.lookup(eid) is not None


# --- UI-edit -----------------------------------------------------------------


def test_concern_usage_type_page_lists_concern_definitions(
    element_factory, event_manager
):
    map_package(parse("concern def Safety;\nconcern c : Safety;"), element_factory)
    c = next(iter(element_factory.select(sysml2.ConcernUsage)))
    page = ConstraintRequirementTypePropertyPage(c, event_manager)
    assert page._definition_type is sysml2.ConcernDefinition
    dropdown = find(page.construct(), "constraint-usage-type")
    labels = {
        dropdown.get_model().get_item(i).label
        for i in range(dropdown.get_model().get_n_items())
    }
    assert "Safety" in labels


# --- frame REFERENCE form (Phase 6d-2) ---------------------------------------


def test_parse_frame_reference_vs_declare():
    (member,) = parse(
        "requirement def R { frame existing; frame concern decl : C; frame pkg::c; }"
    ).members
    assert member.framedConcerns == (
        ast.FrameReference(target=("existing",)),
        ast.FrameClause(name="decl", type_name=("C",)),
        ast.FrameReference(target=("pkg", "c")),
    )


def test_frame_reference_builds_anonymous_usage_with_reference_subsetting():
    factory, result = _map(
        "concern def Safety;\nconcern globalSafety : Safety;\n"
        "requirement def R { frame globalSafety; }"
    )
    assert not result.unresolved_frame_refs
    R = _req_def(factory, "R")
    (framed,) = list(requirements.framed_concerns(R))
    assert isinstance(framed, sysml2.ConcernUsage)
    assert not framed.declaredName  # anonymous (a reference, not a declaration)
    referenced = requirements.framed_concern_reference(framed)
    assert isinstance(referenced, sysml2.ConcernUsage)
    assert referenced.declaredName == "globalSafety"


def test_frame_reference_and_declare_keep_order():
    factory, _ = _map(
        "concern def Safety;\nconcern g : Safety;\n"
        "requirement def R { frame g; frame concern localc : Safety; }"
    )
    R = _req_def(factory, "R")
    framed = list(requirements.framed_concerns(R))
    refs = [requirements.framed_concern_reference(c) for c in framed]
    assert refs[0] is not None and refs[0].declaredName == "g"  # reference first
    assert refs[1] is None and framed[1].declaredName == "localc"  # declare second


def test_well_formed_frame_reference_validates_clean():
    factory, result = _map(
        "concern def Safety;\nconcern g : Safety;\nrequirement def R { frame g; }"
    )
    assert not has_errors(
        validate(
            factory,
            result.unresolved_types,
            result.mistyped,
            result.unresolved_ends,
            result.unresolved_frame_refs,
        )
    )


def test_unresolved_frame_reference_is_reported():
    factory, result = _map("requirement def R { frame missingConcern; }")
    assert result.unresolved_frame_refs
    diagnostics = validate(
        factory,
        result.unresolved_types,
        result.mistyped,
        result.unresolved_ends,
        result.unresolved_frame_refs,
    )
    assert any(d.rule == "broken-frame-reference" for d in diagnostics)


@pytest.mark.parametrize(
    "src",
    [
        # resolves to a ConcernDefinition (a Type, not a usage) -> wrong kind
        "concern def Safety;\nrequirement def R { frame Safety; }",
        # resolves to a part usage (a Feature, but not a ConcernUsage) -> wrong kind
        "part p;\nrequirement def R { frame p; }",
    ],
)
def test_wrong_kind_frame_reference_is_reported(src):
    factory, result = _map(src)
    assert result.unresolved_frame_refs
    diagnostics = validate(
        factory,
        result.unresolved_types,
        result.mistyped,
        result.unresolved_ends,
        result.unresolved_frame_refs,
    )
    assert any(d.rule == "broken-frame-reference" for d in diagnostics)


def test_export_emits_frame_reference():
    _factory, result = _map(
        "concern def Safety;\nconcern g : Safety;\nrequirement def R { frame g; }"
    )
    text = export_namespace(result.root)
    assert "requirement def R { frame g; }" in text


def test_frame_reference_round_trips():
    result = round_trip(
        "concern def Safety;\nconcern g : Safety;\n"
        "requirement def R { frame g; frame concern localc : Safety; }"
    )
    assert result.preserved
    assert result.valid


def test_frame_reference_vs_declare_are_distinct_fingerprints():
    assert round_trip(
        "concern def C;\nconcern g : C;\nrequirement def R { frame g; }"
    ).source_form != round_trip(
        "concern def C;\nconcern g : C;\nrequirement def R { frame concern g : C; }"
    ).source_form


def test_frame_reference_survives_save_reload(element_factory, saver, loader):
    map_package(
        parse(
            "concern def Safety;\nconcern g : Safety;\nrequirement def R { frame g; }"
        ),
        element_factory,
    )
    R_id = _req_def(element_factory, "R").id

    loader(saver())

    R = element_factory.lookup(R_id)
    (framed,) = list(requirements.framed_concerns(R))
    referenced = requirements.framed_concern_reference(framed)
    assert isinstance(referenced, sysml2.ConcernUsage)
    assert referenced.declaredName == "g"


def test_add_reference_subsetting_helper(element_factory):
    a = element_factory.create(sysml2.ConcernUsage)
    b = element_factory.create(sysml2.ConcernUsage)
    subsetting = kk.add_reference_subsetting(a, b)
    assert kk.reference_subsetting(a) is subsetting
    assert kk._single(subsetting.referencedFeature) is b
    assert kk._single(subsetting.subsettingFeature) is a
    assert subsetting in a.ownedRelationship  # owned by the referencing feature


def _corrupt_frame_reference_to_part(factory):
    """Point a framed concern's ReferenceSubsetting at a PartUsage (a non-concern),
    as a stored/API-mutated model would -- returns the requirement's root."""
    R = _req_def(factory, "R")
    (framed,) = list(requirements.framed_concerns(R))
    subsetting = kk.reference_subsetting(framed)
    for old in list(subsetting.referencedFeature):
        kerml.ReferenceSubsetting.referencedFeature.delete(subsetting, old)
    part = factory.create(sysml2.PartUsage)
    part.declaredName = "p"
    subsetting.referencedFeature = part


def test_corrupted_frame_reference_is_reported_model_derived():
    # A ReferenceSubsetting pointing at a non-ConcernUsage must be caught WITHOUT
    # mapping context (a stored/API-mutated model), via exact-one semantics.
    factory, _ = _map(
        "concern def Safety;\nconcern g : Safety;\nrequirement def R { frame g; }"
    )
    _corrupt_frame_reference_to_part(factory)
    assert any(d.rule == "broken-frame-reference" for d in validate(factory))


def test_corrupted_frame_reference_not_exported_as_invalid_text():
    factory, result = _map(
        "concern def Safety;\nconcern g : Safety;\nrequirement def R { frame g; }"
    )
    _corrupt_frame_reference_to_part(factory)
    text = export_namespace(result.root)
    assert "frame" not in text  # the broken reference is skipped, not emitted
    assert "requirement def R;" in text


def test_multiple_reference_subsettings_on_a_framed_concern_is_reported():
    # `reference_subsetting` reads only the first match, so a SECOND appended
    # ReferenceSubsetting must be caught by the exactly-one integrity check --
    # otherwise validate passes and export silently drops the extra reference.
    factory, result = _map(
        "concern def C;\nconcern g : C;\nconcern h : C;\n"
        "requirement def R { frame g; }"
    )
    R = _req_def(factory, "R")
    (framed,) = list(requirements.framed_concerns(R))
    h = next(c for c in factory.select(sysml2.ConcernUsage) if c.declaredName == "h")
    kk.add_reference_subsetting(framed, h)  # append a SECOND reference (corruption)
    assert len(list(kk.reference_subsettings(framed))) == 2

    assert any(d.rule == "broken-frame-reference" for d in validate(factory))
    # export must not silently emit only the first reference.
    assert "frame g;" not in export_namespace(result.root)


def test_reqid_page_applies_to_concern(element_factory, event_manager):
    cdef = element_factory.create(sysml2.ConcernDefinition)
    cdef.declaredName = "Safety"
    page = RequirementReqIdPropertyPage(cdef, event_manager)
    entry = find(page.construct(), "requirement-reqid")
    entry.set_text("C1")
    assert requirements.reqId(cdef) == "C1"
