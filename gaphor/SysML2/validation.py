"""Scoped structural + typing validation for the SysML2 model.

Validation grows construct by construct (each rule tested); it started as the
four M2 rules and now also enforces kind-specific typing. Rules are ERROR severity
per the conformance policy (decision sec 4), except where noted (the
empty-constraint-body rule is a WARNING -- syntactically allowed, likely a
mistake):

- missing owner            -> structural integrity broken
- duplicate member name    -> name resolution would be ambiguous
- unresolved import        -> an outbound reference cannot be tracked
- usage without valid type -> a declared type name does not resolve to a Type
- broken typing            -> a FeatureTyping is missing an end (no type / no
                              typed feature), caught model-derived
- type-kind mismatch       -> a usage is typed by the wrong definition kind
                              (e.g. `part p : AttributeDefinition`); reported
                              both from mapping context and model-derived, so a
                              wrong-kind relation is caught whether it came from
                              text or was injected via the API / a reloaded model
- broken connection end    -> a connector endpoint did not resolve to a feature
                              (mapping context)
- non-feature connection   -> a connector source/target is set to a non-feature
                              (e.g. a definition); caught model-derived, since the
                              low-level diagram connect / API can store one
- incomplete connection    -> a binary connection has exactly one end set,
                              caught model-derived (no valid textual form)
- broken conjugation       -> a conjugated port typing does not resolve to a real
                              conjugate of a port definition (model-derived)
- empty constraint body    -> a preserved constraint body is empty/whitespace
                              (WARNING; model-derived). The body is opaque text,
                              not interpreted -- expression semantics are out of
                              scope.

Rules that need mapping context (unresolved-symbol, mapping-context kind
mismatch) take it as an argument; the rest are recomputed from the stored model
alone, so a reloaded `.gaphor` is validated without it. Name resolution stays
scoped: same-namespace and simple qualified-name only (no inheritance,
visibility, aliases, or feature chains).
"""

from __future__ import annotations

import enum
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from gaphor.core.modeling import ElementFactory
from gaphor.SysML2 import constraints
from gaphor.SysML2 import kerml
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2 import requirements
from gaphor.SysML2 import sysml2
from gaphor.SysML2.mapping import is_managed_usage_kind, type_matches_usage_kind


