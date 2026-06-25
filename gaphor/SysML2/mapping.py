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

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache

from gaphor.core.modeling import ElementFactory
from gaphor.SysML2 import conjugation
from gaphor.SysML2 import constraints
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2 import requirements
from gaphor.SysML2.element_id import assign_element_ids
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
    # element id -> the (qualified) name that was visible from MORE THAN ONE import
    # and so did not bind, for the ambiguous-name validation rule (Phase 5a).
    ambiguous: dict[str, str] = field(default_factory=dict)
    # definition element id -> the LIST of declared `:> Super` supertype names that
    # did not resolve to a Classifier (no Subclassification created), for the
    # unresolved-specialization validation rule (Phase 5c). All unresolved supertypes
    # of a `:> A, B` are recorded, so none is dropped.
    unresolved_supertypes: dict[str, list[str]] = field(default_factory=dict)
    # usage element id -> the declared `:> y` subsetted feature name that did not
    # resolve to a Feature (no Subsetting created), for the unresolved-subsetting
    # validation rule (Phase 5c).
    unresolved_subsettings: dict[str, str] = field(default_factory=dict)
    # usage element id -> the declared `:>> y` redefined feature name that did not
    # resolve to a Feature (no Redefinition created), for the unresolved-redefinition
    # validation rule (Phase 5c-2).
    unresolved_redefinitions: dict[str, str] = field(default_factory=dict)
    # usage element id -> the declared `:>> y` name that denotes the redefining
    # feature ITSELF (a feature cannot redefine itself; no Redefinition created), for
    # the self-redefinition validation rule (Phase 5c-2 finding fix).
    self_redefinitions: dict[str, str] = field(default_factory=dict)


@dataclass
class _MappingContext:
    """Mutable mapping state threaded through the build (Phase 5d-review refactor).

    Replaces the parallel positional lists that used to be passed to
    `_build_members`: `factory`/`root`, the optional `on_element` provenance
    callback, and the phase-2 collection lists the build APPENDS to and `resolve`
    CONSUMES. One object means a new phase adds one field (not an argument in four
    call sites), and `resolve` is the SINGLE copy of the phase-2 resolution sequence
    -- it was previously duplicated verbatim in both orchestrators, the top drift
    risk. Behavior is unchanged; this is purely a threading refactor.
    """

    factory: ElementFactory
    root: kerml.Namespace
    on_element: Callable[[kerml.Element, object], None] | None = None
    typed_usages: list = field(default_factory=list)
    connection_ends: list = field(default_factory=list)
    subject_typings: list = field(default_factory=list)
    frame_references: list = field(default_factory=list)
    imports: list = field(default_factory=list)
    aliases: list = field(default_factory=list)
    subclassifications: list = field(default_factory=list)
    subsettings: list = field(default_factory=list)
    redefinitions: list = field(default_factory=list)

    def resolve(self, top_level: dict[str, kerml.Element]) -> MappingResult:
        """Run the phase-2 resolution sequence and build the MappingResult.

        Order matters and is the single source of truth for both `map_package` and
        `map_project_members`: imports FIRST (so the typed-usage/subject passes see
        imported members, Phase 5a); aliases NEXT (alias targets + alias-to-alias
        chains, Phase 5b); subclassifications BEFORE the member passes (so the
        inherited-member lookup used by typing/subsetting/redefinition sees the
        supertype links, Phase 5c/5c-2); then the member passes; and LAST the
        implicit universal base for anything still un-specialized (Phase 5d).
        """
        _resolve_imports(self.imports)
        ambiguous: dict[str, str] = {}
        # `relationship_sources` (relationship id -> declaring element id) is shared
        # across every relationship-creating resolver, so an importer can trace ANY
        # mapper-made relationship -- typing, subclassification, subsetting,
        # redefinition, framed-concern reference -- back to its source declaration's
        # line, not just the typed-usage FeatureTyping (Phase 5d-review §4).
        relationship_sources: dict[str, str] = {}
        _resolve_aliases(self.aliases, ambiguous)
        unresolved_supertypes = _resolve_subclassifications(
            self.subclassifications, ambiguous, relationship_sources
        )
        unresolved_types, mistyped = _resolve_typed_usages(
            self.root, self.typed_usages, ambiguous, relationship_sources
        )
        unresolved_ends = _resolve_connection_ends(
            self.connection_ends, ambiguous, relationship_sources
        )
        unresolved_types.update(
            _resolve_subject_types(
                self.subject_typings, ambiguous, relationship_sources
            )
        )
        unresolved_frame_refs = _resolve_frame_references(
            self.frame_references, ambiguous, relationship_sources
        )
        unresolved_subsettings = _resolve_subsettings(
            self.subsettings, ambiguous, relationship_sources
        )
        unresolved_redefinitions, self_redefinitions = _resolve_redefinitions(
            self.redefinitions, ambiguous, relationship_sources
        )
        _apply_implicit_bases(
            self.root,
            _explicitly_specialized(
                self.subclassifications, self.subsettings, self.redefinitions
            ),
        )
        # Mint a stable API-facing elementId for every element at creation time
        # (Phase 12). Persisted, distinct from Base.id, ignored by round-trip.
        assign_element_ids(self.factory)
        return MappingResult(
            root=self.root,
            elements_by_name=top_level,
            unresolved_types=unresolved_types,
            mistyped=mistyped,
            relationship_sources=relationship_sources,
            ambiguous=ambiguous,
            unresolved_ends=unresolved_ends,
            unresolved_frame_refs=unresolved_frame_refs,
            unresolved_supertypes=unresolved_supertypes,
            unresolved_subsettings=unresolved_subsettings,
            unresolved_redefinitions=unresolved_redefinitions,
            self_redefinitions=self_redefinitions,
        )


