"""Map the SysML v2 AST onto semantic elements.

Turns a parsed `Package` AST into generated SysML/KerML elements in an
`ElementFactory`, building the KerML ownership spine so the kernel's derived
surface (members, qualified names) works:

- `part def Engine;`            -> a `PartDefinition` owned by its namespace
- `part vehicleEngine : Engine;`-> a `PartUsage` owned by its namespace, typed
  by the referenced definition (via a `FeatureTyping`)
- `package P { ... }`           -> a `Package` (a KerML Namespace) owned by its
  parent, recursively owning its own members and sub-packages

Mapping is two-phase: phase 1 creates the full ownership tree (so every name
exists before resolution), phase 2 resolves usage typing. Typing is recorded
with a `FeatureTyping` owned by the usage. An unresolved type name is recorded
(not silently dropped) for validation to report.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gaphor.core.modeling import ElementFactory
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.grammar import ast


# Each usage kind is typed by exactly one definition kind. The pairing is exact,
# not by subclassing: a RequirementUsage must be typed by a RequirementDefinition
# (not a plain ConstraintDefinition), and a ConstraintUsage by a
# ConstraintDefinition (NOT a RequirementDefinition, even though that subclasses
# ConstraintDefinition). This is the kind-specific typing contract the support
# matrix describes; it is the single source of truth shared by the mapper (which
# refuses a cross-kind type) and validation (which reports it).
USAGE_DEFINITION_KIND: dict[type, type] = {
    sysml2.PartUsage: sysml2.PartDefinition,
    sysml2.AttributeUsage: sysml2.AttributeDefinition,
    sysml2.ActionUsage: sysml2.ActionDefinition,
    sysml2.ConstraintUsage: sysml2.ConstraintDefinition,
    sysml2.RequirementUsage: sysml2.RequirementDefinition,
    sysml2.PortUsage: sysml2.PortDefinition,
    sysml2.ConnectionUsage: sysml2.ConnectionDefinition,
}


def is_managed_usage_kind(usage: kerml.Feature) -> bool:
    """Whether `usage` is one of the SysML usage kinds whose typing kind is
    governed by `USAGE_DEFINITION_KIND` (exact-type membership, so a future
    usage subclass is not silently assumed to share a parent's contract)."""
    return type(usage) in USAGE_DEFINITION_KIND


def type_matches_usage_kind(usage: kerml.Feature, target: kerml.Type) -> bool:
    """Whether `target` is the exact definition kind that `usage` must be typed by.

    Exact-type match (not isinstance), so a RequirementDefinition does not satisfy
    a plain ConstraintUsage and a ConstraintDefinition does not satisfy a
    RequirementUsage. A usage kind with no registered definition kind is treated
    as not matchable (it has no valid textual typing yet).
    """
    required = USAGE_DEFINITION_KIND.get(type(usage))
    return required is not None and type(target) is required


@dataclass
class MappingResult:
    root: kerml.Namespace
    # top-level members by name (nested members are reached via the model).
    elements_by_name: dict[str, kerml.Element]
    # usage element id -> declared type name that did not resolve (for the
    # usage-without-valid-type validation rule).
    unresolved_types: dict[str, str] = field(default_factory=dict)
    # usage element id -> (declared type name, resolved-type kind name) for a type
    # that resolved but is the WRONG kind for the usage (cross-kind typing).
    mistyped: dict[str, tuple[str, str]] = field(default_factory=dict)


def map_package(pkg: ast.Package, factory: ElementFactory) -> MappingResult:
    """Build semantic elements for a parsed package into `factory`."""
    root = factory.create(kerml.Namespace)

    # Phase 1: build the whole ownership tree (definitions, usages, nested
    # packages) so every name exists before any type is resolved. Records each
    # typed usage with its owning namespace for phase 2.
    typed_usages: list[tuple[sysml2.PartUsage, kerml.Namespace, tuple[str, ...]]] = []
    top_level = _build_members(pkg.members, root, factory, typed_usages)

    unresolved_types, mistyped = _resolve_typed_usages(root, typed_usages)
    return MappingResult(
        root=root,
        elements_by_name=top_level,
        unresolved_types=unresolved_types,
        mistyped=mistyped,
    )


def map_project(packages, factory: ElementFactory) -> MappingResult:
    """Map several parsed packages into one shared project namespace.

    Used for KPAR project import: every package's top-level members are built
    under a single root, then typing is resolved project-wide -- so a qualified
    name resolves against any imported member (cross-file references inside the
    same project resolve), while a name that belongs to no imported member stays
    unresolved (recorded, never silently dropped). Resolution scope is otherwise
    the same as `map_package`.
    """
    root = factory.create(kerml.Namespace)
    typed_usages: list[tuple[sysml2.PartUsage, kerml.Namespace, tuple[str, ...]]] = []
    top_level: dict[str, kerml.Element] = {}
    for pkg in packages:
        top_level.update(_build_members(pkg.members, root, factory, typed_usages))

    unresolved_types, mistyped = _resolve_typed_usages(root, typed_usages)
    return MappingResult(
        root=root,
        elements_by_name=top_level,
        unresolved_types=unresolved_types,
        mistyped=mistyped,
    )


def _resolve_typed_usages(
    root: kerml.Namespace, typed_usages: list
) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    """Resolve usage typing for the collected usages (mapping phase 2).

    A simple name resolves in the usage's own namespace; a qualified name resolves
    from the root. A name that does not resolve to a Type is recorded as
    unresolved; one that resolves to the WRONG kind is recorded as mistyped. Only
    an exact-kind match creates the FeatureTyping, so nothing is silently dropped
    and no cross-kind typing is ever stored.
    """
    unresolved_types: dict[str, str] = {}
    mistyped: dict[str, tuple[str, str]] = {}
    for usage, namespace, type_name in typed_usages:
        target = _resolve_type(root, namespace, type_name)
        if not isinstance(target, kerml.Type):
            unresolved_types[usage.id] = "::".join(type_name)
        elif type_matches_usage_kind(usage, target):
            _set_type(usage, target)
        else:
            mistyped[usage.id] = ("::".join(type_name), type(target).__name__)
    return unresolved_types, mistyped


def _build_members(
    members: tuple,
    namespace: kerml.Namespace,
    factory: ElementFactory,
    typed_usages: list,
) -> dict[str, kerml.Element]:
    """Create each AST member as an owned member of `namespace`, recursing into
    sub-packages. Returns this level's elements by name."""
    by_name: dict[str, kerml.Element] = {}
    for member in members:
        if isinstance(member, ast.PartDefinition):
            element: kerml.Element = factory.create(sysml2.PartDefinition)
        elif isinstance(member, ast.AttributeDefinition):
            element = factory.create(sysml2.AttributeDefinition)
        elif isinstance(member, ast.PartUsage):
            element = factory.create(sysml2.PartUsage)
            if member.type_name is not None:
                typed_usages.append((element, namespace, member.type_name))
        elif isinstance(member, ast.AttributeUsage):
            element = factory.create(sysml2.AttributeUsage)
            if member.type_name is not None:
                typed_usages.append((element, namespace, member.type_name))
        elif isinstance(member, ast.ActionDefinition):
            element = factory.create(sysml2.ActionDefinition)
        elif isinstance(member, ast.ActionUsage):
            element = factory.create(sysml2.ActionUsage)
            if member.type_name is not None:
                typed_usages.append((element, namespace, member.type_name))
        elif isinstance(member, ast.ConstraintDefinition):
            element = factory.create(sysml2.ConstraintDefinition)
        elif isinstance(member, ast.ConstraintUsage):
            element = factory.create(sysml2.ConstraintUsage)
            if member.type_name is not None:
                typed_usages.append((element, namespace, member.type_name))
        elif isinstance(member, ast.RequirementDefinition):
            element = factory.create(sysml2.RequirementDefinition)
        elif isinstance(member, ast.RequirementUsage):
            element = factory.create(sysml2.RequirementUsage)
            if member.type_name is not None:
                typed_usages.append((element, namespace, member.type_name))
        elif isinstance(member, ast.PortDefinition):
            element = factory.create(sysml2.PortDefinition)
        elif isinstance(member, ast.PortUsage):
            element = factory.create(sysml2.PortUsage)
            if member.type_name is not None:
                typed_usages.append((element, namespace, member.type_name))
        elif isinstance(member, ast.ConnectionDefinition):
            element = factory.create(sysml2.ConnectionDefinition)
        elif isinstance(member, ast.ConnectionUsage):
            element = factory.create(sysml2.ConnectionUsage)
            if member.type_name is not None:
                typed_usages.append((element, namespace, member.type_name))
        elif isinstance(member, ast.PackageDefinition):
            element = factory.create(kerml.Package)
        else:  # pragma: no cover - AST node types are exhaustive
            raise TypeError(f"unsupported AST member: {member!r}")
        element.declaredName = member.name
        kk.add_owned_member(
            namespace, element, factory.create(kerml.OwningMembership)
        )
        if isinstance(member, ast.PackageDefinition):
            _build_members(member.members, element, factory, typed_usages)
        by_name[member.name] = element
    return by_name


def _resolve_type(
    root: kerml.Namespace,
    namespace: kerml.Namespace,
    type_name: tuple[str, ...],
) -> kerml.Element | None:
    """Resolve a (qualified) type name. M2-scoped: a simple name resolves in the
    usage's own namespace; a qualified name resolves from the root. No
    inheritance, visibility, aliases, or feature chains."""
    if len(type_name) == 1:
        return kk.owned_member_named(namespace, type_name[0])
    # Qualified name: resolve relative to the implicit root (its first segment
    # is a top-level member, e.g. Vehicles::Engine).
    return kk.resolve_in_namespace(root, "::".join(type_name))


def _set_type(usage: kerml.Feature, definition: kerml.Type) -> None:
    """Record that `usage` is typed by `definition` via a KerML FeatureTyping.

    Ownership follows KerML: the FeatureTyping is owned by the typed feature
    (its `owningFeature` is "a typedFeature that is also the owningRelatedElement
    of this FeatureTyping"). So the usage owns the typing through the containment
    spine -- deleting the usage cascades to the typing -- while the definition is
    only the non-owning `type` target and is never cascade-deleted.
    """
    kk.set_feature_type(usage, definition)
