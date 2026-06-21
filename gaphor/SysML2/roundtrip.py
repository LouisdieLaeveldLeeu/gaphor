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
        for member in kk.members(namespace):
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

            # A feature direction is recorded as a SEPARATE entry (only when set),
            # so a directed usage's fingerprint differs from the undirected one
            # without changing the base usage tuple.
            if isinstance(member, kerml.Feature) and member.direction is not None:
                entries.add(
                    ("FeatureDirection", kk.qualified_name(member), str(member.direction))
                )

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
                    ("RequirementFrame", requirements.framed_concerns(member)),
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
                for tag, kind in (
                    ("RequirementAssume", requirements.Assumption),
                    ("RequirementRequire", requirements.Requirement),
                ):
                    for i, c in enumerate(
                        requirements.requirement_constraints(member, kind)
                    ):
                        entries.add((tag, req_qn, i, constraints.body_text(c) or ""))

    visit(root)
    return frozenset(entries)


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
        factory, result.unresolved_types, result.mistyped, result.unresolved_ends
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