def map_package(pkg: ast.Package, factory: ElementFactory) -> MappingResult:
    """Build semantic elements for a parsed package into `factory`."""
    ctx = _MappingContext(factory, factory.create(kerml.Namespace))
    # Phase 1: build the whole ownership tree (definitions, usages, nested packages)
    # so every name exists before any type is resolved, recording phase-2 work on
    # `ctx`. Phase 2 is `ctx.resolve` (the single resolution sequence).
    top_level = _build_members(pkg.members, ctx.root, ctx)
    return ctx.resolve(top_level)


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
    ctx = _MappingContext(factory, factory.create(kerml.Namespace))
    top_level: dict[str, kerml.Element] = {}
    provenance: dict[str, tuple] = {}
    for label, pkg in named_packages:

        def record(element, node, _label=label):
            provenance[element.id] = (_label, node)

        # All packages share one root and one ctx; only the provenance callback
        # changes per package (it binds that package's label).
        ctx.on_element = record
        top_level.update(_build_members(pkg.members, ctx.root, ctx))

    result = ctx.resolve(top_level)
    for relationship_id, source_id in result.relationship_sources.items():
        if source_id in provenance:
            provenance[relationship_id] = provenance[source_id]
    return result, provenance


def _resolve_typed_usages(
    root: kerml.Namespace,
    typed_usages: list,
    ambiguous: dict[str, str],
    relationship_sources: dict[str, str],
) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    """Resolve usage typing for the collected usages (mapping phase 2).

    Name resolution is nearest-first across enclosing namespaces (see
    `_resolve_type`). A name that does not resolve in the user model is, for an
    AttributeUsage, tried against the standard library (e.g. `attribute x : Real`);
    otherwise it is recorded as unresolved. A name that resolves to the WRONG kind
    is recorded as mistyped. Only a kind match creates the FeatureTyping, so
    nothing is silently dropped and no cross-kind typing is ever stored. A created
    FeatureTyping records its usage in `relationship_sources` for provenance tracing.

    A conjugated port typing (`port p : ~Fuel`) resolves its name like a normal
    typing but must land on a PortDefinition; on a match it is typed by the
    definition's conjugate via a ConjugatedPortTyping (see `conjugation`).
    """
    unresolved_types: dict[str, str] = {}
    mistyped: dict[str, tuple[str, str]] = {}
    for usage, namespace, type_name, conjugated in typed_usages:
        target = _resolve_type(namespace, type_name)
        display_name = ("~" if conjugated else "") + "::".join(type_name)
        # A name visible from more than one import is ambiguous: report it and do
        # not bind (no library fallback, no typing) (Phase 5a).
        if target is _AMBIGUOUS:
            ambiguous[usage.id] = display_name
            continue
        # Only fall back to the standard library when the name resolves to
        # NOTHING in the user model. A user name that resolves to a non-Type
        # (e.g. a local `package Real`) shadows the library and stays
        # unresolved/wrong-kind -- the library never overrides user content.
        if target is None:
            target = _library_value_type(usage, type_name, root)
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
    return unresolved_types, mistyped


def _resolve_connection_ends(
    connection_ends: list,
    ambiguous: dict[str, str],
    relationship_sources: dict[str, str],
) -> dict[str, list[str]]:
    """Resolve binary connector endpoints to features (mapping phase 2).

    Each endpoint name is resolved nearest-first from the connection's namespace
    (imports included). A binary connection's ends are ATOMIC: source and target
    are set together only when BOTH names resolve to a `Feature` (a usage). An end
    visible from more than one import is recorded `ambiguous` (Phase 5a); an end
    that does not resolve, or resolves to a non-feature, is recorded broken
    (`broken-connection-end`). Either way NEITHER end is set -- the connection has
    no valid textual form and is reported rather than materialised half-formed. A
    feature-chain end (Phase 5e) synthesizes a chain Feature + FeatureChainings, all
    recorded in `relationship_sources` against the declaring connector so they trace
    to its source line on KPAR import (Phase 5e-review).
    """
    unresolved_ends: dict[str, list[str]] = {}
    for connection, namespace, source_name, target_name in connection_ends:
        broken: list[str] = []
        # Maps "source"/"target" -> the resolved end: a Feature for a plain endpoint,
        # or a list of chaining Features for a chain endpoint (Phase 5e). The chain
        # FEATURE is synthesized only after BOTH ends resolve, so a half-broken
        # connection leaves no orphan chain feature (the ends stay atomic).
        resolved: dict[str, kerml.Feature | list[kerml.Feature]] = {}
        for name, setter in (
            (source_name, "source"),
            (target_name, "target"),
        ):
            if isinstance(name, ast.FeatureChain):
                steps = _resolve_chain_features(namespace, name)
                if steps is _AMBIGUOUS:
                    ambiguous[connection.id] = _chain_display(name)
                elif steps is not None:
                    resolved[setter] = steps
                else:
                    broken.append(_chain_display(name))
                continue
            target = _resolve_type(namespace, name)
            if target is _AMBIGUOUS:
                ambiguous[connection.id] = "::".join(name)
            elif isinstance(target, kerml.Feature):
                resolved[setter] = target
            else:
                broken.append("::".join(name))
        if len(resolved) == 2:
            for setter, end in resolved.items():
                feature = (
                    _make_chain_feature(connection, end, relationship_sources)
                    if isinstance(end, list)
                    else end
                )
                setattr(connection, setter, feature)
        elif broken:
            unresolved_ends[connection.id] = broken
        # else: an ambiguous end (no plain-broken end) -- reported via `ambiguous`,
        # not double-reported as a broken end; ends left unset.
    return unresolved_ends


