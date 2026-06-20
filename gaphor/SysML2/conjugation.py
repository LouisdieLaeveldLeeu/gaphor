"""Port conjugation behavior (Phase 8a).

`port p : ~Fuel` types `p` by the *conjugate* of `Fuel`, modeled faithfully on
the normative metamodel rather than as an ad-hoc flag:

- each PortDefinition has at most one `ConjugatedPortDefinition` (its implicit
  conjugate), linked to the original by a `PortConjugation` (a KerML
  `Conjugation`) whose `originalPortDefinition` is the original;
- a port usage typed `: ~Fuel` is typed by that conjugate through a
  `ConjugatedPortTyping` (a FeatureTyping carrying `conjugatedPortDefinition`).

The implicit conjugate and its PortConjugation are owned by the ORIGINAL
definition, so they cascade on its delete and round-trip with the model. The
conjugate carries no `declaredName` (its name is the derived `~<original>`), so
it stays invisible to name resolution, duplicate-name checks, and textual export
-- only `~Fuel` is ever emitted, never the conjugate as a `port def`.

This is the SysML port-conjugation layer; the generic KerML `Conjugation`
behavior (originalType/conjugatedType) lives with the kernel. Kept separate so
`kerml_kernel` stays KerML-pure.
"""

from __future__ import annotations

from gaphor.SysML2 import kerml
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2 import sysml2


def port_conjugation(
    conjugate: sysml2.ConjugatedPortDefinition,
) -> sysml2.PortConjugation | None:
    """The PortConjugation owned by `conjugate` (links it to its original)."""
    for relationship in conjugate.ownedRelationship:
        if isinstance(relationship, sysml2.PortConjugation):
            return relationship
    return None


def original_port_definition(
    conjugate: sysml2.ConjugatedPortDefinition,
) -> sysml2.PortDefinition | None:
    """The PortDefinition that `conjugate` is the conjugate of."""
    pc = port_conjugation(conjugate)
    if pc is None:
        return None
    original = kk._single(pc.originalPortDefinition)
    return original if isinstance(original, sysml2.PortDefinition) else None


def conjugate_of(
    original: sysml2.PortDefinition,
) -> sysml2.ConjugatedPortDefinition | None:
    """The materialized conjugate of `original`, if one exists."""
    for member in kk.members(original):
        if isinstance(member, sysml2.ConjugatedPortDefinition):
            return member
    return None


def get_or_create_conjugate(
    original: sysml2.PortDefinition,
) -> sysml2.ConjugatedPortDefinition:
    """The conjugate of `original`, creating (and persisting) it if needed.

    At most one conjugate exists per PortDefinition; every `: ~Original` typing
    reuses it. The conjugate is an unnamed owned member of `original`, owning a
    PortConjugation back to it.
    """
    existing = conjugate_of(original)
    if existing is not None:
        return existing

    factory = original.model
    conjugate = factory.create(sysml2.ConjugatedPortDefinition)
    kk.add_owned_member(original, conjugate, factory.create(kerml.OwningMembership))

    pc = factory.create(sysml2.PortConjugation)
    pc.originalPortDefinition = original
    # The KerML Conjugation ends: original -> conjugated.
    pc.originalType = original
    pc.conjugatedType = conjugate
    conjugate.ownedRelationship = pc
    pc.owningRelatedElement = conjugate
    return conjugate


def conjugated_typing(
    feature: kerml.Feature,
) -> sysml2.ConjugatedPortTyping | None:
    """The ConjugatedPortTyping owned by `feature`, if it is conjugated-typed."""
    for typing in kk.feature_typings(feature):
        if isinstance(typing, sysml2.ConjugatedPortTyping):
            return typing
    return None


def set_conjugated_port_type(
    usage: kerml.Feature, original: sysml2.PortDefinition
) -> sysml2.ConjugatedPortTyping:
    """Type `usage` by the conjugate of `original` via a ConjugatedPortTyping.

    Like `kk.set_feature_type`, but creates the conjugated typing and points it at
    the (get-or-created) conjugate. Re-typing first clears any existing typing so
    UI edits do not accumulate duplicates.
    """
    kk.clear_feature_type(usage)
    conjugate = get_or_create_conjugate(original)

    factory = usage.model
    typing = factory.create(sysml2.ConjugatedPortTyping)
    typing.typedFeature = usage
    typing.type = conjugate
    typing.conjugatedPortDefinition = conjugate
    usage.ownedRelationship = typing
    typing.owningRelatedElement = usage
    return typing


def conjugated_type_name(feature: kerml.Feature) -> kerml.Element | None:
    """The ORIGINAL PortDefinition behind `feature`'s conjugated typing, if any.

    Used by export to render `~<original>`; returns None for a non-conjugated (or
    untyped) feature.
    """
    typing = conjugated_typing(feature)
    if typing is None:
        return None
    conjugate = kk._single(typing.conjugatedPortDefinition)
    if not isinstance(conjugate, sysml2.ConjugatedPortDefinition):
        return None
    return original_port_definition(conjugate)
