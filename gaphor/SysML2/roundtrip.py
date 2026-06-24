"""Round-trip harness + canonical form (M2 sub-step 6).

The harness is the project's coverage dashboard: it drives a construct through
the full chain and asserts the model is preserved by comparing *canonical
forms*, never raw text or element ids (invariant 6 / the round-trip rule).

Canonical form here is a structural fingerprint of a namespace: for each member,
its kind, effective (qualified) name, and -- for a usage -- the qualified name of
its resolved type. It deliberately ignores element ids, declaration order, and
textual formatting, so equivalence means "same semantic structure", not "same
bytes".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO

from gaphor.core.modeling import ElementFactory
from gaphor.core.modeling.modelinglanguage import (
    CoreModelingLanguage,
    MockModelingLanguage,
)
import gaphor.storage as storage
from gaphor.SysML2 import conjugation
from gaphor.SysML2 import constraints
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import requirements
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.export import export_namespace
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.modelinglanguage import (
    KerMLModelingLanguage,
    SysML2ModelingLanguage,
)
from gaphor.SysML2.validation import Diagnostic, has_errors, validate


def canonical_form(root: kerml.Namespace) -> frozenset[tuple[str, ...]]:
    """A structural fingerprint of `root`, independent of ids/order/formatting.

    Recurses through packages; each entry's qualified name encodes the full
    nesting path, so nesting is captured without storing tree shape separately.
    """
    entries: set[tuple[str, ...]] = set()

    def visit(namespace: kerml.Namespace) -> None:
        # Imports are owned relationships (not members), recorded with their target,
        # wildcard, and visibility so a namespace's imports round-trip (Phase 5a).
        for relationship in namespace.ownedRelationship:
            if isinstance(relationship, kerml.Import):
                target = kk._single(relationship.target)
                entries.add(
                    (
                        "Import",
                        kk.qualified_name(namespace),
                        kk.qualified_name(target) if target is not None else "",
                        kk.is_import_all(relationship),
                        str(relationship.visibility),
                    )
                )
        # An alias is a non-owning membership (not an owned member), recorded with
        # its alias name, resolved target, and visibility so it round-trips and a
        # private alias differs from a public one (Phase 5b).
        for alias in kk.aliases(namespace):
            target = kk._single(alias.memberElement)
            entries.add(
                (
                    "Alias",
                    kk.qualified_name(namespace),
                    alias.memberName,
                    kk.qualified_name(target) if target is not None else "",
                    str(alias.visibility),
                )
            )
        for member in kk.members(namespace):
            # Read-only library proxies (value types, implicit bases) are reference
            # data the mapper materializes; they are invisible to the canonical form
            # (and to export), so skip them entirely -- no base or sub-entries.
            if kk.is_library_proxy(member):
                continue
            # Package check first (Part* are also Namespaces). ConnectionDefinition
            # / ConnectionUsage subclass PartDefinition / PartUsage, so the more
            # specific connection classes are matched before the part classes.
            if isinstance(member, kerml.Package):
                entries.add(("Package", kk.qualified_name(member)))
                visit(member)
            elif isinstance(member, sysml2.InterfaceDefinition):
                entries.add(("InterfaceDefinition", kk.qualified_name(member)))
            elif isinstance(member, sysml2.InterfaceUsage):
                source = kk._single(member.source)
                target = kk._single(member.target)
                entries.add(
                    (
                        "InterfaceUsage",
                        kk.qualified_name(member),
                        _usage_type_qualified_name(member) or "",
                        kk.qualified_name(source) if source is not None else "",
                        kk.qualified_name(target) if target is not None else "",
                    )
                )
            elif isinstance(member, sysml2.ConnectionDefinition):
                entries.add(("ConnectionDefinition", kk.qualified_name(member)))
            elif isinstance(member, sysml2.ConnectionUsage):
                source = kk._single(member.source)
                target = kk._single(member.target)
                entries.add(
                    (
                        "ConnectionUsage",
                        kk.qualified_name(member),
                        _usage_type_qualified_name(member) or "",
                        kk.qualified_name(source) if source is not None else "",
                        kk.qualified_name(target) if target is not None else "",
                    )
                )
            elif isinstance(member, sysml2.PartDefinition):
                entries.add(("PartDefinition", kk.qualified_name(member)))
            elif isinstance(member, sysml2.AttributeDefinition):
                entries.add(("AttributeDefinition", kk.qualified_name(member)))
            elif isinstance(member, sysml2.PartUsage):
                entries.add(
                    (
                        "PartUsage",
                        kk.qualified_name(member),
                        _usage_type_qualified_name(member) or "",
                    )
                )
            elif isinstance(member, sysml2.AttributeUsage):
                entries.add(
                    (
                        "AttributeUsage",
                        kk.qualified_name(member),
                        _usage_type_qualified_name(member) or "",
                    )
                )
            # FlowUsage IS an ActionUsage and SuccessionAsUsage IS a ConnectorAsUsage
            # -- binary connectors recorded with their resolved ends, matched before
            # ActionUsage so a flow is not fingerprinted as a plain action (Phase 7).
            elif isinstance(member, sysml2.FlowUsage):
                entries.add(_connector_entry("FlowUsage", member))
            elif isinstance(member, sysml2.SuccessionAsUsage):
                entries.add(_connector_entry("SuccessionAsUsage", member))
            elif isinstance(member, sysml2.ActionDefinition):
                entries.add(("ActionDefinition", kk.qualified_name(member)))
            elif isinstance(member, sysml2.ActionUsage):
                entries.add(
                    (
                        "ActionUsage",
                        kk.qualified_name(member),
                        _usage_type_qualified_name(member) or "",
                    )
                )
            # ConcernDefinition is a RequirementDefinition is a ConstraintDefinition
            # (and the usages likewise), so the more specific class is matched first.
            elif isinstance(member, sysml2.ConcernDefinition):
                entries.add(("ConcernDefinition", kk.qualified_name(member)))
            elif isinstance(member, sysml2.RequirementDefinition):
                entries.add(("RequirementDefinition", kk.qualified_name(member)))
            elif isinstance(member, sysml2.ConstraintDefinition):
                entries.add(("ConstraintDefinition", kk.qualified_name(member)))
            elif isinstance(member, sysml2.ConcernUsage):
                entries.add(
                    (
                        "ConcernUsage",
                        kk.qualified_name(member),
                        _usage_type_qualified_name(member) or "",
                    )
                )
            elif isinstance(member, sysml2.RequirementUsage):
                entries.add(
                    (
                        "RequirementUsage",
                        kk.qualified_name(member),
                        _usage_type_qualified_name(member) or "",
                    )
                )
            elif isinstance(member, sysml2.ConstraintUsage):
                entries.add(
                    (
                        "ConstraintUsage",
                        kk.qualified_name(member),
                        _usage_type_qualified_name(member) or "",
                    )
                )
            elif isinstance(member, sysml2.PortDefinition):
                entries.add(("PortDefinition", kk.qualified_name(member)))
            elif isinstance(member, sysml2.PortUsage):
                entries.add(
                    (
                        "PortUsage",
                        kk.qualified_name(member),
                        _port_usage_type_qualified_name(member) or "",
                    )
                )

            # Member visibility is a SEPARATE entry, recorded only when PRIVATE (the
            # member default is public), so a `private` member's fingerprint differs
            # from a public one without changing the base tuple (Phase 5a).
            membership = kk._single(member.owningRelationship)
            if (
                membership is not None
                and membership.visibility == kerml.VisibilityKind.private
            ):
                entries.add(("Visibility", kk.qualified_name(member), "private"))

            # A feature direction is recorded as a SEPARATE entry (only when set),
            # so a directed usage's fingerprint differs from the undirected one
            # without changing the base usage tuple.
            if isinstance(member, kerml.Feature) and member.direction is not None:
                entries.add(
                    ("FeatureDirection", kk.qualified_name(member), str(member.direction))
                )

            # Subclassification heritage (Phase 5c): each `:> Super` is a SEPARATE
            # entry (definition qn, supertype qn), so a specializing definition's
            # fingerprint differs from a plain one and the supertype links round-trip.
            # Implicit universal bases (Phase 5d) are EXCLUDED: `explicit_supertypes`
            # / `explicit_subsettings` drop the `Anything`/`things` roots, so the
            # implicit specialization never changes the fingerprint (it is not
            # written on export either).
            if isinstance(member, kerml.Type):
                for supertype in kk.explicit_supertypes(member):
                    entries.add(
                        (
                            "Subclassification",
                            kk.qualified_name(member),
                            kk.qualified_name(supertype),
                        )
                    )
            # Subsetting (Phase 5c): each `:> y` on a usage is a SEPARATE entry
            # (usage qn, subsetted-feature qn). Redefinition (Phase 5c-2): each
            # `:>> y` likewise (usage qn, redefined-feature qn).
            if isinstance(member, kerml.Feature):
                for subsetting in kk.explicit_subsettings(member):
                    target = kk._single(subsetting.subsettedFeature)
                    entries.add(
                        (
                            "Subsetting",
                            kk.qualified_name(member),
                            kk.qualified_name(target) if target is not None else "",
                        )
                    )
                for redefinition in kk.redefinitions(member):
                    target = kk._single(redefinition.redefinedFeature)
                    entries.add(
                        (
                            "Redefinition",
                            kk.qualified_name(member),
                            kk.qualified_name(target) if target is not None else "",
                        )
                    )
            # Recurse into a definition BODY (a part def is a Namespace with nested
            # members), like a package, so its body members round-trip (Phase 5c).
            if isinstance(member, sysml2.PartDefinition):
                visit(member)

            # A constraint body is likewise a SEPARATE entry (only when present),
            # so a constraint with a preserved body differs from one without.
            body = constraints.body_text(member)
            if body is not None:
                entries.add(("ConstraintBody", kk.qualified_name(member), body))

            # A requirement's reqId/subject/actor/stakeholder/assume/require parts
            # are SEPARATE entries (Phase 6b/6c); an ordinal keeps duplicate
            # actor/stakeholder/assume/require parts distinct and order-sensitive.
            if isinstance(
                member, (sysml2.RequirementDefinition, sysml2.RequirementUsage)
            ):
                req_qn = kk.qualified_name(member)
                req_id = requirements.reqId(member)
                if req_id is not None:
                    entries.add(("RequirementReqId", req_qn, req_id))
                subj = requirements.subject(member)
                if subj is not None:
                    entries.add(
                        (
                            "RequirementSubject",
                            req_qn,
                            subj.declaredName or "",
                            _usage_type_qualified_name(subj) or "",
                        )
                    )
                for tag, features in (
                    ("RequirementActor", requirements.actors(member)),
                    ("RequirementStakeholder", requirements.stakeholders(member)),
                ):
                    for i, feature in enumerate(features):
                        entries.add(
                            (
                                tag,
                                req_qn,
                                i,
                                feature.declaredName or "",
                                _usage_type_qualified_name(feature) or "",
                            )
                        )
                # A framed concern is a declared usage (name + optional type) OR a
                # reference to an existing concern; the referenced qualified name
                # distinguishes the two forms (Phase 6d).
                for i, concern in enumerate(requirements.framed_concerns(member)):
                    referenced = requirements.framed_concern_reference(concern)
                    entries.add(
                        (
                            "RequirementFrame",
                            req_qn,
                            i,
                            concern.declaredName or "",
                            _usage_type_qualified_name(concern) or "",
                            kk.qualified_name(referenced) if referenced is not None
                            else "",
                        )
                    )
                for tag, kind in (
                    ("RequirementAssume", requirements.Assumption),
                    ("RequirementRequire", requirements.Requirement),
                ):
                    for i, c in enumerate(
                        requirements.requirement_constraints(member, kind)
                    ):
                        entries.add((tag, req_qn, i, constraints.body_text(c) or ""))

            # An action body's nested members (steps, parameters, successions,
            # flows) are the action's FEATURES; recurse so they are fingerprinted
            # too (their qualified names encode the action path), like packages
            # (Phase 7).
            if isinstance(member, (sysml2.ActionDefinition, sysml2.ActionUsage)):
                visit(member)

    visit(root)
    return frozenset(entries)


def _connector_entry(tag: str, member: kerml.Element) -> tuple[str, ...]:
    """Canonical entry for a binary connector usage (succession / flow): its
    qualified name plus the resolved source/target qualified names (empty when an
    end is unset), so the connector and its ends round-trip (Phase 7)."""
    source = kk._single(member.source)
    target = kk._single(member.target)
    return (
        tag,
        kk.qualified_name(member),
        kk.qualified_name(source) if source is not None else "",
        kk.qualified_name(target) if target is not None else "",
    )


def _usage_type_qualified_name(usage: sysml2.PartUsage) -> str | None:
    for relationship in usage.ownedRelationship:
        if isinstance(relationship, kerml.FeatureTyping):
            definition = kk._single(relationship.type)
            if definition is not None:
                return kk.qualified_name(definition)
    return None


def _port_usage_type_qualified_name(usage: sysml2.PortUsage) -> str | None:
    """Like `_usage_type_qualified_name`, but renders a conjugated typing as
    `~<original>` so `: Fuel` and `: ~Fuel` are distinct, stable fingerprints
    (the conjugate itself is unnamed/implicit, so its qualified name is not used).
    """
    original = conjugation.conjugated_type_name(usage)
    if original is not None:
        return "~" + kk.qualified_name(original)
    return _usage_type_qualified_name(usage)


def _modeling_language() -> MockModelingLanguage:
    return MockModelingLanguage(
        CoreModelingLanguage(),
        KerMLModelingLanguage(),
        SysML2ModelingLanguage(),
    )


@dataclass
class RoundTripResult:
    source_form: frozenset[tuple[str, ...]]
    reloaded_form: frozenset[tuple[str, ...]]
    exported_text: str
    reexported_form: frozenset[tuple[str, ...]]
    # Diagnostics from validating the source model (before save). The harness
    # validates the reloaded model too and asserts it matches.
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def preserved(self) -> bool:
        return self.source_form == self.reloaded_form == self.reexported_form

    @property
    def valid(self) -> bool:
        return not has_errors(self.diagnostics)


def round_trip(text: str, root_name: str = "Root") -> RoundTripResult:
    """import -> validate -> save -> reload -> validate -> export -> re-parse.

    Compares canonical forms (structure, never ids/text) across the source,
    reloaded, and re-exported models, and runs validation on the source and the
    reloaded model -- asserting validation survives persistence too, so the
    harness exercises the full M2 chain (including validate), not just storage.
    """
    # import (text -> AST -> semantic model)
    factory = ElementFactory()
    result = map_package(parse(text), factory)
    result.root.declaredName = root_name
    source_form = canonical_form(result.root)
    # Full diagnostics use mapping context (e.g. an unresolvable declared type
    # name, which is only known at mapping time). The model-derived subset is
    # what can be recomputed from a persisted model with no mapping context.
    source_diagnostics = validate(
        factory,
        result.unresolved_types,
        result.mistyped,
        result.unresolved_ends,
        result.unresolved_frame_refs,
        result.ambiguous,
        result.unresolved_supertypes,
        result.unresolved_subsettings,
        result.unresolved_redefinitions,
        result.self_redefinitions,
    )
    source_model_diagnostics = validate(factory)
    root_id = result.root.id

    # save -> reload through .gaphor
    f = StringIO()
    storage.save(f, factory)
    data = f.getvalue()
    factory.flush()
    storage.load(
        StringIO(data), element_factory=factory, modeling_language=_modeling_language()
    )
    reloaded_root = factory.lookup(root_id)
    assert isinstance(reloaded_root, kerml.Namespace)
    reloaded_form = canonical_form(reloaded_root)
    # The MODEL-DERIVED verdict must survive persistence (validation is not
    # dependent on transient mapping state). Mapping-context-only diagnostics
    # (an unresolvable type name) legitimately do not persist -- after reload an
    # untyped usage is indistinguishable from one that never declared a type --
    # so they are intentionally excluded from this invariant.
    reloaded_diagnostics = validate(factory)
    assert has_errors(reloaded_diagnostics) == has_errors(source_model_diagnostics)

    # export -> re-parse -> re-map -> canonical form
    exported_text = export_namespace(reloaded_root)
    reexport_factory = ElementFactory()
    reexport_result = map_package(parse(exported_text), reexport_factory)
    reexport_result.root.declaredName = root_name
    reexported_form = canonical_form(reexport_result.root)

    return RoundTripResult(
        source_form=source_form,
        reloaded_form=reloaded_form,
        exported_text=exported_text,
        reexported_form=reexported_form,
        diagnostics=source_diagnostics,
    )
