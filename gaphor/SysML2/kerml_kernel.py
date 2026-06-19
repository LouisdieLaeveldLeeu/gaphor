"""KerML minimal kernel: behaviour layer over the generated structural classes.

`kerml.py` is generated from the normative MOF XMI and carries only the
*stored* (non-derived) structure: the Relationship containment spine
(`Element.ownedRelationship` / `Relationship.ownedRelatedElement`, both
composite), relationship back-pointers, and non-owning references such as
`Membership.memberElement` and `Specialization.general`/`specific`.

KerML's *derived* features (owner, owningNamespace, ownedMembership, member,
importedElement, featuringType, qualifiedName, ...) are NOT persisted -- the XMI
marks them `isDerived=true`, so storing them would create stale state. This
module computes them from the stored structure, ported from the normative
derivations in the XMI (not intuition). Each derivation that is not yet
implemented raises `NotImplementedError` rather than returning a wrong default.

Wiring helper `add_owned_member` establishes the stored containment spine the
generated model expects; the derived accessors then read back through it.
"""

from __future__ import annotations

from collections.abc import Iterator

from gaphor.SysML2.kerml import (
    Element,
    Feature,
    FeatureTyping,
    Import,
    Membership,
    Namespace,
    OwningMembership,
    Relationship,
    Type,
)

QUALIFIED_NAME_SEPARATOR = "::"


# --- wiring the stored containment spine -------------------------------------


def add_owned_member(
    namespace: Namespace, member: Element, membership: OwningMembership
) -> OwningMembership:
    """Make `member` an owned member of `namespace` through `membership`.

    Establishes the stored spine the generated model persists:
    `namespace` owns `membership` (`ownedRelationship`, composite), `membership`
    owns `member` (`ownedRelatedElement`, composite) and references it
    (`memberElement`), with the relationship back-pointers set. The derived
    accessors below read this structure; nothing derived is stored.
    """
    namespace.ownedRelationship = membership
    membership.owningRelatedElement = namespace
    membership.ownedRelatedElement = member
    membership.memberElement = member
    # Back-pointer: the member's owningRelationship is this membership. The
    # generated associations are one-directional (the XMI declares no opposite
    # ends), so the navigation edge owning_namespace() reads is set explicitly.
    member.owningRelationship = membership
    return membership


def add_import(namespace: Namespace, imported: Element, imp: Import) -> Import:
    """Make `imported` imported into `namespace` through `imp` (stored spine)."""
    namespace.ownedRelationship = imp
    imp.owningRelatedElement = namespace
    # The imported element is a non-owning target (must NOT cascade on delete).
    imp.target = imported
    return imp


def feature_typings(feature: Feature) -> Iterator[FeatureTyping]:
    """FeatureTyping relationships owned by `feature` and targeting it."""
    for relationship in feature.ownedRelationship:
        if (
            isinstance(relationship, FeatureTyping)
            and feature in relationship.typedFeature
        ):
            yield relationship


def feature_type(feature: Feature) -> Type | None:
    """The first stored type of `feature`, if it has a FeatureTyping."""
    for typing in feature_typings(feature):
        type_ = _single(typing.type)
        if isinstance(type_, Type):
            return type_
    return None


def clear_feature_type(feature: Feature) -> None:
    """Remove stored FeatureTyping relationships owned by `feature`."""
    for typing in list(feature_typings(feature)):
        typing.unlink()


def set_feature_type(feature: Feature, type_: Type | None) -> FeatureTyping | None:
    """Set the stored FeatureTyping for a feature.

    The FeatureTyping is owned by the typed feature, while `type_` is a
    non-owning reference. Re-setting the type first removes the existing owned
    FeatureTyping so UI edits cannot accumulate duplicate typing relationships.
    """
    clear_feature_type(feature)
    if type_ is None:
        return None

    typing = feature.model.create(FeatureTyping)
    typing.typedFeature = feature
    typing.type = type_
    feature.ownedRelationship = typing
    typing.owningRelatedElement = feature
    return typing


