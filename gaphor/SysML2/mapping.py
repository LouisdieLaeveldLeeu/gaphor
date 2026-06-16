"""Map the SysML v2 AST onto semantic elements (M2 sub-step 2).

Turns a parsed `Package` AST into generated SysML/KerML elements in an
`ElementFactory`, building the KerML ownership spine so the kernel's derived
surface (members, qualified names) works:

- `part def Engine;`            -> a `PartDefinition` owned by the root namespace
- `part vehicleEngine : Engine;`-> a `PartUsage` owned by the root namespace,
  typed by the referenced definition

Typing is recorded with a `FeatureTyping` relationship (the usage is the typed
feature, the definition its type). Diagnostics for unresolved types are a
validation concern (M2 sub-step 4); here an unresolved type name is left
unresolved on the usage so validation can report it.
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
    elements_by_name: dict[str, kerml.Element]
    # usage element id -> declared type name that did not resolve (for the
    # usage-without-valid-type validation rule).
    unresolved_types: dict[str, str] = field(default_factory=dict)


def map_package(pkg: ast.Package, factory: ElementFactory) -> MappingResult:
    """Build semantic elements for a parsed package into `factory`."""
    root = factory.create(kerml.Namespace)
    by_name: dict[str, kerml.Element] = {}
    unresolved_types: dict[str, str] = {}

    # First pass: create definitions and usages as owned members of the root.
    for member in pkg.members:
        if isinstance(member, ast.PartDefinition):
            element: kerml.Element = factory.create(sysml2.PartDefinition)
        elif isinstance(member, ast.PartUsage):
            element = factory.create(sysml2.PartUsage)
        else:  # pragma: no cover - AST has only these two node types in M2
            raise TypeError(f"unsupported AST member: {member!r}")
        element.declaredName = member.name
        kk.add_owned_member(root, element, factory.create(kerml.OwningMembership))
        by_name[member.name] = element

    # Second pass: resolve usage typing now that all names exist. An unresolved
    # type name is recorded (not silently dropped) for validation to report.
    for member in pkg.members:
        if isinstance(member, ast.PartUsage) and member.type_name is not None:
            usage = by_name[member.name]
            target = _resolve_type(root, member.type_name)
            if target is not None:
                _set_type(factory, usage, target)
            else:
                unresolved_types[usage.id] = "::".join(member.type_name)

    return MappingResult(
        root=root,
        elements_by_name=by_name,
        unresolved_types=unresolved_types,
    )


def _resolve_type(
    root: kerml.Namespace, type_name: tuple[str, ...]
) -> kerml.Element | None:
    """Resolve a (qualified) type name: same-namespace or simple qualified name.

    M2-scoped resolution only (no inheritance/visibility/aliases).
    """
    if len(type_name) == 1:
        return kk.owned_member_named(root, type_name[0])
    return kk.resolve_qualified_name(root, "::".join(type_name))


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
