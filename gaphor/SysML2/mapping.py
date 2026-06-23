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
from gaphor.SysML2 import conjugation
from gaphor.SysML2 import constraints
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2 import requirements
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
    sysml2.ConcernUsage: sysml2.ConcernDefinition,
    sysml2.PortUsage: sysml2.PortDefinition,
    sysml2.ConnectionUsage: sysml2.ConnectionDefinition,
    sysml2.InterfaceUsage: sysml2.InterfaceDefinition,
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
    if isinstance(usage, sysml2.PortUsage):
        # A port may be typed by a PortDefinition or, for `: ~Fuel`, its
        # conjugate (a ConjugatedPortDefinition IS a PortDefinition), so the
        # match is by subclass here -- the only PortDefinition subclass.
        return isinstance(target, sysml2.PortDefinition)
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
    # connection element id -> the declared connector-end references that did not
    # resolve to a feature (broken or kind-mismatched endpoints), for the
    # connection-end validation rule.
    unresolved_ends: dict[str, list[str]] = field(default_factory=dict)
    # framed-concern ConcernUsage id -> the `frame <ref>` name that did not resolve
    # to a ConcernUsage, for the framed-concern-reference validation rule (6d-2).
    unresolved_frame_refs: dict[str, str] = field(default_factory=dict)


