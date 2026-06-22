"""Requirement parameter behavior (Phase 6b/6c/6d).

A requirement body's `subject`, `assume`/`require`, `actor`, `stakeholder`, and
`frame` parts are modeled faithfully on the normative memberships:

- `subject` is a parameter feature related to the requirement by a
  `SubjectMembership` (a KerML ParameterMembership);
- `assume`/`require` each own a `ConstraintUsage` (whose body reuses the Phase 6a
  opaque-text mechanism) through a `RequirementConstraintMembership` whose `kind`
  is `assumption` or `requirement`;
- `actor`/`stakeholder` are `PartUsage` parameters related by an `ActorMembership`
  / `StakeholderMembership` respectively (both KerML ParameterMemberships; the
  pinned XMI types their owned parameter as a PartUsage), kept in declaration
  order (Phase 6c);
- `frame` owns a `ConcernUsage` through a `FramedConcernMembership` (a
  RequirementConstraintMembership with `kind` fixed to `requirement`), kept in
  declaration order (Phase 6d). Because FramedConcernMembership IS a
  RequirementConstraintMembership, the `require`-constraint reader excludes it;
- `reqId` is the requirement's `declaredShortName` (Phase 6c): a plain KerML
  short-name attribute, not a membership.

The constraints/subject/actor/stakeholder/concern are owned through these
memberships (which ARE OwningMemberships), so they persist, cascade on delete, and
round-trip. The constraint bodies remain opaque (no expression semantics) -- the
requirement rows stay `alpha`.
"""

from __future__ import annotations

from collections.abc import Iterator

from gaphor.SysML2 import kerml
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2 import sysml2

Assumption = sysml2.RequirementConstraintKind.assumption
Requirement = sysml2.RequirementConstraintKind.requirement


def subject_membership(
    requirement: sysml2.RequirementDefinition | sysml2.RequirementUsage,
) -> sysml2.SubjectMembership | None:
    for relationship in requirement.ownedRelationship:
        if isinstance(relationship, sysml2.SubjectMembership):
            return relationship
    return None


def subject(
    requirement: sysml2.RequirementDefinition | sysml2.RequirementUsage,
) -> kerml.Feature | None:
    """The requirement's subject parameter feature, if any."""
    membership = subject_membership(requirement)
    member = kk._single(membership.memberElement) if membership is not None else None
    return member if isinstance(member, kerml.Feature) else None


def add_subject(
    requirement: sysml2.RequirementDefinition | sysml2.RequirementUsage,
    feature: kerml.Feature,
) -> sysml2.SubjectMembership:
    """Relate `feature` as the requirement's subject via a SubjectMembership."""
    membership = requirement.model.create(sysml2.SubjectMembership)
    kk.add_owned_member(requirement, feature, membership)
    return membership


def reqId(
    requirement: sysml2.RequirementDefinition | sysml2.RequirementUsage,
) -> str | None:
    """The requirement's `reqId` (its KerML `declaredShortName`), or None."""
    value = requirement.declaredShortName
    return value if value else None


def set_reqId(
    requirement: sysml2.RequirementDefinition | sysml2.RequirementUsage,
    value: str | None,
) -> None:
    """Set the requirement's `reqId` into `declaredShortName` (None clears it)."""
    requirement.declaredShortName = value or None


def _part_usage_parameters(
    requirement: sysml2.RequirementDefinition | sysml2.RequirementUsage,
    membership_type: type,
) -> Iterator[sysml2.PartUsage]:
    """The PartUsage parameters related by `membership_type`, in declaration order.

    Actor/stakeholder parameters are PartUsages (per the pinned XMI); a member of
    any other kind is skipped here and reported by validation.
    """
    for relationship in requirement.ownedRelationship:
        if isinstance(relationship, membership_type):
            member = kk._single(relationship.memberElement)
            if isinstance(member, sysml2.PartUsage):
                yield member


def _add_part_usage_parameter(
    requirement: sysml2.RequirementDefinition | sysml2.RequirementUsage,
    usage: sysml2.PartUsage,
    membership_type: type,
):
    membership = requirement.model.create(membership_type)
    kk.add_owned_member(requirement, usage, membership)
    return membership


def actors(
    requirement: sysml2.RequirementDefinition | sysml2.RequirementUsage,
) -> Iterator[sysml2.PartUsage]:
    """The requirement's actor parameter PartUsages, in declaration order."""
    return _part_usage_parameters(requirement, sysml2.ActorMembership)


def add_actor(
    requirement: sysml2.RequirementDefinition | sysml2.RequirementUsage,
    usage: sysml2.PartUsage,
) -> sysml2.ActorMembership:
    """Relate `usage` as an actor of the requirement via an ActorMembership."""
    return _add_part_usage_parameter(requirement, usage, sysml2.ActorMembership)


