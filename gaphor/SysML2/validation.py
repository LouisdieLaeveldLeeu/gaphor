"""Scoped structural + typing validation for the SysML2 model.

Validation grows construct by construct (each rule tested); it started as the
four M2 rules and now also enforces kind-specific typing. Rules are ERROR severity
per the conformance policy (decision sec 4), except where noted (the
empty-constraint-body rule is a WARNING -- syntactically allowed, likely a
mistake):

- missing owner            -> structural integrity broken
- duplicate member name    -> name resolution would be ambiguous
- unresolved import        -> an outbound reference cannot be tracked
- usage without valid type -> a declared type name does not resolve to a Type
- broken typing            -> a FeatureTyping is missing an end (no type / no
                              typed feature), caught model-derived
- type-kind mismatch       -> a usage is typed by the wrong definition kind
                              (e.g. `part p : AttributeDefinition`); reported
                              both from mapping context and model-derived, so a
                              wrong-kind relation is caught whether it came from
                              text or was injected via the API / a reloaded model
- broken connection end    -> a connector endpoint did not resolve to a feature
                              (mapping context)
- non-feature connection   -> a connector source/target is set to a non-feature
                              (e.g. a definition); caught model-derived, since the
                              low-level diagram connect / API can store one
- incomplete connection    -> a binary connection has exactly one end set,
                              caught model-derived (no valid textual form)
- broken conjugation       -> a conjugated port typing does not resolve to a real
                              conjugate of a port definition (model-derived)
- empty constraint body    -> a preserved constraint body is empty/whitespace
                              (WARNING; model-derived). The body is opaque text,
                              not interpreted -- expression semantics are out of
                              scope.

Rules that need mapping context (unresolved-symbol, mapping-context kind
mismatch) take it as an argument; the rest are recomputed from the stored model
alone, so a reloaded `.gaphor` is validated without it. Name resolution stays
scoped: same-namespace and simple qualified-name only (no inheritance,
visibility, aliases, or feature chains).
"""

from __future__ import annotations

import enum
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from gaphor.core.modeling import ElementFactory
from gaphor.SysML2 import constraints
from gaphor.SysML2 import kerml
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2 import sysml2
from gaphor.SysML2.mapping import is_managed_usage_kind, type_matches_usage_kind