def _chain_display(chain: ast.FeatureChain) -> str:
    """The dotted text of a feature chain (`a.b.c`) for diagnostics (Phase 5e)."""
    return ".".join(("::".join(chain.head), *chain.rest))


def _resolve_chain_features(
    namespace: kerml.Namespace, chain: ast.FeatureChain
):
    """Resolve a feature chain `a.b.c` to its ordered chaining features (Phase 5e).

    The HEAD resolves nearest-first (imports included) and must be a Feature; each
    subsequent `.step` resolves as a member of the PREVIOUS feature's TYPE (own
    member, else its sole inherited member). Returns the ordered feature list, or
    `_AMBIGUOUS` if the head is visible from more than one import, or None if any
    step does not resolve to a feature (a broken chain).
    """
    head = _resolve_type(namespace, chain.head)
    if head is _AMBIGUOUS:
        return _AMBIGUOUS
    if not isinstance(head, kerml.Feature):
        return None
    features: list[kerml.Feature] = [head]
    current = head
    for step in chain.rest:
        type_ = kk.feature_type(current)
        if type_ is None:
            return None  # the previous feature is untyped: nothing to navigate into
        member = kk.owned_member_named(type_, step)
        if member is None and isinstance(type_, kerml.Type):
            inherited = kk.inherited_members_named(type_, step)
            member = inherited[0] if len(inherited) == 1 else None
        if not isinstance(member, kerml.Feature) or _is_library_proxy(member):
            return None
        features.append(member)
        current = member
    return features


def _make_chain_feature(
    connection: kerml.Feature,
    steps: list[kerml.Feature],
    relationship_sources: dict[str, str],
) -> kerml.Feature:
    """Synthesize the anonymous chain Feature for a connector end (Phase 5e): a
    Feature owning an ordered FeatureChaining per step, owned by the connection (an
    end feature). It is recognized by `kk.is_feature_chain` and skipped where user
    members are iterated.

    The synthesized chain Feature and each FeatureChaining are recorded in
    `relationship_sources` against the CONNECTION (which carries element-level
    provenance), so KPAR import can trace these synthesized artifacts to the
    connector's source line (Phase 5e-review)."""
    factory = connection.model
    chain = factory.create(kerml.Feature)
    relationship_sources[chain.id] = connection.id
    for step in steps:
        chaining = kk.add_feature_chaining(chain, step)
        relationship_sources[chaining.id] = connection.id
    kk.add_owned_member(connection, chain, factory.create(kerml.FeatureMembership))
    return chain


def _resolve_frame_references(
    frame_references: list,
    ambiguous: dict[str, str],
    relationship_sources: dict[str, str],
) -> dict[str, str]:
    """Resolve each framed-concern REFERENCE to an existing ConcernUsage (phase 2).

    `frame <ref>` owns an anonymous ConcernUsage that REFERENCES an existing
    concern. The name is resolved nearest-first from the requirement's namespace
    (imports included); a name that resolves to a ConcernUsage gets a
    ReferenceSubsetting linking the anonymous usage to it. A name visible from more
    than one import is recorded `ambiguous` (Phase 5a); a name that does not resolve,
    or resolves to a non-ConcernUsage (a ConcernDefinition or a part), is recorded
    unresolved -- never silently dropped. A created ReferenceSubsetting records its
    framing ConcernUsage in `relationship_sources` for provenance tracing
    (Phase 5d-review §4).
    """
    unresolved: dict[str, str] = {}
    for concern, namespace, target in frame_references:
        referenced = _resolve_type(namespace, target)
        if referenced is _AMBIGUOUS:
            ambiguous[concern.id] = "::".join(target)
        elif isinstance(referenced, sysml2.ConcernUsage):
            reference_subsetting = kk.add_reference_subsetting(concern, referenced)
            relationship_sources[reference_subsetting.id] = concern.id
        else:
            unresolved[concern.id] = "::".join(target)
    return unresolved