# --- derived surface (computed from stored structure) ------------------------


def effective_name(element: Element) -> str | None:
    """The name used during resolution: `declaredName` by default (KerML)."""
    return element.declaredName


def owned_memberships(namespace: Namespace) -> Iterator[Membership]:
    """Owned relationships of the namespace that are Memberships (KerML)."""
    for relationship in namespace.ownedRelationship:
        if isinstance(relationship, Membership):
            yield relationship


def members(namespace: Namespace) -> Iterator[Element]:
    """Member elements: the memberElements of the namespace's memberships."""
    for membership in owned_memberships(namespace):
        member = _single(membership.memberElement)
        if member is not None:
            yield member


def owned_member_named(namespace: Namespace, name: str) -> Element | None:
    """Same-namespace name resolution: find a member by effective name."""
    for member in members(namespace):
        if effective_name(member) == name:
            return member
    return None


def owning_namespace(element: Element) -> Namespace | None:
    """The namespace owning this element: the owner of its owning Membership.

    Derived per KerML: an element's owningNamespace is the owningRelatedElement
    of the Membership that owns it.
    """
    for relationship in element.owningRelationship:
        if isinstance(relationship, Membership):
            owner = _single(relationship.owningRelatedElement)
            if isinstance(owner, Namespace):
                return owner
    return None


def owned_elements(element: Element) -> Iterator[Element]:
    """Elements owned by this element via its owned relationships (KerML)."""
    for relationship in element.ownedRelationship:
        for owned in relationship.ownedRelatedElement:
            yield owned


def qualified_name(element: Element) -> str:
    """Ownership-qualified name: owning-namespace names joined by `::`.

    Composed by walking the owning-namespace chain (KerML). Falls back to the
    effective name when there is no owner.
    """
    parts: list[str] = []
    current: Element | None = element
    seen: set[str] = set()
    while current is not None:
        if current.id in seen:  # defensive against cycles
            break
        seen.add(current.id)
        name = effective_name(current)
        parts.append(name if name is not None else "")
        current = owning_namespace(current)
    return QUALIFIED_NAME_SEPARATOR.join(reversed(parts))


def resolve_in_namespace(namespace: Namespace, qualified: str) -> Element | None:
    """Resolve a `A::B::C` qualified name relative to a containing namespace.

    The first segment is a *member* of `namespace` (not its own name); each
    further segment is a member of the previously resolved namespace. Used for
    resolution from an implicit/unnamed root that owns the top-level members.
    """
    current: Element | None = namespace
    for segment in qualified.split(QUALIFIED_NAME_SEPARATOR):
        if not isinstance(current, Namespace):
            return None
        current = owned_member_named(current, segment)
        if current is None:
            return None
    return current


def resolve_qualified_name(root: Namespace, qualified: str) -> Element | None:
    """Resolve a `A::B::C` qualified name where the FIRST segment is `root`'s own
    name (root-rooted), then each further segment is a member."""
    segments = qualified.split(QUALIFIED_NAME_SEPARATOR)
    if not segments or effective_name(root) != segments[0]:
        return None
    current: Element | None = root
    for segment in segments[1:]:
        if not isinstance(current, Namespace):
            return None
        current = owned_member_named(current, segment)
        if current is None:
            return None
    return current


def imported_elements(namespace: Namespace) -> Iterator[Element]:
    """Elements imported by the namespace's owned Imports.

    Derived per KerML; for this M1b minimum the imported element is the Import's
    (non-owning) target.
    """
    for relationship in namespace.ownedRelationship:
        if isinstance(relationship, Import):
            target = _single(relationship.target)
            if target is not None:
                yield target


# `featuring_types` (the derived TypeFeaturing surface) was retired in Phase 5:
# it had no implementation (the kernel slice does not wire TypeFeaturing) and no
# caller, so a raising stub added no value. It returns as a real derivation if a
# later phase wires TypeFeaturing and a consumer needs it.


# --- internal helpers --------------------------------------------------------


def _single(relation) -> Element | None:
    items = list(relation)
    return items[0] if items else None