def map_package(pkg: ast.Package, factory: ElementFactory) -> MappingResult:
    """Build semantic elements for a parsed package into `factory`."""
    root = factory.create(kerml.Namespace)

    # Phase 1: build the whole ownership tree (definitions, usages, nested
    # packages) so every name exists before any type is resolved. Records each
    # typed usage with its owning namespace for phase 2.
    typed_usages: list[tuple[kerml.Feature, kerml.Namespace, tuple[str, ...]]] = []
    connection_ends: list = []
    subject_typings: list = []
    frame_references: list = []
    top_level = _build_members(
        pkg.members,
        root,
        factory,
        typed_usages,
        connection_ends,
        subject_typings,
        frame_references,
    )

    unresolved_types, mistyped, relationship_sources = _resolve_typed_usages(
        root, typed_usages
    )
    unresolved_ends = _resolve_connection_ends(connection_ends)
    unresolved_types.update(_resolve_subject_types(subject_typings))
    unresolved_frame_refs = _resolve_frame_references(frame_references)
    return MappingResult(
        root=root,
        elements_by_name=top_level,
        unresolved_types=unresolved_types,
        mistyped=mistyped,
        relationship_sources=relationship_sources,
        unresolved_ends=unresolved_ends,
        unresolved_frame_refs=unresolved_frame_refs,
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
    connection_ends: list = []
    subject_typings: list = []
    frame_references: list = []
    top_level: dict[str, kerml.Element] = {}
    provenance: dict[str, tuple] = {}
    for label, pkg in named_packages:

        def record(element, node, _label=label):
            provenance[element.id] = (_label, node)

        top_level.update(
            _build_members(
                pkg.members,
                root,
                factory,
                typed_usages,
                connection_ends,
                subject_typings,
                frame_references,
                record,
            )
        )

    unresolved_types, mistyped, relationship_sources = _resolve_typed_usages(
        root, typed_usages
    )
    unresolved_ends = _resolve_connection_ends(connection_ends)
    unresolved_types.update(_resolve_subject_types(subject_typings))
    unresolved_frame_refs = _resolve_frame_references(frame_references)
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
            unresolved_ends=unresolved_ends,
            unresolved_frame_refs=unresolved_frame_refs,
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

    A conjugated port typing (`port p : ~Fuel`) resolves its name like a normal
    typing but must land on a PortDefinition; on a match it is typed by the
    definition's conjugate via a ConjugatedPortTyping (see `conjugation`).
    """
    unresolved_types: dict[str, str] = {}
    mistyped: dict[str, tuple[str, str]] = {}
    relationship_sources: dict[str, str] = {}
    for usage, namespace, type_name, conjugated in typed_usages:
        target = _resolve_type(namespace, type_name)
        # Only fall back to the standard library when the name resolves to
        # NOTHING in the user model. A user name that resolves to a non-Type
        # (e.g. a local `package Real`) shadows the library and stays
        # unresolved/wrong-kind -- the library never overrides user content.
        if target is None:
            target = _library_value_type(usage, type_name, root)
        display_name = ("~" if conjugated else "") + "::".join(type_name)
        if not isinstance(target, kerml.Type):
            unresolved_types[usage.id] = display_name
            continue
        if conjugated:
            # `~<type>` must reference a PortDefinition; its conjugate types p.
            if isinstance(target, sysml2.PortDefinition):
                typing = conjugation.set_conjugated_port_type(usage, target)
                relationship_sources[typing.id] = usage.id
            else:
                mistyped[usage.id] = (display_name, type(target).__name__)
            continue
        if type_matches_usage_kind(usage, target):
            typing = _set_type(usage, target)
            if typing is not None:
                relationship_sources[typing.id] = usage.id
        else:
            mistyped[usage.id] = ("::".join(type_name), type(target).__name__)
    return unresolved_types, mistyped, relationship_sources


def _resolve_connection_ends(connection_ends: list) -> dict[str, list[str]]:
    """Resolve binary connector endpoints to features (mapping phase 2).

    Each endpoint name is resolved nearest-first from the connection's namespace.
    A binary connection's ends are ATOMIC: source and target are set together
    only when BOTH names resolve to a `Feature` (a usage). If either name does not
    resolve, or resolves to a non-feature (a package or a definition), the broken
    name(s) are recorded and NEITHER end is set -- the connect clause is reported
    as broken (`broken-connection-end`) rather than materialised half-formed. This
    keeps the model from ever holding a one-ended binary connection, which has no
    valid textual form and would otherwise be dropped silently on export.
    """
    unresolved_ends: dict[str, list[str]] = {}
    for connection, namespace, source_name, target_name in connection_ends:
        broken: list[str] = []
        resolved: dict[str, kerml.Feature] = {}
        for name, setter in (
            (source_name, "source"),
            (target_name, "target"),
        ):
            target = _resolve_type(namespace, name)
            if isinstance(target, kerml.Feature):
                resolved[setter] = target
            else:
                broken.append("::".join(name))
        if broken:
            unresolved_ends[connection.id] = broken
        else:
            for setter, feature in resolved.items():
                setattr(connection, setter, feature)
    return unresolved_ends


def _resolve_frame_references(frame_references: list) -> dict[str, str]:
    """Resolve each framed-concern REFERENCE to an existing ConcernUsage (phase 2).

    `frame <ref>` owns an anonymous ConcernUsage that REFERENCES an existing
    concern. The name is resolved nearest-first from the requirement's namespace; a
    name that resolves to a ConcernUsage gets a ReferenceSubsetting linking the
    anonymous usage to it, otherwise it is recorded unresolved (a name resolving to
    a non-ConcernUsage -- e.g. a ConcernDefinition or a part -- is wrong-kind and
    also recorded, never silently dropped).
    """
    unresolved: dict[str, str] = {}
    for concern, namespace, target in frame_references:
        referenced = _resolve_type(namespace, target)
        if isinstance(referenced, sysml2.ConcernUsage):
            kk.add_reference_subsetting(concern, referenced)
        else:
            unresolved[concern.id] = "::".join(target)
    return unresolved


def _build_requirement_body(
    requirement,
    member,
    namespace,
    factory,
    typed_usages,
    subject_typings,
    frame_references,
    on_element,
):
    """Build a requirement's subject/assume/require/actor/stakeholder parts and
    its reqId (Phase 6b/6c).

    The subject becomes a parameter `kerml.Feature` via a SubjectMembership (its
    type resolved in phase 2 via `subject_typings`, where ANY Type matches -- a
    subject parameter is not kind-specific). The actor/stakeholder become
    `sysml2.PartUsage` parameters (the pinned XMI types ActorMembership::
    ownedActorParameter and StakeholderMembership::ownedStakeholderParameter as
    PartUsage), so their types resolve through the SAME kind-checked path as every
    other PartUsage (`typed_usages` -> PartDefinition); a wrong-kind type is
    reported, not silently accepted. Each assumed/required constraint becomes a
    ConstraintUsage carrying an opaque 6a body, owned via a
    RequirementConstraintMembership with the matching kind. The reqId is stored as
    the requirement's declaredShortName.
    """

    def record(element):
        if on_element is not None:
            on_element(element, member)

    if member.reqId is not None:
        requirements.set_reqId(requirement, member.reqId)

    if member.subject is not None:
        subj = factory.create(kerml.Feature)
        subj.declaredName = member.subject.name
        requirements.add_subject(requirement, subj)
        record(subj)
        if member.subject.type_name is not None:
            subject_typings.append((subj, namespace, member.subject.type_name))

    for clauses, add in (
        (member.actors, requirements.add_actor),
        (member.stakeholders, requirements.add_stakeholder),
    ):
        for clause in clauses:
            usage = factory.create(sysml2.PartUsage)
            usage.declaredName = clause.name
            add(requirement, usage)
            record(usage)
            if clause.type_name is not None:
                typed_usages.append((usage, namespace, clause.type_name, False))

    # A framed concern is a ConcernUsage owned via a FramedConcernMembership (Phase
    # 6d). Two forms: DECLARE (`frame concern <name> [: <C>]`, 6d-1) builds a named
    # usage whose type is kind-checked (ConcernUsage -> ConcernDefinition) through
    # the shared typed-usage path; REFERENCE (`frame <existing>`, 6d-2) builds an
    # anonymous usage and resolves `target` in phase 2 to an existing ConcernUsage,
    # linking them with a ReferenceSubsetting.
    for clause in member.framedConcerns:
        concern = factory.create(sysml2.ConcernUsage)
        if isinstance(clause, ast.FrameReference):
            requirements.add_framed_concern(requirement, concern)
            record(concern)
            frame_references.append((concern, namespace, clause.target))
        else:
            concern.declaredName = clause.name
            requirements.add_framed_concern(requirement, concern)
            record(concern)
            if clause.type_name is not None:
                typed_usages.append((concern, namespace, clause.type_name, False))

    for kind, bodies in (
        (requirements.Assumption, member.assume),
        (requirements.Requirement, member.require),
    ):
        for body in bodies:
            constraint = factory.create(sysml2.ConstraintUsage)
            constraints.set_body_text(constraint, body)
            requirements.add_requirement_constraint(requirement, constraint, kind)
            record(constraint)


def _resolve_subject_types(subject_typings: list) -> dict[str, str]:
    """Resolve each requirement SUBJECT's declared type (mapping phase 2).

    A subject may be typed by ANY Type (it is a parameter, not a kind-specific
    usage), so there is no kind check; a name that resolves to a Type sets the
    FeatureTyping, otherwise it is recorded unresolved. (Actor/stakeholder are
    PartUsage and resolve through the kind-checked `_resolve_typed_usages` path.)
    """
    unresolved: dict[str, str] = {}
    for feature, namespace, type_name in subject_typings:
        target = _resolve_type(namespace, type_name)
        if isinstance(target, kerml.Type):
            kk.set_feature_type(feature, target)
        else:
            unresolved[feature.id] = "::".join(type_name)
    return unresolved


def _build_members(
    members: tuple,
    namespace: kerml.Namespace,
    factory: ElementFactory,
    typed_usages: list,
    connection_ends: list,
    subject_typings: list,
    frame_references: list,
    on_element=None,
    owner_is_type: bool = False,
) -> dict[str, kerml.Element]:
    """Create each AST member as an owned member of `namespace`, recursing into
    sub-packages. Returns this level's elements by name.

    Typed usages (including requirement actor/stakeholder PartUsages) are recorded
    in `typed_usages`, connection endpoints in `connection_ends`, requirement
    SUBJECT types in `subject_typings`, and framed-concern references in
    `frame_references` for phase-2 resolution. If `on_element` is given, it is
    called as `on_element(element, ast_node)` for every created element (including
    nested ones), so callers can record per-element provenance from the AST node
    (e.g. its source line)."""
    by_name: dict[str, kerml.Element] = {}
    for member in members:
        if isinstance(member, ast.PartDefinition):
            element: kerml.Element = factory.create(sysml2.PartDefinition)
        elif isinstance(member, ast.AttributeDefinition):
            element = factory.create(sysml2.AttributeDefinition)
        elif isinstance(member, ast.PartUsage):
            element = factory.create(sysml2.PartUsage)
            if member.type_name is not None:
                typed_usages.append((element, namespace, member.type_name, False))
        elif isinstance(member, ast.AttributeUsage):
            element = factory.create(sysml2.AttributeUsage)
            if member.type_name is not None:
                typed_usages.append((element, namespace, member.type_name, False))
        elif isinstance(member, ast.ActionDefinition):
            element = factory.create(sysml2.ActionDefinition)
        elif isinstance(member, ast.ActionUsage):
            element = factory.create(sysml2.ActionUsage)
            if member.type_name is not None:
                typed_usages.append((element, namespace, member.type_name, False))
        elif isinstance(member, ast.SuccessionUsage):
            # A binary control-flow connector; its two ends resolve through the
            # SAME nearest-first connection-end machinery as a connection (Phase 7).
            element = factory.create(sysml2.SuccessionAsUsage)
            connection_ends.append(
                (element, namespace, member.source, member.target)
            )
        elif isinstance(member, ast.FlowUsage):
            element = factory.create(sysml2.FlowUsage)
            connection_ends.append(
                (element, namespace, member.source, member.target)
            )
        elif isinstance(member, ast.ConstraintDefinition):
            element = factory.create(sysml2.ConstraintDefinition)
        elif isinstance(member, ast.ConstraintUsage):
            element = factory.create(sysml2.ConstraintUsage)
            if member.type_name is not None:
                typed_usages.append((element, namespace, member.type_name, False))
        elif isinstance(member, ast.RequirementDefinition):
            element = factory.create(sysml2.RequirementDefinition)
            _build_requirement_body(
                element, member, namespace, factory, typed_usages, subject_typings,
                frame_references, on_element,
            )
        elif isinstance(member, ast.RequirementUsage):
            element = factory.create(sysml2.RequirementUsage)
            if member.type_name is not None:
                typed_usages.append((element, namespace, member.type_name, False))
            _build_requirement_body(
                element, member, namespace, factory, typed_usages, subject_typings,
                frame_references, on_element,
            )
        elif isinstance(member, ast.ConcernDefinition):
            element = factory.create(sysml2.ConcernDefinition)
            _build_requirement_body(
                element, member, namespace, factory, typed_usages, subject_typings,
                frame_references, on_element,
            )
        elif isinstance(member, ast.ConcernUsage):
            element = factory.create(sysml2.ConcernUsage)
            if member.type_name is not None:
                typed_usages.append((element, namespace, member.type_name, False))
            _build_requirement_body(
                element, member, namespace, factory, typed_usages, subject_typings,
                frame_references, on_element,
            )
        elif isinstance(member, ast.PortDefinition):
            element = factory.create(sysml2.PortDefinition)
        elif isinstance(member, ast.PortUsage):
            element = factory.create(sysml2.PortUsage)
            if member.type_name is not None:
                typed_usages.append(
                    (element, namespace, member.type_name, member.conjugated)
                )
        elif isinstance(member, ast.ConnectionDefinition):
            element = factory.create(sysml2.ConnectionDefinition)
        elif isinstance(member, ast.ConnectionUsage):
            element = factory.create(sysml2.ConnectionUsage)
            if member.type_name is not None:
                typed_usages.append((element, namespace, member.type_name, False))
            if member.source is not None and member.target is not None:
                connection_ends.append(
                    (element, namespace, member.source, member.target)
                )
        elif isinstance(member, ast.InterfaceDefinition):
            element = factory.create(sysml2.InterfaceDefinition)
        elif isinstance(member, ast.InterfaceUsage):
            # An InterfaceUsage IS a ConnectionUsage: same typing + binary
            # connector-end machinery (Phase 9), one definition kind deeper.
            element = factory.create(sysml2.InterfaceUsage)
            if member.type_name is not None:
                typed_usages.append((element, namespace, member.type_name, False))
            if member.source is not None and member.target is not None:
                connection_ends.append(
                    (element, namespace, member.source, member.target)
                )
        elif isinstance(member, ast.PackageDefinition):
            element = factory.create(kerml.Package)
        else:  # pragma: no cover - AST node types are exhaustive
            raise TypeError(f"unsupported AST member: {member!r}")
        # A succession/flow connector may be anonymous (no declared name).
        if member.name is not None:
            element.declaredName = member.name
        # A usage may carry a feature direction (`in`/`out`/`inout`); definitions
        # do not (no `direction` field). Undirected stays None (the nullable
        # default), distinct from any direction.
        direction = getattr(member, "direction", None)
        if direction is not None:
            element.direction = kerml.FeatureDirectionKind(direction)
        # A constraint body is preserved as opaque text (Phase 6a); only the
        # constraint AST nodes carry `body`, so this is a no-op for the rest.
        body = getattr(member, "body", None)
        if body is not None:
            constraints.set_body_text(element, body)
        # When the owner is a Type (an action body), its FEATURES (usages: parts,
        # actions, parameters, successions, flows) are owned via FeatureMembership;
        # NON-feature members (nested definitions, packages) are ordinary namespace
        # members via OwningMembership. A non-Type namespace (package) owns
        # everything via OwningMembership. So a FeatureMembership never points at a
        # non-feature (Phase 7 review fix).
        if owner_is_type and isinstance(element, kerml.Feature):
            membership: kerml.OwningMembership = factory.create(kerml.FeatureMembership)
        else:
            membership = factory.create(kerml.OwningMembership)
        kk.add_owned_member(namespace, element, membership)
        if on_element is not None:
            on_element(element, member)
        if isinstance(member, ast.PackageDefinition):
            _build_members(
                member.members,
                element,
                factory,
                typed_usages,
                connection_ends,
                subject_typings,
                frame_references,
                on_element,
            )
        elif isinstance(member, (ast.ActionDefinition, ast.ActionUsage)):
            # An action IS a Type, so its body members are owned per-kind: usages
            # (Features -- steps, directed parameters, successions, flows) via
            # FeatureMembership, nested definitions/packages via OwningMembership
            # (Phase 7). `owner_is_type=True` selects that split per member.
            _build_members(
                member.members,
                element,
                factory,
                typed_usages,
                connection_ends,
                subject_typings,
                frame_references,
                on_element,
                owner_is_type=True,
            )
        if member.name is not None:
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
        # Skip library value-type proxies: they are typing targets reached only
        # through `_library_value_type`, not user-authored symbols. Binding to one
        # here would make resolution declaration-order-dependent (a proxy created
        # for an earlier usage would change how a later name resolves).
        if found is not None and not _is_library_proxy(found):
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
        if current is None or _is_library_proxy(current):
            return None
    return current


def _is_library_proxy(element: kerml.Element) -> bool:
    """A read-only standard-library value-type proxy (a bare ``kerml.DataType``).

    User constructs are SysML2 subclasses (AttributeDefinition, ...) or KerML
    Packages; only the value-type proxies materialized by `_value_type_proxy` are
    bare DataTypes. They are excluded from name resolution so user-symbol lookup
    is independent of whether/when a proxy was created.
    """
    return type(element) is kerml.DataType


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