class Severity(enum.StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Diagnostic:
    severity: Severity
    rule: str
    message: str
    element_id: str | None = None


def validate(
    factory: ElementFactory,
    unresolved_types: dict[str, str] | None = None,
    mistyped: dict[str, tuple[str, str]] | None = None,
    unresolved_ends: dict[str, list[str]] | None = None,
) -> list[Diagnostic]:
    """Run the scoped M2 validation rules over all elements in `factory`.

    `unresolved_types` maps a usage element id -> the declared type name that did
    not resolve during mapping (the mapper records these). The
    usage-without-valid-type rule reports them; a model loaded from `.gaphor`
    with no mapping context simply has none to report.

    `mistyped` maps a usage element id -> (declared type name, resolved-type kind)
    for a type that resolved but is the WRONG KIND for the usage (e.g.
    `part p : AttributeDefinition`). These also produce no FeatureTyping; the
    type-kind-mismatch rule reports them. Like unresolved types, this needs
    mapping context, so a reloaded model has none to report.

    `unresolved_ends` maps a connection element id -> the declared connector-end
    references that did not resolve to a feature (broken or kind-mismatched
    endpoints). The connection-end rule reports them; mapping context only.
    """
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(_check_missing_owner(factory))
    diagnostics.extend(_check_duplicate_names(factory))
    diagnostics.extend(_check_unresolved_imports(factory))
    diagnostics.extend(_check_broken_typing(factory))
    diagnostics.extend(
        _check_usage_without_valid_type(factory, unresolved_types or {})
    )
    diagnostics.extend(_check_type_kind_mismatch(factory, mistyped or {}))
    diagnostics.extend(_check_connection_ends(factory, unresolved_ends or {}))
    diagnostics.extend(_check_connection_end_integrity(factory))
    diagnostics.extend(_check_conjugated_typing(factory))
    diagnostics.extend(_check_constraint_body(factory))
    return diagnostics


def _check_constraint_body(factory: ElementFactory) -> Iterator[Diagnostic]:
    """A preserved constraint body must not be empty (basic well-formedness).

    Model-derived: a constraint body is preserved as opaque text in a
    `TextualRepresentation` (language `sysml`); the grammar already enforces the
    `{ }` delimiters, so the only well-formedness check left is that the body is
    not empty/whitespace-only (`constraint c { }`), which is reported as a
    WARNING (it is syntactically allowed but almost certainly a mistake). The body
    is NOT otherwise interpreted -- expression semantics are out of scope here.
    """
    for rep in factory.select(kerml.TextualRepresentation):
        if rep.language != constraints.BODY_LANGUAGE:
            continue
        if not (rep.body or "").strip():
            owner = kk.owning_namespace(rep)
            name = owner.declaredName if owner is not None else None
            yield Diagnostic(
                Severity.WARNING,
                "empty-constraint-body",
                f"constraint {name!r} has an empty body"
                if name
                else "constraint has an empty body",
                owner.id if owner is not None else rep.id,
            )


def _sole(values) -> kerml.Element | None:
    """The single element of a stored association, or None if it does not hold
    EXACTLY one. The conjugation ends are conceptually single-valued, but the
    generated associations are relation-many at runtime, so an API mutation can
    APPEND a second target. `_single` (first-only) would miss that; `_sole`
    returns None for both an empty and a multi-valued association so either is
    treated as broken."""
    items = list(values)
    return items[0] if len(items) == 1 else None


def _holds_only(values, expected) -> bool:
    """Whether a stored association holds EXACTLY the one `expected` element
    (not merely as its first value -- an appended extra target is a mismatch)."""
    return list(values) == [expected]


def _check_conjugated_typing(factory: ElementFactory) -> Iterator[Diagnostic]:
    """A conjugated port typing must be internally consistent across ALL its
    stored ends -- each holding EXACTLY its expected target, not merely navigable
    along one path nor merely correct in its first value.

    Model-derived (no mapping context): a `ConjugatedPortTyping` stores both the
    inherited FeatureTyping `type` AND the `conjugatedPortDefinition`, and the
    conjugate stores a `PortConjugation` with both the SysML `originalPortDefinition`
    and the KerML `Conjugation` ends (`originalType`/`conjugatedType`). The normal
    mapper/UI path sets each of these to a single, agreeing target, but a
    hand-edited/persisted .gaphor or an API mutation can store contradictory ends
    -- including an APPENDED extra target, since these generated associations are
    relation-many at runtime (`typing.type = power` appends rather than replaces).
    Every end is checked for exactly its expected target so such a model is
    reported, not silently accepted as a clean `~Fuel`:

    - the typing's `conjugatedPortDefinition` is exactly one ConjugatedPortDefinition;
    - the typing's `type` is exactly that conjugate;
    - the conjugate owns exactly one `PortConjugation` naming exactly one original
      `PortDefinition`;
    - that PortConjugation's `originalType` is exactly that original, and its
      `conjugatedType` is exactly the conjugate.
    """
    for typing in factory.select(sysml2.ConjugatedPortTyping):
        feature = kk._single(typing.typedFeature)
        element_id = feature.id if feature is not None else typing.id

        def broken(message: str, _id=element_id) -> Diagnostic:
            return Diagnostic(Severity.ERROR, "broken-conjugation", message, _id)

        conjugate = _sole(typing.conjugatedPortDefinition)
        if not isinstance(conjugate, sysml2.ConjugatedPortDefinition):
            yield broken(
                "conjugated port typing does not have exactly one "
                "conjugated port definition"
            )
            continue
        # The inherited typing target must be EXACTLY the conjugate, or the port
        # is really typed by something other than what `~<original>` renders.
        if not _holds_only(typing.type, conjugate):
            yield broken(
                "conjugated port typing's type is not exactly its "
                "conjugated port definition"
            )
        conjugators = [
            r
            for r in conjugate.ownedRelationship
            if isinstance(r, sysml2.PortConjugation)
        ]
        if len(conjugators) != 1:
            yield broken(
                "conjugated port definition does not have exactly one "
                "port conjugation"
            )
            continue
        pc = conjugators[0]
        original = _sole(pc.originalPortDefinition)
        if not isinstance(original, sysml2.PortDefinition):
            yield broken(
                "port conjugation does not have exactly one original "
                "port definition"
            )
            continue
        # The KerML Conjugation ends must agree (exactly) with the SysML ends.
        if not _holds_only(pc.originalType, original):
            yield broken(
                "port conjugation original type does not match its "
                "original port definition"
            )
        if not _holds_only(pc.conjugatedType, conjugate):
            yield broken(
                "port conjugation conjugated type does not match its conjugate"
            )


def _check_connection_end_integrity(factory: ElementFactory) -> Iterator[Diagnostic]:
    """A binary connection's ends must be features, and must come as a pair.

    Model-derived (needs no mapping context), so it guards ends that reached the
    model OUTSIDE the textual path -- a low-level diagram connect (Gaphor's
    `connect()` does not consult the connector's `allow`), the Python/kernel API,
    or a hand-edited/persisted .gaphor:

    - non-feature end: a source/target set to a non-`Feature` (e.g. a connection
      wired to a definition). The textual mapper rejects these; such an end has no
      valid textual form, so it must be reported here rather than exported as a
      clause the mapper would reject on re-import.
    - incomplete connection: exactly one of source/target is set. A one-ended
      binary connection likewise has no valid textual form and would otherwise be
      dropped silently on export.

    The textual mapper already keeps ends atomic and feature-typed, so a model
    built from text never trips this; it is the safety net for the other routes.
    """
    for connection in factory.select(sysml2.ConnectionUsage):
        source = kk._single(connection.source)
        target = kk._single(connection.target)
        name = connection.declaredName
        for end, role in ((source, "source"), (target, "target")):
            if end is not None and not isinstance(end, kerml.Feature):
                yield Diagnostic(
                    Severity.ERROR,
                    "non-feature-connection-end",
                    f"connection {name!r} has a {role} end that is not a feature "
                    f"(a {type(end).__name__})"
                    if name
                    else f"connection {role} end is not a feature "
                    f"(a {type(end).__name__})",
                    connection.id,
                )
        if (source is None) != (target is None):
            present, missing = (
                ("source", "target") if source is not None else ("target", "source")
            )
            yield Diagnostic(
                Severity.ERROR,
                "incomplete-connection",
                f"connection {name!r} has a {present} end but no {missing} end"
                if name
                else f"connection has a {present} end but no {missing} end",
                connection.id,
            )


def _check_connection_ends(
    factory: ElementFactory, unresolved_ends: dict[str, list[str]]
) -> Iterator[Diagnostic]:
    """A connection whose declared connector end did not resolve to a feature is
    a broken/mismatched endpoint (the mapper records these)."""
    for connection_id, ends in unresolved_ends.items():
        element = factory.lookup(connection_id)
        name = element.declaredName if element is not None else None
        for end in ends:
            yield Diagnostic(
                Severity.ERROR,
                "broken-connection-end",
                f"connection {name!r} declares endpoint {end!r} which does not "
                f"resolve to a feature"
                if name
                else f"connection endpoint {end!r} does not resolve to a feature",
                connection_id,
            )


def has_errors(diagnostics: Iterable[Diagnostic]) -> bool:
    return any(d.severity is Severity.ERROR for d in diagnostics)


def _check_missing_owner(factory: ElementFactory) -> Iterator[Diagnostic]:
    """Every non-root member element must have an owning namespace.

    A Namespace may be a root (no owner); other members reached through a
    membership must resolve an owning namespace.
    """
    for membership in factory.select(kerml.OwningMembership):
        member = kk._single(membership.memberElement)
        if member is not None and kk.owning_namespace(member) is None:
            yield Diagnostic(
                Severity.ERROR,
                "missing-owner",
                f"element {member.declaredName!r} has no owning namespace",
                member.id,
            )


def _check_duplicate_names(factory: ElementFactory) -> Iterator[Diagnostic]:
    """No two members of the same namespace may share an effective name."""
    for namespace in factory.select(kerml.Namespace):
        names = Counter(
            kk.effective_name(m)
            for m in kk.members(namespace)
            if kk.effective_name(m) is not None
        )
        for name, count in names.items():
            if count > 1:
                yield Diagnostic(
                    Severity.ERROR,
                    "duplicate-name",
                    f"name {name!r} is declared {count} times in the same namespace",
                    namespace.id,
                )


def _check_unresolved_imports(factory: ElementFactory) -> Iterator[Diagnostic]:
    """Every Import must reference an element that exists."""
    for imp in factory.select(kerml.Import):
        if kk._single(imp.target) is None:
            yield Diagnostic(
                Severity.ERROR,
                "unresolved-import",
                "import does not reference a resolvable element",
                imp.id,
            )


def _check_broken_typing(factory: ElementFactory) -> Iterator[Diagnostic]:
    """A FeatureTyping must reference both a typed feature and a type.

    This is model-derived (needs no mapping context), so it catches a typing
    that became broken in a persisted or mutated model -- e.g. after its type
    element was deleted, leaving an orphaned FeatureTyping with an empty `type`.
    """
    for typing in factory.select(kerml.FeatureTyping):
        feature = kk._single(typing.typedFeature)
        type_ = kk._single(typing.type)
        if type_ is None:
            owner = kk._single(typing.owningRelatedElement)
            name = owner.declaredName if owner is not None else None
            yield Diagnostic(
                Severity.ERROR,
                "usage-without-valid-type",
                f"feature typing on {name!r} has no resolved type"
                if name
                else "feature typing has no resolved type",
                (feature.id if feature is not None else typing.id),
            )
        elif feature is None:
            yield Diagnostic(
                Severity.ERROR,
                "broken-typing",
                "feature typing has a type but no typed feature",
                typing.id,
            )
        elif is_managed_usage_kind(feature) and not type_matches_usage_kind(
            feature, type_
        ):
            # Both ends present but kind-mismatched (e.g. a PartUsage typed by an
            # AttributeDefinition). Model-derived, so this catches a wrong-kind
            # relation that reached the model outside the textual path -- via the
            # Python/kernel API or a hand-edited/persisted .gaphor -- which the
            # mapping-context `type-kind-mismatch` rule alone would miss. Only the
            # managed SysML usage kinds are checked; a bare kernel Feature typing
            # is out of this contract's scope.
            name = feature.declaredName
            yield Diagnostic(
                Severity.ERROR,
                "type-kind-mismatch",
                f"{type(feature).__name__} {name!r} is typed by a "
                f"{type(type_).__name__}, not its required definition kind",
                feature.id,
            )


def _check_usage_without_valid_type(
    factory: ElementFactory, unresolved_types: dict[str, str]
) -> Iterator[Diagnostic]:
    """Any usage that declared a type which did not resolve to a Type is an error.

    The mapper records (usage id -> declared type name) for every usage -- Part,
    Attribute, or any future usage kind -- whose declared type name either did
    not resolve or resolved to a non-Type (e.g. a Package). Iterating the
    recorded ids (not a specific usage class) keeps this correct as constructs
    grow. A usage with no declared type is fine (an untyped usage is legal).
    """
    for usage_id, declared_type in unresolved_types.items():
        element = factory.lookup(usage_id)
        name = element.declaredName if element is not None else None
        yield Diagnostic(
            Severity.ERROR,
            "usage-without-valid-type",
            f"usage {name!r} declares type {declared_type!r} which does not "
            f"resolve to a type",
            usage_id,
        )


def _check_type_kind_mismatch(
    factory: ElementFactory, mistyped: dict[str, tuple[str, str]]
) -> Iterator[Diagnostic]:
    """A usage typed by a resolvable Type of the WRONG KIND is an error.

    Each usage kind is typed by exactly one definition kind (a part by a
    PartDefinition, a requirement by a RequirementDefinition, ...). A declared
    type that resolves to a Type of a different kind -- e.g.
    `part p : AttributeDefinition` or `requirement r : ConstraintDefinition` --
    is a kind mismatch: no FeatureTyping is created (the mapper records it here),
    and it must be reported rather than silently accepted.
    """
    for usage_id, (declared_type, resolved_kind) in mistyped.items():
        element = factory.lookup(usage_id)
        name = element.declaredName if element is not None else None
        usage_kind = type(element).__name__ if element is not None else "usage"
        yield Diagnostic(
            Severity.ERROR,
            "type-kind-mismatch",
            f"{usage_kind} {name!r} declares type {declared_type!r} which "
            f"resolves to a {resolved_kind}, not the required definition kind",
            usage_id,
        )