class Severity(enum.StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Diagnostic:
    severity: Severity
    rule: str
    message: str
    element_id: str | None = None


def validate(
    factory: ElementFactory,
    unresolved_types: dict[str, str] | None = None,
    mistyped: dict[str, tuple[str, str]] | None = None,
    unresolved_ends: dict[str, list[str]] | None = None,
    unresolved_frame_refs: dict[str, str] | None = None,
    ambiguous: dict[str, str] | None = None,
    unresolved_supertypes: dict[str, list[str]] | None = None,
    unresolved_subsettings: dict[str, str] | None = None,
    unresolved_redefinitions: dict[str, str] | None = None,
) -> list[Diagnostic]:
    """Run the scoped M2 validation rules over all elements in `factory`.

    `unresolved_types` maps a usage element id -> the declared type name that did
    not resolve during mapping (the mapper records these). The
    usage-without-valid-type rule reports them; a model loaded from `.gaphor`
    with no mapping context simply has none to report.

    `mistyped` maps a usage element id -> (declared type name, resolved-type kind)
    for a type that resolved but is the WRONG KIND for the usage (e.g.
    `part p : AttributeDefinition`). These also produce no FeatureTyping; the
    type-kind-mismatch rule reports them. Like unresolved types, this needs
    mapping context, so a reloaded model has none to report.

    `unresolved_ends` maps a connection element id -> the declared connector-end
    references that did not resolve to a feature (broken or kind-mismatched
    endpoints). The connection-end rule reports them; mapping context only.

    `unresolved_frame_refs` maps a framed-concern ConcernUsage id -> the
    `frame <ref>` name that did not resolve to a ConcernUsage (Phase 6d-2). The
    framed-concern-reference rule reports them; mapping context only.

    `ambiguous` maps an element id -> a (qualified) name that was visible from MORE
    THAN ONE import and so did not bind (Phase 5a). The ambiguous-name rule reports
    them; mapping context only.

    `unresolved_supertypes` maps a definition id -> the LIST of its `:> Super` names
    that did not resolve to a Classifier (a `:> A, B` with both bad reports both),
    `unresolved_subsettings` maps a usage id -> the `:> y` name that did not resolve
    to a Feature (Phase 5c), and `unresolved_redefinitions` a usage id -> the `:>> y`
    name that did not resolve (Phase 5c-2). The mapper records these (an AMBIGUOUS
    supertype/subsetted/redefined name goes to `ambiguous` instead, so there is no
    double report); mapping context only. Separately, `_check_broken_specializations`
    is MODEL-DERIVED and reports a persisted Subclassification/Subsetting/Redefinition
    whose end was cleared, independent of mapping context.
    """
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(_check_missing_owner(factory))
    diagnostics.extend(_check_duplicate_names(factory))
    diagnostics.extend(_check_unresolved_imports(factory))
    diagnostics.extend(_check_unresolved_aliases(factory, ambiguous or {}))
    diagnostics.extend(_check_broken_typing(factory))
    diagnostics.extend(
        _check_usage_without_valid_type(factory, unresolved_types or {})
    )
    diagnostics.extend(_check_type_kind_mismatch(factory, mistyped or {}))
    diagnostics.extend(_check_ambiguous_names(factory, ambiguous or {}))
    diagnostics.extend(_check_connection_ends(factory, unresolved_ends or {}))
    diagnostics.extend(_check_connection_end_integrity(factory))
    diagnostics.extend(_check_conjugated_typing(factory))
    diagnostics.extend(_check_constraint_body(factory))
    diagnostics.extend(_check_requirement_parameters(factory))
    diagnostics.extend(
        _check_frame_references(factory, unresolved_frame_refs or {})
    )
    diagnostics.extend(_check_feature_membership_members(factory))
    diagnostics.extend(
        _check_unresolved_specializations(unresolved_supertypes or {})
    )
    diagnostics.extend(_check_unresolved_subsettings(unresolved_subsettings or {}))
    diagnostics.extend(
        _check_unresolved_redefinitions(unresolved_redefinitions or {})
    )
    diagnostics.extend(_check_broken_specializations(factory))
    return diagnostics


def _check_requirement_parameters(factory: ElementFactory) -> Iterator[Diagnostic]:
    """A requirement's subject/actor/stakeholder/assume/require/frame memberships
    must own EXACTLY ONE member of the right kind.

    Model-derived (no mapping context): a `SubjectMembership` must own exactly one
    `Feature` (the subject parameter); an `ActorMembership` and `StakeholderMembership`
    must each own exactly one `PartUsage` (the pinned XMI types the actor/stakeholder
    parameter as a PartUsage, so a bare Feature is NOT sufficient); a
    `RequirementConstraintMembership` must own exactly one `ConstraintUsage` (the
    assumed/required constraint); and a `FramedConcernMembership` must own exactly
    one `ConcernUsage` AND carry kind=requirement (Phase 6d). `memberElement` is
    relation-many at runtime, so `_sole` is used (not first-value `_single`): a
    membership with zero, multiple (appended), or a wrong-kind member is reported.
    The textual mapper always builds these correctly; this is the safety net for a
    hand-edited/persisted .gaphor or an API mutation. The parameter's declared TYPE
    is validated by the usual unresolved-type rule (recorded during mapping).
    """
    for membership_type, label, member_kind, kind_name in (
        (sysml2.SubjectMembership, "subject", kerml.Feature, "feature"),
        (sysml2.ActorMembership, "actor", sysml2.PartUsage, "part usage"),
        (sysml2.StakeholderMembership, "stakeholder", sysml2.PartUsage, "part usage"),
    ):
        for membership in factory.select(membership_type):
            if not isinstance(_sole(membership.memberElement), member_kind):
                yield Diagnostic(
                    Severity.ERROR,
                    "broken-requirement-parameter",
                    f"requirement {label} is not exactly one {kind_name}",
                    membership.id,
                )
    # A FramedConcernMembership IS a RequirementConstraintMembership, so it is
    # handled separately and EXCLUDED from the constraint loop below.
    for membership in factory.select(sysml2.FramedConcernMembership):
        if not isinstance(_sole(membership.memberElement), sysml2.ConcernUsage):
            yield Diagnostic(
                Severity.ERROR,
                "broken-requirement-parameter",
                "requirement framed concern is not exactly one concern usage",
                membership.id,
            )
        if membership.kind != sysml2.RequirementConstraintKind.requirement:
            yield Diagnostic(
                Severity.ERROR,
                "broken-requirement-parameter",
                "framed concern kind must be 'requirement'",
                membership.id,
            )
    for membership in factory.select(sysml2.RequirementConstraintMembership):
        if isinstance(membership, sysml2.FramedConcernMembership):
            continue
        if not isinstance(_sole(membership.memberElement), sysml2.ConstraintUsage):
            yield Diagnostic(
                Severity.ERROR,
                "broken-requirement-parameter",
                f"requirement {membership.kind} is not exactly one constraint",
                membership.id,
            )


def _check_frame_references(
    factory: ElementFactory, unresolved_frame_refs: dict[str, str]
) -> Iterator[Diagnostic]:
    """A framed-concern REFERENCE (`frame <existing>`) must target a ConcernUsage
    (Phase 6d-2).

    Two complementary checks for DISJOINT cases (no double-reporting):

    - Mapping context: the mapper resolves `frame <ref>` nearest-first and, when a
      name does NOT resolve to a ConcernUsage (missing, or a wrong-kind target such
      as a ConcernDefinition or a part), records it WITHOUT creating a
      ReferenceSubsetting. Each such name is reported here. Like the other reference
      rules (unresolved types, connection ends) this needs mapping context, so a
      reloaded model has none to report.
    - Model-derived: when a ReferenceSubsetting DOES exist under a framed concern
      (a stored/API-mutated model the mapper never produced), its referenced
      feature must be EXACTLY ONE ConcernUsage (`_sole`, not first-value): a zero,
      multiple, or wrong-kind target is reported so a corrupted reference cannot
      validate clean and then export invalid text (e.g. `frame p;`).
    """
    for concern_id, name in unresolved_frame_refs.items():
        yield Diagnostic(
            Severity.ERROR,
            "broken-frame-reference",
            f"framed concern references {name!r}, which does not resolve to a "
            "concern usage",
            concern_id,
        )
    for membership in factory.select(sysml2.FramedConcernMembership):
        concern = _sole(membership.memberElement)
        if not isinstance(concern, sysml2.ConcernUsage):
            continue  # the membership-member kind is checked elsewhere
        if not requirements.is_referencing_frame(concern):
            continue  # a declared frame, or an unresolved import (mapping context)
        # A framed concern that owns a ReferenceSubsetting must be a WELL-FORMED
        # reference (the shared predicate export uses): exactly one subsetting to
        # exactly one ConcernUsage, and otherwise anonymous (no declaredName, no own
        # FeatureTyping). Otherwise export would silently drop the extra reference
        # or the declared name/type, so it is reported here instead.
        if requirements.framed_concern_reference(concern) is None:
            yield Diagnostic(
                Severity.ERROR,
                "broken-frame-reference",
                "framed concern reference must be a single anonymous reference to "
                "a concern usage",
                membership.id,
            )


def _check_feature_membership_members(
    factory: ElementFactory,
) -> Iterator[Diagnostic]:
    """A (plain) `FeatureMembership` relates a Type to one of its FEATURES, so its
    member must be EXACTLY ONE `Feature`.

    Model-derived safety net: an action body's feature members (steps, parameters,
    successions, flows) are owned via FeatureMembership, while nested
    definitions/packages are NON-features owned via OwningMembership; this guards a
    FeatureMembership wired to a non-feature outside the textual path (a hand-edited
    .gaphor or an API mutation). Only the EXACT type is checked: the
    Parameter/Subject/Actor/Stakeholder/RequirementConstraint/FramedConcern
    membership subtypes have their own kind-specific rules, so they are skipped here
    to avoid double-reporting.
    """
    for membership in factory.select(kerml.FeatureMembership):
        if type(membership) is not kerml.FeatureMembership:
            continue
        if not isinstance(_sole(membership.memberElement), kerml.Feature):
            yield Diagnostic(
                Severity.ERROR,
                "broken-feature-membership",
                "feature membership does not own exactly one feature",
                membership.id,
            )


def _check_constraint_body(factory: ElementFactory) -> Iterator[Diagnostic]:
    """A preserved constraint body must not be empty (basic well-formedness).

    Model-derived: a constraint body is preserved as opaque text in a
    `TextualRepresentation` (language `sysml`); the grammar already enforces the
    `{ }` delimiters, so the only well-formedness check left is that the body is
    not empty/whitespace-only (`constraint c { }`), which is reported as a
    WARNING (it is syntactically allowed but almost certainly a mistake). The body
    is NOT otherwise interpreted -- expression semantics are out of scope here.
    """
    for rep in factory.select(kerml.TextualRepresentation):
        if rep.language != constraints.BODY_LANGUAGE:
            continue
        if not (rep.body or "").strip():
            owner = kk.owning_namespace(rep)
            name = owner.declaredName if owner is not None else None
            yield Diagnostic(
                Severity.WARNING,
                "empty-constraint-body",
                f"constraint {name!r} has an empty body"
                if name
                else "constraint has an empty body",
                owner.id if owner is not None else rep.id,
            )


def _sole(values) -> kerml.Element | None:
    """The single element of a stored association, or None if it does not hold
    EXACTLY one. The conjugation ends are conceptually single-valued, but the
    generated associations are relation-many at runtime, so an API mutation can
    APPEND a second target. `_single` (first-only) would miss that; `_sole`
    returns None for both an empty and a multi-valued association so either is
    treated as broken."""
    items = list(values)
    return items[0] if len(items) == 1 else None


def _holds_only(values, expected) -> bool:
    """Whether a stored association holds EXACTLY the one `expected` element
    (not merely as its first value -- an appended extra target is a mismatch)."""
    return list(values) == [expected]


def _check_conjugated_typing(factory: ElementFactory) -> Iterator[Diagnostic]:
    """A conjugated port typing must be internally consistent across ALL its
    stored ends -- each holding EXACTLY its expected target, not merely navigable
    along one path nor merely correct in its first value.

    Model-derived (no mapping context): a `ConjugatedPortTyping` stores both the
    inherited FeatureTyping `type` AND the `conjugatedPortDefinition`, and the
    conjugate stores a `PortConjugation` with both the SysML `originalPortDefinition`
    and the KerML `Conjugation` ends (`originalType`/`conjugatedType`). The normal
    mapper/UI path sets each of these to a single, agreeing target, but a
    hand-edited/persisted .gaphor or an API mutation can store contradictory ends
    -- including an APPENDED extra target, since these generated associations are
    relation-many at runtime (`typing.type = power` appends rather than replaces).
    Every end is checked for exactly its expected target so such a model is
    reported, not silently accepted as a clean `~Fuel`:

    - the typing's `conjugatedPortDefinition` is exactly one ConjugatedPortDefinition;
    - the typing's `type` is exactly that conjugate;
    - the conjugate owns exactly one `PortConjugation` naming exactly one original
      `PortDefinition`;
    - that PortConjugation's `originalType` is exactly that original, and its
      `conjugatedType` is exactly the conjugate.
    """
    for typing in factory.select(sysml2.ConjugatedPortTyping):
        feature = kk._single(typing.typedFeature)
        element_id = feature.id if feature is not None else typing.id

        def broken(message: str, _id=element_id) -> Diagnostic:
            return Diagnostic(Severity.ERROR, "broken-conjugation", message, _id)

        conjugate = _sole(typing.conjugatedPortDefinition)
        if not isinstance(conjugate, sysml2.ConjugatedPortDefinition):
            yield broken(
                "conjugated port typing does not have exactly one "
                "conjugated port definition"
            )
            continue
        # The inherited typing target must be EXACTLY the conjugate, or the port
        # is really typed by something other than what `~<original>` renders.
        if not _holds_only(typing.type, conjugate):
            yield broken(
                "conjugated port typing's type is not exactly its "
                "conjugated port definition"
            )
        conjugators = [
            r
            for r in conjugate.ownedRelationship
            if isinstance(r, sysml2.PortConjugation)
        ]
        if len(conjugators) != 1:
            yield broken(
                "conjugated port definition does not have exactly one "
                "port conjugation"
            )
            continue
        pc = conjugators[0]
        original = _sole(pc.originalPortDefinition)
        if not isinstance(original, sysml2.PortDefinition):
            yield broken(
                "port conjugation does not have exactly one original "
                "port definition"
            )
            continue
        # The KerML Conjugation ends must agree (exactly) with the SysML ends.
        if not _holds_only(pc.originalType, original):
            yield broken(
                "port conjugation original type does not match its "
                "original port definition"
            )
        if not _holds_only(pc.conjugatedType, conjugate):
            yield broken(
                "port conjugation conjugated type does not match its conjugate"
            )


def _check_connection_end_integrity(factory: ElementFactory) -> Iterator[Diagnostic]:
    """A binary connection's ends must be features, and must come as a pair.

    Model-derived (needs no mapping context), so it guards ends that reached the
    model OUTSIDE the textual path -- a low-level diagram connect (Gaphor's
    `connect()` does not consult the connector's `allow`), the Python/kernel API,
    or a hand-edited/persisted .gaphor:

    - non-feature end: a source/target set to a non-`Feature` (e.g. a connection
      wired to a definition). The textual mapper rejects these; such an end has no
      valid textual form, so it must be reported here rather than exported as a
      clause the mapper would reject on re-import.
    - incomplete connection: exactly one of source/target is set. A one-ended
      binary connection likewise has no valid textual form and would otherwise be
      dropped silently on export.

    The textual mapper already keeps ends atomic and feature-typed, so a model
    built from text never trips this; it is the safety net for the other routes.
    Covers EVERY binary connector usage -- connection, interface, succession, and
    flow (all `ConnectorAsUsage`) -- so an action's succession/flow ends are guarded
    the same way (Phase 7).
    """
    for connection in factory.select(sysml2.ConnectorAsUsage):
        source = kk._single(connection.source)
        target = kk._single(connection.target)
        name = connection.declaredName
        for end, role in ((source, "source"), (target, "target")):
            if end is not None and not isinstance(end, kerml.Feature):
                yield Diagnostic(
                    Severity.ERROR,
                    "non-feature-connection-end",
                    f"connector {name!r} has a {role} end that is not a feature "
                    f"(a {type(end).__name__})"
                    if name
                    else f"connector {role} end is not a feature "
                    f"(a {type(end).__name__})",
                    connection.id,
                )
        if (source is None) != (target is None):
            present, missing = (
                ("source", "target") if source is not None else ("target", "source")
            )
            yield Diagnostic(
                Severity.ERROR,
                "incomplete-connection",
                f"connector {name!r} has a {present} end but no {missing} end"
                if name
                else f"connector has a {present} end but no {missing} end",
                connection.id,
            )


def _check_connection_ends(
    factory: ElementFactory, unresolved_ends: dict[str, list[str]]
) -> Iterator[Diagnostic]:
    """A connector usage (connection / succession / flow) whose declared end did
    not resolve to a feature is a broken/mismatched endpoint (the mapper records
    these)."""
    for connection_id, ends in unresolved_ends.items():
        element = factory.lookup(connection_id)
        name = element.declaredName if element is not None else None
        for end in ends:
            yield Diagnostic(
                Severity.ERROR,
                "broken-connection-end",
                f"connector {name!r} declares endpoint {end!r} which does not "
                f"resolve to a feature"
                if name
                else f"connector endpoint {end!r} does not resolve to a feature",
                connection_id,
            )


def has_errors(diagnostics: Iterable[Diagnostic]) -> bool:
    return any(d.severity is Severity.ERROR for d in diagnostics)


def _check_missing_owner(factory: ElementFactory) -> Iterator[Diagnostic]:
    """Every non-root member element must have an owning namespace.

    A Namespace may be a root (no owner); other members reached through a
    membership must resolve an owning namespace.
    """
    for membership in factory.select(kerml.OwningMembership):
        member = kk._single(membership.memberElement)
        if member is not None and kk.owning_namespace(member) is None:
            yield Diagnostic(
                Severity.ERROR,
                "missing-owner",
                f"element {member.declaredName!r} has no owning namespace",
                member.id,
            )


def _check_duplicate_names(factory: ElementFactory) -> Iterator[Diagnostic]:
    """No two members of the same namespace may share a name.

    A name in a namespace is an alias's alias name (`memberName`) OR an owned
    member's effective name, so an alias that collides with an owned member or
    another alias is a duplicate too (Phase 5b). The alias name is counted even
    when the alias target is UNRESOLVED -- the name still occupies the namespace --
    so an unresolved alias colliding by name is still reported (independently of its
    own unresolved-alias diagnostic).
    """
    for namespace in factory.select(kerml.Namespace):
        names: Counter[str] = Counter()
        for membership in kk.owned_memberships(namespace):
            member = kk._single(membership.memberElement)
            # An alias carries its name (`memberName`) before its target resolves;
            # an owned member takes its name from its element.
            name = membership.memberName or (
                kk.effective_name(member) if member is not None else None
            )
            if name is not None:
                names[name] += 1
        for name, count in names.items():
            if count > 1:
                yield Diagnostic(
                    Severity.ERROR,
                    "duplicate-name",
                    f"name {name!r} is declared {count} times in the same namespace",
                    namespace.id,
                )


def _check_unresolved_imports(factory: ElementFactory) -> Iterator[Diagnostic]:
    """Every Import must reference an element that exists."""
    for imp in factory.select(kerml.Import):
        if kk._single(imp.target) is None:
            yield Diagnostic(
                Severity.ERROR,
                "unresolved-import",
                "import does not reference a resolvable element",
                imp.id,
            )


def _check_unresolved_aliases(
    factory: ElementFactory, ambiguous: dict[str, str]
) -> Iterator[Diagnostic]:
    """Every alias must reference an element that exists (Phase 5b).

    Model-derived: an alias is a non-owning Membership carrying a `memberName`
    (`kk.is_alias`); it must resolve to a `memberElement`. An alias whose target
    never resolved has none and is reported here -- EXCEPT one whose target was
    AMBIGUOUS (visible from more than one import): that is reported `ambiguous-name`
    and must not be double-reported as unresolved (Phase 5b, mirroring connection
    ends / frame references). On a reloaded model the ambiguous context is gone, so
    such an alias is reported unresolved instead -- still an error, reclassified.
    """
    for membership in factory.select(kerml.Membership):
        if (
            kk.is_alias(membership)
            and kk._single(membership.memberElement) is None
            and membership.id not in ambiguous
        ):
            yield Diagnostic(
                Severity.ERROR,
                "unresolved-alias",
                f"alias {membership.memberName!r} does not reference a "
                "resolvable element",
                membership.id,
            )


def _check_unresolved_specializations(
    unresolved_supertypes: dict[str, list[str]]
) -> Iterator[Diagnostic]:
    """Each definition `:> Super` whose supertype did not resolve to a Classifier
    (Phase 5c). Mapping context: the mapper records EVERY unresolved supertype name
    of a definition (a `:> A, B` with both bad reports both), so no unresolved
    supertype is dropped; an ambiguous supertype is reported `ambiguous-name`
    instead. A reloaded model has no mapping context, so nothing to report here.
    """
    for element_id, names in unresolved_supertypes.items():
        for name in names:
            yield Diagnostic(
                Severity.ERROR,
                "unresolved-specialization",
                f"supertype {name!r} does not resolve to a definition",
                element_id,
            )


def _check_unresolved_subsettings(
    unresolved_subsettings: dict[str, str]
) -> Iterator[Diagnostic]:
    """A usage `:> y` whose subsetted feature did not resolve to a Feature (Phase
    5c). Mapping context: recorded when no Subsetting was created (an ambiguous
    subsetted name is reported `ambiguous-name` instead). Mapping context only.
    """
    for element_id, name in unresolved_subsettings.items():
        yield Diagnostic(
            Severity.ERROR,
            "unresolved-subsetting",
            f"subsetted feature {name!r} does not resolve to a feature",
            element_id,
        )


def _check_unresolved_redefinitions(
    unresolved_redefinitions: dict[str, str]
) -> Iterator[Diagnostic]:
    """A usage `:>> y` whose redefined feature did not resolve to a Feature (Phase
    5c-2). Mapping context: recorded when no Redefinition was created (an ambiguous
    redefined name is reported `ambiguous-name` instead). Mapping context only.
    """
    for element_id, name in unresolved_redefinitions.items():
        yield Diagnostic(
            Severity.ERROR,
            "unresolved-redefinition",
            f"redefined feature {name!r} does not resolve to a feature",
            element_id,
        )


def _check_broken_specializations(factory: ElementFactory) -> Iterator[Diagnostic]:
    """A persisted Subclassification must reference a supertype, a (plain) Subsetting
    a subsetted feature, and a Redefinition a redefined feature (Phase 5c/5c-2).

    Model-derived (needs no mapping context): the mapper only CREATES these when the
    target resolves, so this catches a hand- or API-mutated / corrupt heritage
    relationship -- e.g. a Subclassification whose `superclassifier` was cleared, a
    Subsetting whose `subsettedFeature`, or a Redefinition whose `redefinedFeature`
    was deleted -- that export would otherwise silently drop (it reads only
    resolvable ends). ReferenceSubsetting (the framed-concern form) and Redefinition
    are Subsetting subkinds checked separately, so PLAIN Subsetting is matched by
    exact type.
    """
    for subclassification in factory.select(kerml.Subclassification):
        if kk._single(subclassification.superclassifier) is None:
            yield Diagnostic(
                Severity.ERROR,
                "broken-subclassification",
                "subclassification does not reference a supertype",
                subclassification.id,
            )
    for subsetting in factory.select(kerml.Subsetting):
        if type(subsetting) is not kerml.Subsetting:
            continue  # ReferenceSubsetting / Redefinition checked elsewhere
        if kk._single(subsetting.subsettedFeature) is None:
            yield Diagnostic(
                Severity.ERROR,
                "broken-subsetting",
                "subsetting does not reference a subsetted feature",
                subsetting.id,
            )
    for redefinition in factory.select(kerml.Redefinition):
        if kk._single(redefinition.redefinedFeature) is None:
            yield Diagnostic(
                Severity.ERROR,
                "broken-redefinition",
                "redefinition does not reference a redefined feature",
                redefinition.id,
            )


def _check_ambiguous_names(
    factory: ElementFactory, ambiguous: dict[str, str]
) -> Iterator[Diagnostic]:
    """A name that resolves to MORE THAN ONE distinct element is ambiguous.

    Mapping context: the resolver records a (qualified) name that, at one scope,
    resolved to more than one distinct element -- visible from several IMPORTS
    (Phase 5a) or INHERITED from several unrelated supertypes (Phase 5c, an
    inherited-name conflict) -- and so did NOT bind. Reported here; like the other
    reference rules this needs mapping context, so a reloaded model has none.
    """
    for element_id, name in ambiguous.items():
        yield Diagnostic(
            Severity.ERROR,
            "ambiguous-name",
            f"{name!r} resolves to more than one element "
            "(ambiguous: imported or inherited)",
            element_id,
        )


def _check_broken_typing(factory: ElementFactory) -> Iterator[Diagnostic]:
    """A FeatureTyping must reference both a typed feature and a type.

    This is model-derived (needs no mapping context), so it catches a typing
    that became broken in a persisted or mutated model -- e.g. after its type
    element was deleted, leaving an orphaned FeatureTyping with an empty `type`.
    """
    for typing in factory.select(kerml.FeatureTyping):
        feature = kk._single(typing.typedFeature)
        type_ = kk._single(typing.type)
        if type_ is None:
            owner = kk._single(typing.owningRelatedElement)
            name = owner.declaredName if owner is not None else None
            yield Diagnostic(
                Severity.ERROR,
                "usage-without-valid-type",
                f"feature typing on {name!r} has no resolved type"
                if name
                else "feature typing has no resolved type",
                (feature.id if feature is not None else typing.id),
            )
        elif feature is None:
            yield Diagnostic(
                Severity.ERROR,
                "broken-typing",
                "feature typing has a type but no typed feature",
                typing.id,
            )
        elif is_managed_usage_kind(feature) and not type_matches_usage_kind(
            feature, type_
        ):
            # Both ends present but kind-mismatched (e.g. a PartUsage typed by an
            # AttributeDefinition). Model-derived, so this catches a wrong-kind
            # relation that reached the model outside the textual path -- via the
            # Python/kernel API or a hand-edited/persisted .gaphor -- which the
            # mapping-context `type-kind-mismatch` rule alone would miss. Only the
            # managed SysML usage kinds are checked; a bare kernel Feature typing
            # is out of this contract's scope.
            name = feature.declaredName
            yield Diagnostic(
                Severity.ERROR,
                "type-kind-mismatch",
                f"{type(feature).__name__} {name!r} is typed by a "
                f"{type(type_).__name__}, not its required definition kind",
                feature.id,
            )


def _check_usage_without_valid_type(
    factory: ElementFactory, unresolved_types: dict[str, str]
) -> Iterator[Diagnostic]:
    """Any usage that declared a type which did not resolve to a Type is an error.

    The mapper records (usage id -> declared type name) for every usage -- Part,
    Attribute, or any future usage kind -- whose declared type name either did
    not resolve or resolved to a non-Type (e.g. a Package). Iterating the
    recorded ids (not a specific usage class) keeps this correct as constructs
    grow. A usage with no declared type is fine (an untyped usage is legal).
    """
    for usage_id, declared_type in unresolved_types.items():
        element = factory.lookup(usage_id)
        name = element.declaredName if element is not None else None
        yield Diagnostic(
            Severity.ERROR,
            "usage-without-valid-type",
            f"usage {name!r} declares type {declared_type!r} which does not "
            f"resolve to a type",
            usage_id,
        )


def _check_type_kind_mismatch(
    factory: ElementFactory, mistyped: dict[str, tuple[str, str]]
) -> Iterator[Diagnostic]:
    """A usage typed by a resolvable Type of the WRONG KIND is an error.

    Each usage kind is typed by exactly one definition kind (a part by a
    PartDefinition, a requirement by a RequirementDefinition, ...). A declared
    type that resolves to a Type of a different kind -- e.g.
    `part p : AttributeDefinition` or `requirement r : ConstraintDefinition` --
    is a kind mismatch: no FeatureTyping is created (the mapper records it here),
    and it must be reported rather than silently accepted.
    """
    for usage_id, (declared_type, resolved_kind) in mistyped.items():
        element = factory.lookup(usage_id)
        name = element.declaredName if element is not None else None
        usage_kind = type(element).__name__ if element is not None else "usage"
        yield Diagnostic(
            Severity.ERROR,
            "type-kind-mismatch",
            f"{usage_kind} {name!r} declares type {declared_type!r} which "
            f"resolves to a {resolved_kind}, not the required definition kind",
            usage_id,
        )
