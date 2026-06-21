"""Requirement parameter behavior (Phase 6b).

A requirement body's `subject`, `assume`, and `require` parts are modeled
faithfully on the normative memberships:

- `subject` is a parameter feature related to the requirement by a
  `SubjectMembership` (a KerML ParameterMembership);
- `assume`/`require` each own a `ConstraintUsage` (whose body reuses the Phase 6a
  opaque-text mechanism) through a `RequirementConstraintMembership` whose `kind`
  is `assumption` or `requirement`.

The constraints/subject are owned through these memberships (which ARE
OwningMemberships), so they persist, cascade on delete, and round-trip. Only the
named subject/assume/require parts are covered here; actor/stakeholder/framed-
concern parameters and `reqId` are out of scope, and the constraint bodies remain
opaque (no expression semantics) -- the requirement rows stay `alpha`.
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


def requirement_constraints(
    requirement: sysml2.RequirementDefinition | sysml2.RequirementUsage,
    kind: sysml2.RequirementConstraintKind,
) -> Iterator[sysml2.ConstraintUsage]:
    """The assumed (kind=assumption) or required (kind=requirement) constraints,
    in declaration order."""
    for relationship in requirement.ownedRelationship:
        if (
            isinstance(relationship, sysml2.RequirementConstraintMembership)
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
