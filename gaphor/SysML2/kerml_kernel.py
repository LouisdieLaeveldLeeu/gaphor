"""KerML minimal kernel: behaviour layer over the generated structural classes.

`kerml.py` is generated from the normative MOF XMI and carries the structural
shape (classes, attributes, references) and persistence. It does not implement
KerML's *derived* features, which the spec defines operationally. This module
adds that behaviour as functions over the generated elements, so generated
structure and hand-written semantics stay cleanly separated.

Derivations are ported from the normative KerML 1.0 abstract syntax
(docs/sysml-v2/omg/20250201/KerML.xmi), not from intuition:

- `owner` = the `owningRelatedElement` of the Element's `owningRelationship`.
- effective `name` = `declaredName` by default.
- `qualified_name` = the ownership-qualified name, composed by walking the
  owning-namespace chain.

Name resolution here is the M1b minimum: same-namespace lookup plus simple
qualified-name resolution from a root namespace. Richer KerML resolution
(imports visibility, inheritance, aliases) is layered in later milestones.
"""

from __future__ import annotations

from collections.abc import Iterator

from gaphor.SysML2.kerml import (
    Element,
    Import,
    Membership,
    Namespace,
    OwningMembership,
)

QUALIFIED_NAME_SEPARATOR = "::"


def add_owned_member(
    namespace: Namespace, member: Element, membership: OwningMembership
) -> OwningMembership:
    """Wire `member` into `namespace` through `membership`, both directions.

    The generated structural model emits each reference as a one-directional
    association (the normative XMI does not declare opposite-end pairings, so
    they cannot be derived without hand-authoring assumptions). KerML's
    owner/member navigation is bidirectional, so that semantic relationship is
    established here, in the behaviour layer: the owning side and the member's
    back-reference are both set, keeping the structural model faithful to the
    XMI while the kernel exposes correct navigation.
    """
    membership.ownedMemberElement = member
    membership.membershipOwningNamespace = namespace
    namespace.ownedMembership = membership
    # Back-references for navigation from the member/membership outward.
    member.owningMembership = membership
    member.owningNamespace = namespace
    return membership


def effective_name(element: Element) -> str | None:
    """The name used during resolution: `declaredName` by default (KerML)."""
    return element.declaredName


def members(namespace: Namespace) -> Iterator[Element]:
    """The member elements of a namespace, via its memberships."""
    for membership in namespace.ownedMembership:
        member = _membership_element(membership)
        if member is not None:
            yield member


def owned_member_named(namespace: Namespace, name: str) -> Element | None:
    """Same-namespace name resolution: find a member by effective name."""
    for member in members(namespace):
        if effective_name(member) == name:
            return member
    return None


def owning_namespace(element: Element) -> Namespace | None:
    """The namespace that owns this element, via its owning membership."""
    for membership in element.owningMembership:
        if isinstance(membership, OwningMembership):
            ns = _membership_namespace(membership)
            if ns is not None:
                return ns
    return None


def qualified_name(element: Element) -> str:
    """Ownership-qualified name: owning-namespace qualified names joined by `::`.

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


def resolve_qualified_name(root: Namespace, qualified: str) -> Element | None:
    """Resolve a `A::B::C` qualified name starting from `root`.

    `root` matches the first segment; each remaining segment is resolved as a
    member of the previously resolved namespace.
    """
    segments = qualified.split(QUALIFIED_NAME_SEPARATOR)
    if not segments:
        return None
    if effective_name(root) != segments[0]:
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
    """Elements brought in by the namespace's owned imports."""
    for imp in namespace.ownedImport:
        target = _import_element(imp)
        if target is not None:
            yield target


# --- internal single-valued accessors over the generated relations -----------
#
# The generated references are `relation_many` (association ends), so these
# helpers take the single expected value where KerML semantics are single-valued.


def _membership_element(membership: Membership) -> Element | None:
    if isinstance(membership, OwningMembership):
        return _single(membership.ownedMemberElement)
    return _single(membership.memberElement)


def _membership_namespace(membership: Membership) -> Namespace | None:
    return _single(membership.membershipOwningNamespace)


def _import_element(imp: Import) -> Element | None:
    return _single(imp.importedElement)


def _single(relation) -> Element | None:
    items = list(relation)
    return items[0] if items else None
