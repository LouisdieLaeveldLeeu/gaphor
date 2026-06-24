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
    Classifier,
    Element,
    Feature,
    FeatureTyping,
    Import,
    Membership,
    Namespace,
    OwningMembership,
    ReferenceSubsetting,
    Relationship,
    Subclassification,
    Subsetting,
    Type,
    VisibilityKind,
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


def add_reference_subsetting(
    referencing: Feature, referenced: Feature
) -> ReferenceSubsetting:
    """Make `referencing` REFERENCE `referenced` via an owned ReferenceSubsetting.

    The ReferenceSubsetting is owned by the `referencing` feature (composite,
    cascades), while `referenced` (the subsetted/referenced feature) is a
    NON-owning reference. Mirrors `set_feature_type`: the owning feature is the
    subsettingFeature; the referencedFeature is the target.
    """
    subsetting = referencing.model.create(ReferenceSubsetting)
    subsetting.subsettingFeature = referencing
    subsetting.referencedFeature = referenced
    referencing.ownedRelationship = subsetting
    subsetting.owningRelatedElement = referencing
    return subsetting


def add_subclassification(
    subtype: Classifier, supertype: Classifier
) -> Subclassification:
    """Make `subtype` specialize `supertype` via an owned Subclassification (the
    KerML heritage relationship between Classifiers, Phase 5c).

    The Subclassification is owned by `subtype` (composite, cascades); `supertype`
    (the superclassifier/general) is a NON-owning reference. Mirrors
    `set_feature_type`: the subkind-specific ends (subclassifier/superclassifier)
    carry the relation; the base general/specific stay unset.
    """
    sc = subtype.model.create(Subclassification)
    sc.subclassifier = subtype
    sc.superclassifier = supertype
    subtype.ownedRelationship = sc
    sc.owningRelatedElement = subtype
    return sc


def subclassifications(type_: Type) -> Iterator[Subclassification]:
    """Subclassifications owned by `type_` (where it is the subclassifier)."""
    for relationship in type_.ownedRelationship:
        if isinstance(relationship, Subclassification):
            yield relationship


def supertypes(type_: Type) -> Iterator[Type]:
    """Direct supertypes of `type_`: the superclassifiers of its Subclassifications
    (Phase 5c)."""
    for sc in subclassifications(type_):
        general = _single(sc.superclassifier)
        if general is not None:
            yield general


def inherited_members_named(type_: Type, name: str) -> list[Element]:
    """The DISTINCT public members named `name` inherited through `type_`'s
    supertypes (transitive closure, cycle-guarded) (Phase 5c).

    Returns every distinct candidate, deduplicated by id -- so a member reachable by
    several paths (a diamond) is ONE result, but the same name declared by two
    UNRELATED supertypes is two results, an inherited-name CONFLICT. The caller
    decides what more-than-one means (the resolver reports it ambiguous); this never
    picks a winner, so no inherited conflict binds silently to a first match.

    A private member is NOT inherited (visibility governs inheritance); the member
    default is public, so ordinary members ARE inherited. The type's OWN members are
    searched by the caller (own shadows inherited), not here. Matches an owned member
    by its element name and an alias by its alias name, like `owned_member_named`.
    """
    found: dict[str, Element] = {}
    seen: set[str] = set()
    queue: list[Type] = list(supertypes(type_))
    while queue:
        supertype = queue.pop(0)
        if supertype.id in seen:  # guard against inheritance cycles / diamonds
            continue
        seen.add(supertype.id)
        for membership in owned_memberships(supertype):
            if membership.visibility != VisibilityKind.public:
                continue  # private members are not inherited
            member = _single(membership.memberElement)
            if member is None:
                continue
            member_name = membership.memberName or effective_name(member)
            if member_name == name:
                found[member.id] = member
        queue.extend(supertypes(supertype))
    return list(found.values())


def add_subsetting(
    subsetting_feature: Feature, subsetted_feature: Feature
) -> Subsetting:
    """Make `subsetting_feature` SUBSET `subsetted_feature` via an owned (plain)
    Subsetting (`part x :> y;`, Phase 5c).

    A plain Subsetting, NOT a ReferenceSubsetting (the framed-concern form). Owned by
    the subsetting feature (composite, cascades); the subsetted feature is a
    NON-owning reference, like `set_feature_type` / `add_reference_subsetting`.
    """
    subsetting = subsetting_feature.model.create(Subsetting)
    subsetting.subsettingFeature = subsetting_feature
    subsetting.subsettedFeature = subsetted_feature
    subsetting_feature.ownedRelationship = subsetting
    subsetting.owningRelatedElement = subsetting_feature
    return subsetting