def _resolve_imports(imports: list) -> None:
    """Resolve each import's target (mapping phase 2), OWNED members only.

    A named `import A::B` resolves to any element; a wildcard `import A::*` must
    resolve to a Namespace. Resolution uses `use_imports=False` so an import never
    resolves through another import (no transitive import chains in Phase 5a). A
    target that does not resolve leaves the import with no `target`, which
    `_check_unresolved_imports` reports model-derived. Imports are resolved BEFORE
    the typed-usage/subject passes so those can see imported members.
    """
    for imp, namespace, target_name, wildcard in imports:
        target = _resolve_type(namespace, target_name, use_imports=False)
        if wildcard and not isinstance(target, kerml.Namespace):
            target = None
        if isinstance(target, kerml.Element):
            imp.target = target


def _resolve_aliases(aliases: list, ambiguous: dict[str, str]) -> None:
    """Resolve each alias's target (mapping phase 2), import-aware (Phase 5b).

    An alias's target resolves with the SAME nearest-first, import-aware rule as a
    typed usage (`_resolve_type`): it may name an own member, an imported member, or
    another alias. Because an alias may target another alias, resolution is iterated
    to a fixpoint -- each pass binds any alias whose target now resolves, repeating
    while progress is made. An alias whose target is visible from more than one
    import is recorded `ambiguous` (the alias does not bind); an alias whose target
    never resolves is left without a `memberElement`, which
    `_check_unresolved_aliases` reports model-derived. A cycle (an alias chain that
    never resolves) simply makes no progress and is reported unresolved.

    Aliases are resolved AFTER imports and BEFORE typed usages so a usage typed by
    an alias name (or by an aliased target) sees the bound target.
    """
    pending = list(aliases)
    while pending:
        still: list = []
        progressed = False
        for alias, namespace, target_name in pending:
            target = _resolve_type(namespace, target_name)
            if target is _AMBIGUOUS:
                ambiguous[alias.id] = "::".join(target_name)
                progressed = True
                continue
            if isinstance(target, kerml.Element):
                kk.set_alias_target(alias, target)
                progressed = True
            else:
                still.append((alias, namespace, target_name))
        if not progressed:
            break
        pending = still


def _resolve_subclassifications(
    subclassifications: list,
    ambiguous: dict[str, str],
    relationship_sources: dict[str, str],
) -> dict[str, list[str]]:
    """Resolve each definition `:> Super` to a Classifier and create a
    Subclassification (mapping phase 2, Phase 5c).

    The supertype name resolves with the import-aware nearest-first rule
    (`_resolve_type`) in the namespace containing the definition. A supertype visible
    from more than one import is recorded `ambiguous` (no Subclassification); a name
    that does not resolve to a Classifier (a definition) is APPENDED to the
    definition's unresolved-supertype list -- so EVERY bad supertype of a `:> A, B`
    is reported, none dropped. Resolved BEFORE the member passes so inherited-member
    lookup sees the supertype links. A created Subclassification records its
    declaring definition in `relationship_sources` so importers can trace it to that
    definition's source line (Phase 5d-review §4).
    """
    unresolved: dict[str, list[str]] = {}
    for subtype, namespace, super_name in subclassifications:
        target = _resolve_type(namespace, super_name)
        if target is _AMBIGUOUS:
            ambiguous[subtype.id] = "::".join(super_name)
            continue
        if isinstance(target, kerml.Classifier):
            sc = kk.add_subclassification(subtype, target)
            relationship_sources[sc.id] = subtype.id
        else:
            unresolved.setdefault(subtype.id, []).append("::".join(super_name))
    return unresolved


def _resolve_subsettings(
    subsettings: list,
    ambiguous: dict[str, str],
    relationship_sources: dict[str, str],
) -> dict[str, str]:
    """Resolve each usage `:> y` subsetted feature to a Feature and create a plain
    Subsetting (mapping phase 2, Phase 5c).

    The subsetted feature resolves with the import- AND inheritance-aware
    `_resolve_type` from the usage's namespace, so it may be an own, INHERITED, or
    enclosing feature. Visible from more than one import -> `ambiguous` (no
    Subsetting); not a Feature / not found -> recorded for the
    `unresolved-subsetting` rule (never silently dropped). A created Subsetting
    records its declaring usage in `relationship_sources` for provenance tracing
    (Phase 5d-review §4).
    """
    unresolved: dict[str, str] = {}
    for feature, namespace, subset_name in subsettings:
        target = _resolve_type(namespace, subset_name)
        if target is _AMBIGUOUS:
            ambiguous[feature.id] = "::".join(subset_name)
            continue
        if isinstance(target, kerml.Feature):
            subsetting = kk.add_subsetting(feature, target)
            relationship_sources[subsetting.id] = feature.id
        else:
            unresolved[feature.id] = "::".join(subset_name)
    return unresolved


