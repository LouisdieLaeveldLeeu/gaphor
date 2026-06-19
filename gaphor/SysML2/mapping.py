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
from functools import lru_cache

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
    """Whether `target` is a kind that `usage` may be typed by.

    An AttributeUsage may be typed by any KerML `DataType`: an AttributeDefinition
    (which is a DataType) or a standard-library value type such as
    `ScalarValues::Real` (materialized as a read-only DataType proxy). For the
    other usage kinds the match is exact (not isinstance), so a
    RequirementDefinition does not satisfy a plain ConstraintUsage and a
    ConstraintDefinition does not satisfy a RequirementUsage. A usage kind with no
    registered definition kind is treated as not matchable.
    """
    if isinstance(usage, sysml2.AttributeUsage):
        return isinstance(target, kerml.DataType)
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
    # relationship element id -> source element id for relationships the mapper
    # creates from a source declaration (currently FeatureTyping from typed
    # usages). Importers can use this to inherit provenance from the declaration.
    relationship_sources: dict[str, str] = field(default_factory=dict)


def map_package(pkg: ast.Package, factory: ElementFactory) -> MappingResult:
    """Build semantic elements for a parsed package into `factory`."""
    root = factory.create(kerml.Namespace)

    # Phase 1: build the whole ownership tree (definitions, usages, nested
    # packages) so every name exists before any type is resolved. Records each
    # typed usage with its owning namespace for phase 2.
    typed_usages: list[tuple[kerml.Feature, kerml.Namespace, tuple[str, ...]]] = []
    top_level = _build_members(pkg.members, root, factory, typed_usages)

    unresolved_types, mistyped, relationship_sources = _resolve_typed_usages(
        root, typed_usages
    )
    return MappingResult(
        root=root,
        elements_by_name=top_level,
        unresolved_types=unresolved_types,
        mistyped=mistyped,
        relationship_sources=relationship_sources,
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
    result, _ = map_project_members([(None, pkg) for pkg in packages], factory)
    return result


def map_project_members(named_packages, factory: ElementFactory):
    """Map `(label, package)` pairs into one shared project namespace.

    Like `map_project`, but also returns a provenance map
    `element.id -> (label, ast_node)` for every created element (including nested
    ones). KPAR import uses the label (source member) and the AST node's source
    line to trace each imported element back to its declaration.
    """
    root = factory.create(kerml.Namespace)
    typed_usages: list[tuple[kerml.Feature, kerml.Namespace, tuple[str, ...]]] = []
    top_level: dict[str, kerml.Element] = {}
    provenance: dict[str, tuple] = {}
    for label, pkg in named_packages:

        def record(element, node, _label=label):
            provenance[element.id] = (_label, node)

        top_level.update(
            _build_members(pkg.members, root, factory, typed_usages, record)
        )

    unresolved_types, mistyped, relationship_sources = _resolve_typed_usages(
        root, typed_usages
    )
    for relationship_id, source_id in relationship_sources.items():
        if source_id in provenance:
            provenance[relationship_id] = provenance[source_id]
    return (
        MappingResult(
            root=root,
            elements_by_name=top_level,
            unresolved_types=unresolved_types,
            mistyped=mistyped,
            relationship_sources=relationship_sources,
        ),
        provenance,
    )


def _resolve_typed_usages(
    root: kerml.Namespace, typed_usages: list
) -> tuple[dict[str, str], dict[str, tuple[str, str]], dict[str, str]]:
    """Resolve usage typing for the collected usages (mapping phase 2).

    Name resolution is nearest-first across enclosing namespaces (see
    `_resolve_type`). A name that does not resolve in the user model is, for an
    AttributeUsage, tried against the standard library (e.g. `attribute x : Real`);
    otherwise it is recorded as unresolved. A name that resolves to the WRONG kind
    is recorded as mistyped. Only a kind match creates the FeatureTyping, so
    nothing is silently dropped and no cross-kind typing is ever stored.
    """
    unresolved_types: dict[str, str] = {}
    mistyped: dict[str, tuple[str, str]] = {}
    relationship_sources: dict[str, str] = {}
    for usage, namespace, type_name in typed_usages:
        target = _resolve_type(namespace, type_name)
        # Only fall back to the standard library when the name resolves to
        # NOTHING in the user model. A user name that resolves to a non-Type
        # (e.g. a local `package Real`) shadows the library and stays
        # unresolved/wrong-kind -- the library never overrides user content.
        if target is None:
            target = _library_value_type(usage, type_name, root)
        if not isinstance(target, kerml.Type):
            unresolved_types[usage.id] = "::".join(type_name)
            continue
        if type_matches_usage_kind(usage, target):
            typing = _set_type(usage, target)
            if typing is not None:
                relationship_sources[typing.id] = usage.id
        else:
            mistyped[usage.id] = ("::".join(type_name), type(target).__name__)
    return unresolved_types, mistyped, relationship_sources


def _build_members(
    members: tuple,
    namespace: kerml.Namespace,
    factory: ElementFactory,
    typed_usages: list,
    on_element=None,
) -> dict[str, kerml.Element]:
    """Create each AST member as an owned member of `namespace`, recursing into
    sub-packages. Returns this level's elements by name.

    If `on_element` is given, it is called as `on_element(element, ast_node)` for
    every created element (including nested ones), so callers can record
    per-element provenance from the AST node (e.g. its source line)."""
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
        if on_element is not None:
            on_element(element, member)
        if isinstance(member, ast.PackageDefinition):
            _build_members(
                member.members, element, factory, typed_usages, on_element
            )
        by_name[member.name] = element
    return by_name


def _resolve_type(
    namespace: kerml.Namespace, type_name: tuple[str, ...]
) -> kerml.Element | None:
    """Resolve a (qualified) type name with nearest-first scoping.

    The first segment is looked up by walking outward from the usage's own
    namespace through each enclosing namespace to the model root; the nearest
    declaration wins (an inner scope shadows an outer one). The remaining
    segments are then navigated as members from that match. This resolves names
    declared in enclosing packages and relative-qualified names (e.g. a sibling
    `A::Engine` referenced from within the same enclosing package), not only
    same-namespace names and root-qualified names.

    Deferred to follow-up phases (they need grammar/semantic support that does
    not exist yet): imports and imported memberships, aliases, inherited members,
    visibility, implicit specialization, and feature chains.
    """
    first, *rest = type_name
    scope: kerml.Namespace | None = namespace
    while scope is not None:
        found = kk.owned_member_named(scope, first)
        if found is not None:
            return _descend(found, rest)
        scope = kk.owning_namespace(scope)
    return None


def _descend(element: kerml.Element, segments: list[str]) -> kerml.Element | None:
    """Navigate qualified `segments` as members from a resolved first match."""
    current: kerml.Element | None = element
    for segment in segments:
        if not isinstance(current, kerml.Namespace):
            return None
        current = kk.owned_member_named(current, segment)
        if current is None:
            return None
    return current


@lru_cache(maxsize=1)
def _standard_library():
    """The pinned standard value-type library, loaded once per process.

    Read-only reference data: used to recognise library value-type names and
    their canonical declared names; the proxies the mapper materialises live in
    the user's own factory, not here.
    """
    from gaphor.SysML2.kpar.library import import_scalar_values_library

    return import_scalar_values_library()


def _library_value_type(
    usage: kerml.Feature, type_name: tuple[str, ...], root: kerml.Namespace
) -> kerml.DataType | None:
    """A read-only proxy DataType for a standard-library value type.

    Only AttributeUsages may be typed by a library value type (e.g.
    `attribute x : Real`). Returns None if `usage` is not an attribute usage or
    the declared name is not a standard-library value type. The proxy is a bare
    `kerml.DataType` owned by the model root: it is a real Type for FeatureTyping,
    persists with the model, and -- being neither a SysML2 construct nor a
    Package -- is invisible to textual export and the round-trip canonical form,
    so the library declaration is never dumped. The contract's amendment treats
    these as read-only, provenance-by-qualified-name references, regenerable from
    the pinned KPAR.
    """
    if not isinstance(usage, sysml2.AttributeUsage):
        return None
    element = _standard_library().resolve("::".join(type_name))
    if not isinstance(element, kerml.DataType):
        return None
    return _value_type_proxy(root, element.declaredName)


def library_value_type_names() -> tuple[str, ...]:
    """Sorted simple names of the concrete standard-library value types.

    For the UI type chooser and the Python API: the value types a user may type
    an attribute by (e.g. Boolean, Integer, Real, String). Abstract library
    bases (ScalarValue, NumericalValue, Number) are excluded.
    """
    return tuple(
        sorted(
            element.declaredName
            for element in _standard_library().elements
            if isinstance(element, kerml.DataType)
            and not element.isAbstract
            and element.declaredName
        )
    )


def set_attribute_library_type(
    usage: sysml2.AttributeUsage, simple_name: str
) -> kerml.FeatureTyping | None:
    """Type an AttributeUsage by a standard-library value type (UI/Python API).

    Materializes (or reuses) the read-only value-type proxy at the usage's model
    root and sets the FeatureTyping, the same representation the text mapper uses.
    `usage` must be a SysML2 AttributeUsage (library value typing applies only to
    attributes); anything else raises `TypeError`. `simple_name` is validated
    against the pinned library and must name a concrete value type (e.g. "Real",
    or "ScalarValues::Real"); anything else raises `ValueError`. Both checks run
    before any mutation, so the API can neither type a non-attribute by a value
    type nor mint arbitrary non-library proxies.
    """
    if not isinstance(usage, sysml2.AttributeUsage):
        raise TypeError(
            "library value typing applies to AttributeUsage, not "
            f"{type(usage).__name__}"
        )
    element = _standard_library().resolve(simple_name)
    if not isinstance(element, kerml.DataType) or element.isAbstract:
        raise ValueError(
            f"{simple_name!r} is not a concrete standard-library value type"
        )
    return _set_type(usage, _value_type_proxy(_root_of(usage), element.declaredName))


def _root_of(element: kerml.Element) -> kerml.Namespace:
    current: kerml.Element = element
    while True:
        owner = kk.owning_namespace(current)
        if owner is None:
            return current  # type: ignore[return-value]
        current = owner


def _value_type_proxy(root: kerml.Namespace, simple_name: str) -> kerml.DataType:
    """Find or create the read-only library value-type proxy named `simple_name`
    owned by `root` (one proxy per library type per model root)."""
    factory = root.model
    for existing in factory.select(kerml.DataType):
        if (
            type(existing) is kerml.DataType
            and existing.declaredName == simple_name
            and kk.owning_namespace(existing) is root
        ):
            return existing
    proxy = factory.create(kerml.DataType)
    proxy.declaredName = simple_name
    kk.add_owned_member(root, proxy, factory.create(kerml.OwningMembership))
    return proxy


def _set_type(
    usage: kerml.Feature, definition: kerml.Type
) -> kerml.FeatureTyping | None:
    """Record that `usage` is typed by `definition` via a KerML FeatureTyping.

    Ownership follows KerML: the FeatureTyping is owned by the typed feature
    (its `owningFeature` is "a typedFeature that is also the owningRelatedElement
    of this FeatureTyping"). So the usage owns the typing through the containment
    spine -- deleting the usage cascades to the typing -- while the definition is
    only the non-owning `type` target and is never cascade-deleted.
    """
    return kk.set_feature_type(usage, definition)
