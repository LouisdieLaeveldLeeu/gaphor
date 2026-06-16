"""Scoped structural + typing validation for the M2 tracer.

Implements exactly the four M2 rules over a mapped model, with the
error/warning/info severities from the conformance policy (decision sec 4):

- missing owner            -> ERROR (structural integrity broken)
- duplicate member name    -> ERROR (name resolution would be ambiguous)
- unresolved import        -> ERROR (an outbound reference cannot be tracked)
- usage without valid type -> ERROR (the typing reference is broken)

Name resolution stays M2-scoped: same-namespace and simple qualified-name only,
with an unresolved-symbol diagnostic (no inheritance, visibility, aliases, or
feature chains). Richer rules are added construct by construct, each tested.
"""

from __future__ import annotations

import enum
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from gaphor.core.modeling import ElementFactory
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk


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
) -> list[Diagnostic]:
    """Run the scoped M2 validation rules over all elements in `factory`.

    `unresolved_types` maps a usage element id -> the declared type name that did
    not resolve during mapping (the mapper records these). The
    usage-without-valid-type rule reports them; a model loaded from `.gaphor`
    with no mapping context simply has none to report.
    """
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(_check_missing_owner(factory))
    diagnostics.extend(_check_duplicate_names(factory))
    diagnostics.extend(_check_unresolved_imports(factory))
    diagnostics.extend(
        _check_usage_without_valid_type(factory, unresolved_types or {})
    )
    return diagnostics


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


def _check_usage_without_valid_type(
    factory: ElementFactory, unresolved_types: dict[str, str]
) -> Iterator[Diagnostic]:
    """A PartUsage that declared a type whose name did not resolve is an error.

    The mapper records (usage id -> declared type name) for type names it could
    not resolve; this rule reports them. A usage with no declared type is fine
    (an untyped usage is legal).
    """
    for usage in factory.select(sysml2.PartUsage):
        declared_type = unresolved_types.get(usage.id)
        if declared_type is not None:
            yield Diagnostic(
                Severity.ERROR,
                "usage-without-valid-type",
                f"usage {usage.declaredName!r} declares type {declared_type!r} "
                f"which does not resolve",
                usage.id,
            )