def stakeholders(
    requirement: sysml2.RequirementDefinition | sysml2.RequirementUsage,
) -> Iterator[sysml2.PartUsage]:
    """The requirement's stakeholder parameter PartUsages, in declaration order."""
    return _part_usage_parameters(requirement, sysml2.StakeholderMembership)


def add_stakeholder(
    requirement: sysml2.RequirementDefinition | sysml2.RequirementUsage,
    usage: sysml2.PartUsage,
) -> sysml2.StakeholderMembership:
    """Relate `usage` as a stakeholder via a StakeholderMembership."""
    return _add_part_usage_parameter(requirement, usage, sysml2.StakeholderMembership)


def requirement_constraints(
    requirement: sysml2.RequirementDefinition | sysml2.RequirementUsage,
    kind: sysml2.RequirementConstraintKind,
) -> Iterator[sysml2.ConstraintUsage]:
    """The assumed (kind=assumption) or required (kind=requirement) constraints,
    in declaration order.

    A `FramedConcernMembership` IS a `RequirementConstraintMembership` (with
    kind=requirement, owning a ConcernUsage), so it is EXCLUDED here -- a framed
    concern is read via `framed_concerns`, not as a `require` constraint.
    """
    for relationship in requirement.ownedRelationship:
        if (
            isinstance(relationship, sysml2.RequirementConstraintMembership)
            and not isinstance(relationship, sysml2.FramedConcernMembership)
            and relationship.kind == kind
        ):
            member = kk._single(relationship.memberElement)
            if isinstance(member, sysml2.ConstraintUsage):
                yield member


def add_requirement_constraint(
    requirement: sysml2.RequirementDefinition | sysml2.RequirementUsage,
    constraint: sysml2.ConstraintUsage,
    kind: sysml2.RequirementConstraintKind,
) -> sysml2.RequirementConstraintMembership:
    """Own `constraint` as an assumed/required constraint via a
    RequirementConstraintMembership carrying `kind`."""
    membership = requirement.model.create(sysml2.RequirementConstraintMembership)
    membership.kind = kind
    kk.add_owned_member(requirement, constraint, membership)
    return membership


def framed_concerns(
    requirement: sysml2.RequirementDefinition | sysml2.RequirementUsage,
) -> Iterator[sysml2.ConcernUsage]:
    """The requirement's framed-concern ConcernUsages, in declaration order
    (Phase 6d)."""
    for relationship in requirement.ownedRelationship:
        if isinstance(relationship, sysml2.FramedConcernMembership):
            member = kk._single(relationship.memberElement)
            if isinstance(member, sysml2.ConcernUsage):
                yield member


def add_framed_concern(
    requirement: sysml2.RequirementDefinition | sysml2.RequirementUsage,
    concern: sysml2.ConcernUsage,
) -> sysml2.FramedConcernMembership:
    """Own `concern` as a framed concern via a FramedConcernMembership.

    The XMI fixes a FramedConcernMembership's `kind` to `requirement`, so it is set
    explicitly (the generated default is the inherited `assumption`)."""
    membership = requirement.model.create(sysml2.FramedConcernMembership)
    membership.kind = Requirement
    kk.add_owned_member(requirement, concern, membership)
    return membership


def framed_concern_reference(
    concern: sysml2.ConcernUsage,
) -> sysml2.ConcernUsage | None:
    """The ConcernUsage that `concern` validly REFERENCES as an anonymous
    framed-concern reference (`frame <existing>`, Phase 6d-2), or None.

    The SINGLE predicate shared by export, round-trip, and validation, so the three
    cannot disagree on what counts as a reference. Returns the referenced concern
    ONLY when `concern` is a WELL-FORMED reference: it owns EXACTLY ONE
    ReferenceSubsetting to EXACTLY ONE ConcernUsage AND is otherwise ANONYMOUS (no
    declaredName, no own FeatureTyping -- the reference form's usage carries no
    independent declaration; its type comes from the referenced concern). A declared
    frame, or ANY corrupt/mixed state (multiple subsettings, a wrong-kind target, or
    a name / own type alongside a reference), returns None -- so export never emits
    it as `frame <ref>` (silently dropping the declared/typed state) and validation
    reports it."""
    subsettings = list(kk.reference_subsettings(concern))
    if len(subsettings) != 1:
        return None
    referenced = list(subsettings[0].referencedFeature)
    target = referenced[0] if len(referenced) == 1 else None
    if not isinstance(target, sysml2.ConcernUsage):
        return None
    if concern.declaredName or kk.feature_type(concern) is not None:
        return None
    return target


def is_referencing_frame(concern: sysml2.ConcernUsage) -> bool:
    """Whether `concern` owns any ReferenceSubsetting -- i.e. it is (or attempts to
    be) the `frame <existing>` reference form, well-formed or not. A declared frame
    (`frame concern <name>`) owns none."""
    return any(kk.reference_subsettings(concern))
