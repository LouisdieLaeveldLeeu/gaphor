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


@dataclass
class MappingResult:
    root: kerml.Namespace
    # top-level members by name (nested members are reached via the model).
    elements_by_name: dict[str, kerml.Element]
    # usage element id -> declared type name that did not resolve (for the
    # usage-without-valid-type validation rule).
    unresolved_types: dict[str, str] = field(default_factory=dict)


def map_package(pkg: ast.Package, factory: ElementFactory) -> MappingResult:
    """Build semantic elements for a parsed package into `factory`."""
    root = factory.create(kerml.Namespace)
    unresolved_types: dict[str, str] = {}

    # Phase 1: build the whole ownership tree (definitions, usages, nested
    # packages) so every name exists before any type is resolved. Records each
    # typed usage with its owning namespace for phase 2.
    typed_usages: list[tuple[sysml2.PartUsage, kerml.Namespace, tuple[str, ...]]] = []
    top_level = _build_members(pkg.members, root, factory, typed_usages)

    # Phase 2: resolve usage typing. Resolution is scoped: a simple name resolves
    # in the usage's own namespace; a qualified name resolves from the root.
    for usage, namespace, type_name in typed_usages:
        target = _resolve_type(root, namespace, type_name)
        if target is not None:
            _set_type(factory, usage, target)
        else:
            unresolved_types[usage.id] = "::".join(type_name)

    return MappingResult(
        root=root,
        elements_by_name=top_level,
        unresolved_types=unresolved_types,
    )


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
        elif isinstance(member, ast.PartUsage):
            element = factory.create(sysml2.PartUsage)
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


def _set_type(
    factory: ElementFactory, usage: kerml.Feature, definition: kerml.Type
) -> None:
    """Record that `usage` is typed by `definition` via a KerML FeatureTyping.

    Ownership follows KerML: the FeatureTyping is owned by the typed feature
    (its `owningFeature` is "a typedFeature that is also the owningRelatedElement
    of this FeatureTyping"). So the usage owns the typing through the containment
    spine -- deleting the usage cascades to the typing -- while the definition is
    only the non-owning `type` target and is never cascade-deleted.
    """
    typing = factory.create(kerml.FeatureTyping)
    typing.typedFeature = usage
    typing.type = definition
    # The usage owns the typing relationship (composite containment spine).
    usage.ownedRelationship = typing
    typing.owningRelatedElement = usage