def _resolve_redefinitions(
    redefinitions: list,
    ambiguous: dict[str, str],
    relationship_sources: dict[str, str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Resolve each usage `:>> y` redefined feature to a Feature and create a
    Redefinition (mapping phase 2, Phase 5c-2). Returns
    `(unresolved, self_redefinitions)`.

    The redefined feature resolves with the import- AND inheritance-aware
    `_resolve_type` from the usage's namespace, EXCLUDING the redefining feature
    itself at EVERY name segment -- so a bare `:>> x` on a feature also named `x`
    resolves to the INHERITED `x` (the thing being redefined), never to itself, and
    an inherited-name conflict can be resolved by redefining one supertype's feature
    (`:>> A::x`). Visible from more than one import/supertype -> `ambiguous` (no
    Redefinition).

    A name that, with the redefining feature EXCLUDED, does not resolve to a Feature
    but WOULD resolve to the redefining feature itself (e.g. `:>> C::x` naming this
    very feature, or a bare `:>> x` with no inherited `x`) is a SELF-redefinition --
    recorded distinctly (a feature cannot redefine itself); anything else that does
    not resolve to a Feature is `unresolved-redefinition`. Neither binds. A created
    Redefinition records its declaring usage in `relationship_sources` for provenance
    tracing (Phase 5d-review §4).
    """
    unresolved: dict[str, str] = {}
    self_redefinitions: dict[str, str] = {}
    for feature, namespace, redefined_name in redefinitions:
        target = _resolve_type(namespace, redefined_name, exclude=feature)
        if target is _AMBIGUOUS:
            ambiguous[feature.id] = "::".join(redefined_name)
            continue
        if isinstance(target, kerml.Feature):
            redefinition = kk.add_redefinition(feature, target)
            relationship_sources[redefinition.id] = feature.id
        elif _resolve_type(namespace, redefined_name) is feature:
            self_redefinitions[feature.id] = "::".join(redefined_name)
        else:
            unresolved[feature.id] = "::".join(redefined_name)
    return unresolved, self_redefinitions


def _build_requirement_body(requirement, member, namespace, ctx: _MappingContext):
    """Build a requirement's subject/assume/require/actor/stakeholder parts and
    its reqId (Phase 6b/6c).

    The subject becomes a parameter `kerml.Feature` via a SubjectMembership (its
    type resolved in phase 2 via `ctx.subject_typings`, where ANY Type matches -- a
    subject parameter is not kind-specific). The actor/stakeholder become
    `sysml2.PartUsage` parameters (the pinned XMI types ActorMembership::
    ownedActorParameter and StakeholderMembership::ownedStakeholderParameter as
    PartUsage), so their types resolve through the SAME kind-checked path as every
    other PartUsage (`ctx.typed_usages` -> PartDefinition); a wrong-kind type is
    reported, not silently accepted. Each assumed/required constraint becomes a
    ConstraintUsage carrying an opaque 6a body, owned via a
    RequirementConstraintMembership with the matching kind. The reqId is stored as
    the requirement's declaredShortName.
    """
    factory = ctx.factory
    typed_usages = ctx.typed_usages
    subject_typings = ctx.subject_typings
    frame_references = ctx.frame_references
    on_element = ctx.on_element

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


def _resolve_subject_types(
    subject_typings: list,
    ambiguous: dict[str, str],
    relationship_sources: dict[str, str],
) -> dict[str, str]:
    """Resolve each requirement SUBJECT's declared type (mapping phase 2).

    A subject may be typed by ANY Type (it is a parameter, not a kind-specific
    usage), so there is no kind check; a name that resolves to a Type sets the
    FeatureTyping, otherwise it is recorded unresolved. A name visible from more
    than one import is recorded ambiguous (Phase 5a). (Actor/stakeholder are
    PartUsage and resolve through the kind-checked `_resolve_typed_usages` path.) A
    created FeatureTyping records its subject in `relationship_sources` for provenance
    tracing (Phase 5d-review §4).
    """
    unresolved: dict[str, str] = {}
    for feature, namespace, type_name in subject_typings:
        target = _resolve_type(namespace, type_name)
        if target is _AMBIGUOUS:
            ambiguous[feature.id] = "::".join(type_name)
        elif isinstance(target, kerml.Type):
            typing = kk.set_feature_type(feature, target)
            if typing is not None:
                relationship_sources[typing.id] = feature.id
        else:
            unresolved[feature.id] = "::".join(type_name)
    return unresolved


def _build_members(
    members: tuple,
    namespace: kerml.Namespace,
    ctx: _MappingContext,
    owner_is_type: bool = False,
) -> dict[str, kerml.Element]:
    """Create each AST member as an owned member of `namespace`, recursing into
    sub-packages and definition bodies. Returns this level's elements by name.

    Phase-2 work is recorded on `ctx`: typed usages (including requirement
    actor/stakeholder PartUsages) in `ctx.typed_usages`, connection endpoints in
    `ctx.connection_ends`, requirement SUBJECT types in `ctx.subject_typings`,
    framed-concern references in `ctx.frame_references`, import targets in
    `ctx.imports`, definition supertypes in `ctx.subclassifications`, usage subsetted
    features in `ctx.subsettings`, and redefined features in `ctx.redefinitions`
    (Phase 5a-5c-2). If `ctx.on_element` is given, it is called as
    `on_element(element, ast_node)` for every created element (including nested
    ones), so callers can record per-element provenance from the AST node."""
    # Unpack ctx into the local names the body uses, so the per-member build logic
    # is unchanged (the lists are the SAME mutable objects -- appends are visible on
    # ctx). Only the threading is refactored (Phase 5d-review).
    factory = ctx.factory
    typed_usages = ctx.typed_usages
    connection_ends = ctx.connection_ends
    imports = ctx.imports
    aliases = ctx.aliases
    subclassifications = ctx.subclassifications
    subsettings = ctx.subsettings
    redefinitions = ctx.redefinitions
    on_element = ctx.on_element
    # subject_typings / frame_references are consumed only by _build_requirement_body
    # (it reads them from ctx), so they are not unpacked here.
    by_name: dict[str, kerml.Element] = {}
    for member in members:
        if isinstance(member, ast.Import):
            # An import is a Relationship owned directly by the namespace (not via a
            # Membership and not named); its target qualified name resolves in
            # phase 2 (Phase 5a).
            imp = factory.create(kerml.Import)
            imp.isImportAll = member.wildcard
            imp.visibility = (
                kerml.VisibilityKind(member.visibility)
                if member.visibility is not None
                else kerml.VisibilityKind.private  # KerML import default
            )
            namespace.ownedRelationship = imp
            imp.owningRelatedElement = namespace
            imports.append((imp, namespace, member.target, member.wildcard))
            if on_element is not None:
                on_element(imp, member)
            continue
        if isinstance(member, ast.Alias):
            # An alias is a NON-owning Membership owned by the namespace: it names a
            # foreign element (memberName) without owning it. Its target qualified
            # name resolves in phase 2 (Phase 5b). Default visibility public (the
            # member default), overridden by the shared prefix.
            alias = factory.create(kerml.Membership)
            kk.add_alias(
                namespace,
                member.name,
                alias,
                kerml.VisibilityKind(member.visibility or "public"),
            )
            aliases.append((alias, namespace, member.target))
            if on_element is not None:
                on_element(alias, member)
            continue
        if isinstance(member, ast.PartDefinition):
            element: kerml.Element = factory.create(sysml2.PartDefinition)
            # Each `:> Super` becomes a Subclassification resolved in phase 2; the
            # supertype name resolves in the namespace CONTAINING the definition
            # (nearest-first), so `namespace` is the resolution scope (Phase 5c).
            for super_name in member.specializes:
                subclassifications.append((element, namespace, super_name))
        elif isinstance(member, ast.AttributeDefinition):
            element = factory.create(sysml2.AttributeDefinition)
        elif isinstance(member, ast.PartUsage):
            element = factory.create(sysml2.PartUsage)
            if member.type_name is not None:
                typed_usages.append((element, namespace, member.type_name, False))
            # `:> y` subsets an existing feature (own, inherited, or outer),
            # resolved in phase 2 from this usage's namespace (Phase 5c).
            if member.subsets is not None:
                subsettings.append((element, namespace, member.subsets))
            # `:>> y` redefines an inherited feature (Phase 5c-2); resolved in phase
            # 2 EXCLUDING this usage itself, so bare `:>> x` finds the inherited x.
            if member.redefines is not None:
                redefinitions.append((element, namespace, member.redefines))
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
            _build_requirement_body(element, member, namespace, ctx)
        elif isinstance(member, ast.RequirementUsage):
            element = factory.create(sysml2.RequirementUsage)
            if member.type_name is not None:
                typed_usages.append((element, namespace, member.type_name, False))
            _build_requirement_body(element, member, namespace, ctx)
        elif isinstance(member, ast.ConcernDefinition):
            element = factory.create(sysml2.ConcernDefinition)
            _build_requirement_body(element, member, namespace, ctx)
        elif isinstance(member, ast.ConcernUsage):
            element = factory.create(sysml2.ConcernUsage)
            if member.type_name is not None:
                typed_usages.append((element, namespace, member.type_name, False))
            _build_requirement_body(element, member, namespace, ctx)
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
        # Member visibility (Phase 5a): set explicitly from the declared prefix,
        # defaulting to PUBLIC (the SysML member default) -- the generated
        # `Membership.visibility` default is private, so this must be set or every
        # member would be private (un-importable).
        membership.visibility = kerml.VisibilityKind(
            getattr(member, "visibility", None) or "public"
        )
        kk.add_owned_member(namespace, element, membership)
        if on_element is not None:
            on_element(element, member)
        if isinstance(member, ast.PackageDefinition):
            _build_members(member.members, element, ctx)
        elif isinstance(
            member, (ast.ActionDefinition, ast.ActionUsage, ast.PartDefinition)
        ):
            # An action/definition IS a Type, so its body members are owned per-kind:
            # usages (Features -- parts, steps, directed parameters, successions,
            # flows) via FeatureMembership, nested definitions/packages via
            # OwningMembership (Phase 7/5c). `owner_is_type=True` selects that split.
            # A `part def`/action with no body has empty members, so this is a no-op.
            _build_members(member.members, element, ctx, owner_is_type=True)
        if member.name is not None:
            by_name[member.name] = element
    return by_name


# Sentinel returned by `_resolve_type` when the first name segment is visible from
# MORE THAN ONE import at the nearest scope that has it (Phase 5a). Distinct from
# None (not found): callers record an `ambiguous-name` diagnostic and do not bind.
_AMBIGUOUS = object()


def _resolve_type(
    namespace: kerml.Namespace,
    type_name: tuple[str, ...],
    use_imports: bool = True,
    exclude: kerml.Element | None = None,
):
    """Resolve a (qualified) type name with nearest-first scoping, including
    imported memberships (Phase 5a).

    At each scope from the usage's own namespace outward to the root: an OWNED
    member wins first (own scope, any visibility); otherwise, if `use_imports`, the
    scope's IMPORTS are consulted -- a wildcard `import A::*` brings A's PUBLIC
    members, a named `import A::B` brings B by its name. The nearest scope that has
    the name wins (inner shadows outer; owned shadows imported). If the name is
    visible from more than one import at that scope and they resolve to DIFFERENT
    elements, returns `_AMBIGUOUS`. The remaining `::` segments are navigated as
    members from the match. `use_imports=False` resolves an import's OWN target
    (owned members only), so imports do not resolve through other imports.

    An ALIAS is resolved transparently: `owned_member_named` matches an alias by
    its alias name and returns the (foreign) element it references (Phase 5b), so a
    name bound by an alias resolves wherever the alias is in scope.

    At a TYPE scope, INHERITED members (reachable through supertypes via
    Subclassification) are in scope too: per KerML, the local search order is owned,
    then inherited, then imported -- so own shadows inherited shadows imported, and
    that whole local scope shadows an enclosing namespace (Phase 5c).

    `exclude` (Phase 5c-2) skips that member element in the OWNED-member lookup, so a
    redefinition `:>> x` on a feature also named `x` resolves to the INHERITED `x`
    rather than to itself.

    Deferred to later phases: implicit specialization (5d), feature chains (5e), and
    transitive re-export through public imports.
    """
    first, *rest = type_name
    scope: kerml.Namespace | None = namespace
    while scope is not None:
        found = kk.owned_member_named(scope, first, exclude=exclude)
        # Skip library value-type proxies: they are typing targets reached only
        # through `_library_value_type`, not user-authored symbols. Binding to one
        # here would make resolution declaration-order-dependent (a proxy created
        # for an earlier usage would change how a later name resolves).
        if found is not None and not _is_library_proxy(found):
            return _descend(found, rest, exclude)
        # Inherited members at a Type scope (own already shadowed them above). More
        # than one DISTINCT inherited member named `first` is an inherited-name
        # conflict -> ambiguous (never bind to an arbitrary first supertype); a
        # qualified name (`Super::first`) sidesteps it by resolving `Super` here.
        if isinstance(scope, kerml.Type):
            inherited = [
                m
                for m in kk.inherited_members_named(scope, first)
                if not _is_library_proxy(m)
            ]
            if len(inherited) > 1:
                return _AMBIGUOUS
            if len(inherited) == 1:
                return _descend(inherited[0], rest, exclude)
        if use_imports:
            candidates = _imported_candidates(scope, first)
            if len(candidates) > 1:
                return _AMBIGUOUS
            if len(candidates) == 1:
                return _descend(candidates[0], rest, exclude)
        scope = kk.owning_namespace(scope)
    return None


def _imported_candidates(
    namespace: kerml.Namespace, name: str
) -> list[kerml.Element]:
    """Distinct elements named `name` visible through `namespace`'s own imports.

    A wildcard import (`import A::*`, isImportAll) brings the PUBLIC members of the
    imported namespace; a named import (`import A::B`) brings the imported element
    by its own name. Honors imported-member visibility (a private member is not
    brought in by a wildcard). Deduplicated by id, so the same element imported two
    ways is one candidate; two DIFFERENT elements means an ambiguity.
    """
    found: dict[str, kerml.Element] = {}
    for relationship in namespace.ownedRelationship:
        if not isinstance(relationship, kerml.Import):
            continue
        target = kk._single(relationship.target)
        if target is None:
            continue
        if kk.is_import_all(relationship):
            if isinstance(target, kerml.Namespace):
                member = _public_member_named(target, name)
                if member is not None:
                    found[member.id] = member
        elif kk.effective_name(target) == name and not _is_library_proxy(target):
            found[target.id] = target
    return list(found.values())


def _public_member_named(
    namespace: kerml.Namespace, name: str
) -> kerml.Element | None:
    """A PUBLIC member of `namespace` named `name`, else None.

    Used for wildcard-import resolution: only public members are importable, so a
    `private` member is invisible to `import <ns>::*`. An owned member matches by
    its element's effective name; a public ALIAS matches by its alias name and
    brings in the (foreign) element it references, so `import <ns>::*` re-exports
    that namespace's aliases too (Phase 5b).
    """
    for membership in kk.owned_memberships(namespace):
        if membership.visibility != kerml.VisibilityKind.public:
            continue
        member = kk._single(membership.memberElement)
        if member is None or _is_library_proxy(member):
            continue
        member_name = membership.memberName or kk.effective_name(member)
        if member_name == name:
            return member
    return None


def _descend(
    element: kerml.Element,
    segments: list[str],
    exclude: kerml.Element | None = None,
) -> kerml.Element | None:
    """Navigate qualified `segments` as members from a resolved first match.

    `exclude` is honored at EVERY segment (Phase 5c-2 finding fix), so a qualified
    redefinition target like `:>> C::x` cannot descend back to the redefining feature
    itself -- the exclusion is not silently dropped after the first name segment.
    """
    current: kerml.Element | None = element
    for segment in segments:
        if not isinstance(current, kerml.Namespace):
            return None
        current = kk.owned_member_named(current, segment, exclude=exclude)
        if current is None or _is_library_proxy(current):
            return None
    return current


def _is_library_proxy(element: kerml.Element) -> bool:
    """A read-only library proxy, excluded from name resolution and user lookup.

    Either a standard-library value-type proxy (a bare ``kerml.DataType``,
    materialized by `_value_type_proxy`) or an implicit-specialization base proxy
    (`Base::Anything` / `Base::things`, Phase 5d) -- see `kk.is_library_proxy`. User
    constructs are SysML2 subclasses or KerML Packages, so neither proxy is ever a
    user symbol; excluding them keeps name resolution independent of whether/when a
    proxy was created.
    """
    return kk.is_library_proxy(element)


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


def _implicit_base_proxy(root: kerml.Namespace, cls, name: str) -> kerml.Element:
    """Find or create the read-only implicit-specialization base proxy named `name`
    (a bare `cls`) owned by `root` -- one `Anything` Classifier and one `things`
    Feature per model root (Phase 5d). Like `_value_type_proxy`: a real element that
    persists, recognized by `kk.is_implicit_base`, and invisible to export and the
    round-trip canonical form."""
    factory = root.model
    for existing in factory.select(cls):
        if (
            type(existing) is cls
            and existing.declaredName == name
            and kk.owning_namespace(existing) is root
        ):
            return existing
    proxy = factory.create(cls)
    proxy.declaredName = name
    kk.add_owned_member(root, proxy, factory.create(kerml.OwningMembership))
    return proxy


def _explicitly_specialized(
    subclassifications: list, subsettings: list, redefinitions: list
) -> set[str]:
    """Ids of elements that DECLARED an explicit `:>`/`:>>` clause (Phase 5d), from
    the phase-2 lists -- whether or not it resolved. The implicit base is suppressed
    for these, so a declared-but-broken specialization is not masked by a root."""
    return (
        {element.id for element, _, _ in subclassifications}
        | {element.id for element, _, _ in subsettings}
        | {element.id for element, _, _ in redefinitions}
    )


def _root_members(root: kerml.Namespace) -> list[kerml.Element]:
    """Elements owned below `root`, excluding the root itself.

    A mapping run may add a new root to a factory that already contains unrelated
    model roots. The implicit-base pass must stay within the current root so a later
    import cannot mutate foreign elements.
    """
    out: list[kerml.Element] = []
    stack = list(kk.members(root))
    while stack:
        element = stack.pop(0)
        out.append(element)
        if isinstance(element, kerml.Namespace):
            stack.extend(kk.members(element))
    return out


def _apply_implicit_bases(
    root: kerml.Namespace, explicit_specialized: set[str]
) -> None:
    """Add the KerML universal implicit specialization (Phase 5d).

    Every Classifier (definition) with NO explicit subclassification implicitly
    subclassifies the root `Anything`; every Feature (usage) with NO explicit
    feature-specialization (Subsetting / ReferenceSubsetting / Redefinition)
    implicitly subsets the root `things`. `explicit_specialized` holds the ids of
    elements that DECLARED a `:>`/`:>>` clause (even one that did not resolve), so a
    declared-but-broken specialization still SUPPRESSES the implicit base -- the user
    expressed intent, and an implicit root would mask the error. Only elements owned
    under `root` are considered; unrelated roots already present in the same factory
    are not mutated. Library proxies and the bases themselves are skipped. The bases
    are read-only proxies, so the implicit specializations never export or change the
    round-trip fingerprint.
    """
    anything: kerml.Element | None = None
    things: kerml.Element | None = None
    root_members = _root_members(root)
    for classifier in root_members:
        if not isinstance(classifier, kerml.Classifier):
            continue
        if _is_library_proxy(classifier) or classifier.id in explicit_specialized:
            continue
        if any(
            isinstance(r, kerml.Subclassification)
            for r in classifier.ownedRelationship
        ):
            continue
        anything = anything or _implicit_base_proxy(root, kerml.Classifier, "Anything")
        kk.add_subclassification(classifier, anything)
    for feature in root_members:
        if not isinstance(feature, kerml.Feature):
            continue
        if (
            _is_library_proxy(feature)
            or kk.is_feature_chain(feature)  # synthesized connector-end chain (5e)
            or feature.id in explicit_specialized
        ):
            continue
        if any(isinstance(r, kerml.Subsetting) for r in feature.ownedRelationship):
            continue  # has an explicit subsetting / reference-subsetting / redefinition
        things = things or _implicit_base_proxy(root, kerml.Feature, "things")
        kk.add_subsetting(feature, things)


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