def subsettings(feature: Feature) -> Iterator[Subsetting]:
    """Plain Subsettings owned by `feature`, in order (Phase 5c).

    EXCLUDES ReferenceSubsetting (a Subsetting subclass used for the framed-concern
    reference form), so the two specialization forms never read each other's
    relationships.
    """
    for relationship in feature.ownedRelationship:
        if type(relationship) is Subsetting:
            yield relationship


def reference_subsettings(feature: Feature) -> Iterator[ReferenceSubsetting]:
    """All ReferenceSubsettings owned by `feature`, in order."""
    for relationship in feature.ownedRelationship:
        if isinstance(relationship, ReferenceSubsetting):
            yield relationship


def reference_subsetting(feature: Feature) -> ReferenceSubsetting | None:
    """The SOLE ReferenceSubsetting owned by `feature`, or None if it owns zero or
    MORE THAN ONE.

    Exact-one (not first-of-many): a feature that references via subsetting
    references exactly one target, so a second owned reference subsetting is a
    corruption the caller must not silently read as the first (which would drop the
    extra on export). `reference_subsettings` exposes the full set for the
    integrity check that reports the corruption."""
    subsettings = list(reference_subsettings(feature))
    return subsettings[0] if len(subsettings) == 1 else None


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
    """Owned member elements: the memberElements of the namespace's OWNING
    memberships.

    Excludes alias memberships (non-owning Memberships, Phase 5b): an alias's
    memberElement lives in another namespace, so it is not one of THIS namespace's
    owned/declared members. Callers that render or count a namespace's own members
    (export, round-trip, duplicate detection) want exactly the owned ones; name
    resolution that must see aliases uses `owned_member_named`.
    """
    for membership in owned_memberships(namespace):
        if not isinstance(membership, OwningMembership):
            continue
        member = _single(membership.memberElement)
        if member is not None:
            yield member


def is_alias(membership: Membership) -> bool:
    """True for an alias membership (Phase 5b): a non-owning Membership carrying a
    `memberName`.

    An alias gives an existing (foreign) element an additional name in a namespace
    without owning it. OwningMembership and its subkinds (FeatureMembership,
    Subject/Actor/Stakeholder/FramedConcern memberships) OWN their member and are
    never aliases.
    """
    return (
        isinstance(membership, Membership)
        and not isinstance(membership, OwningMembership)
        and bool(membership.memberName)
    )


def aliases(namespace: Namespace) -> Iterator[Membership]:
    """Alias memberships owned by `namespace` (Phase 5b)."""
    for membership in owned_memberships(namespace):
        if is_alias(membership):
            yield membership


def add_alias(
    namespace: Namespace,
    name: str,
    alias: Membership,
    visibility: VisibilityKind | None = None,
) -> Membership:
    """Make `alias` (a plain Membership) name an element in `namespace` (Phase 5b).

    An alias is a NON-owning Membership: it gives a foreign element an additional
    name (`memberName`) in this namespace without owning it. The target
    (`memberElement`) is a non-owning reference, resolved and set later via
    `set_alias_target` (mapping phase 2); until then the alias is unresolved.
    """
    namespace.ownedRelationship = alias
    alias.owningRelatedElement = namespace
    alias.memberName = name
    if visibility is not None:
        alias.visibility = visibility
    return alias


def set_alias_target(alias: Membership, target: Element) -> None:
    """Set the (non-owning) element an alias references (mapping phase 2)."""
    alias.memberElement = target


def owned_member_named(namespace: Namespace, name: str) -> Element | None:
    """Same-namespace name resolution: a member by its name in this namespace.

    An owned member matches by its element's effective name; an ALIAS matches by
    its alias name (`memberName`) and resolves to the (foreign) element it
    references (Phase 5b). So `alias E for Lib::Engine;` makes `E` resolve to
    `Lib::Engine` wherever a name resolves in this namespace.
    """
    for membership in owned_memberships(namespace):
        member = _single(membership.memberElement)
        if member is None:
            continue
        member_name = membership.memberName or effective_name(member)
        if member_name == name:
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


def is_import_all(imp: Import) -> bool:
    """Whether `imp` is a wildcard (`import A::*`) import.

    Robust to persistence: a generated `_attribute[bool]` reloads from `.gaphor` as
    the STRING ``"True"``/``"False"`` (non-empty, so a bare truthiness test would
    read ``"False"`` as True), so the value is normalized here. Used everywhere
    `isImportAll` is read as a boolean (resolver, export, round-trip).
    """
    value = imp.isImportAll
    if isinstance(value, str):
        return value.lower() in ("true", "1")
    return bool(value)


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
