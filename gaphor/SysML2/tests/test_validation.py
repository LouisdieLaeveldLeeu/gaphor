"""M2 sub-step 4: scoped structural + typing validation for the tracer."""

from __future__ import annotations

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
