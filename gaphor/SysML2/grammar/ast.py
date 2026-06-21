"""AST node types for the SysML v2 textual grammar (M2 slice).

These are deliberately small, pure-data nodes: parsing produces them, and the
mapping layer (M2 sub-step 2) consumes them to build KerML/SysML semantic
elements. They carry no semantics themselves.

Each declaration node also carries the 1-based source `line` of its declaration
(set by the parser). `line` is excluded from equality (`compare=False`) so AST
comparisons stay position-independent; it exists for provenance (e.g. KPAR
import tracing each imported element/reference back to its source line).
"""

from __future__ import annotations

from dataclasses import dataclass, field

_line = field(default=None, compare=False)

# A usage may carry a feature direction: "in", "out", "inout", or None
# (undirected). Maps to KerML `Feature::direction` (Phase 8b).


@dataclass(frozen=True)
class PartDefinition:
    """`part def <name> ;`"""

    name: str
    line: int | None = _line


@dataclass(frozen=True)
class PartUsage:
    """`[<dir>] part <name> [ : <type> ] ;`"""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None
    direction: str | None = None  # "in" / "out" / "inout", or None (undirected)
    line: int | None = _line


@dataclass(frozen=True)
class AttributeDefinition:
    """`attribute def <name> ;`"""

    name: str
    line: int | None = _line


@dataclass(frozen=True)
class AttributeUsage:
    """`[<dir>] attribute <name> [ : <type> ] ;`"""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None
    direction: str | None = None  # "in" / "out" / "inout", or None (undirected)
    line: int | None = _line


@dataclass(frozen=True)
class ActionDefinition:
    """`action def <name> ;`"""

    name: str
    line: int | None = _line


@dataclass(frozen=True)
class ActionUsage:
    """`[<dir>] action <name> [ : <type> ] ;`"""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None
    direction: str | None = None  # "in" / "out" / "inout", or None (undirected)
    line: int | None = _line


@dataclass(frozen=True)
class ConstraintDefinition:
    """`constraint def <name> ( ; | { <body> } )`

    `body` is the opaque expression text between the braces (or None), preserved
    verbatim -- NOT parsed into an expression tree (Phase 6a)."""

    name: str
    body: str | None = None
    line: int | None = _line


@dataclass(frozen=True)
class ConstraintUsage:
    """`[<dir>] constraint <name> [ : <type> ] ( ; | { <body> } )`

    `body` is the opaque expression text between the braces (or None), preserved
    verbatim -- NOT parsed into an expression tree (Phase 6a)."""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None
    direction: str | None = None  # "in" / "out" / "inout", or None (undirected)
    body: str | None = None  # opaque constraint body text, or None
    line: int | None = _line


@dataclass(frozen=True)
class SubjectClause:
    """`subject <name> [ : <type> ]` inside a requirement body (Phase 6b)."""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None


@dataclass(frozen=True)
class ActorClause:
    """`actor <name> [ : <type> ]` inside a requirement body (Phase 6c)."""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None


@dataclass(frozen=True)
class StakeholderClause:
    """`stakeholder <name> [ : <type> ]` inside a requirement body (Phase 6c)."""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None


@dataclass(frozen=True)
class RequirementDefinition:
    """`requirement def [<reqId>] <name> ( ; | { <clauses> } )`

    `reqId` is the requirement short name (Phase 6c); `subject`/`assume`/`require`
    (Phase 6b) and `actors`/`stakeholders` (Phase 6c) come from the body;
    `assume`/`require` are opaque constraint body texts (reusing 6a)."""

    name: str
    reqId: str | None = None  # the requirement short name, or None
    subject: SubjectClause | None = None
    assume: tuple[str, ...] = ()  # assumed-constraint body texts
    require: tuple[str, ...] = ()  # required-constraint body texts
    actors: tuple[ActorClause, ...] = ()
    stakeholders: tuple[StakeholderClause, ...] = ()
    line: int | None = _line


@dataclass(frozen=True)
class RequirementUsage:
    """`[<dir>] requirement [<reqId>] <name> [ : <type> ] ( ; | { <clauses> } )`"""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None
    direction: str | None = None  # "in" / "out" / "inout", or None (undirected)
    reqId: str | None = None  # the requirement short name, or None
    subject: SubjectClause | None = None
    assume: tuple[str, ...] = ()
    require: tuple[str, ...] = ()
    actors: tuple[ActorClause, ...] = ()
    stakeholders: tuple[StakeholderClause, ...] = ()
    line: int | None = _line


@dataclass(frozen=True)
class PortDefinition:
    """`port def <name> ;`"""

    name: str
    line: int | None = _line


@dataclass(frozen=True)
class PortUsage:
    """`port <name> [ : [~]<type> ] ;`

    `conjugated` is True for the `: ~<type>` form, which types the port by the
    conjugate of the referenced PortDefinition (Phase 8a)."""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None
    conjugated: bool = False
    direction: str | None = None  # "in" / "out" / "inout", or None (undirected)
    line: int | None = _line


@dataclass(frozen=True)
class ConnectionDefinition:
    """`connection def <name> ;`"""

    name: str
    line: int | None = _line


@dataclass(frozen=True)
class ConnectionUsage:
    """`connection <name> [ : <type> ] [ connect <end> to <end> ] ;`

    `source`/`target` are the two binary connector-end references (qualified-name
    segments), or both None for a declaration-only connection."""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None
    source: tuple[str, ...] | None = None  # endpoint 1, or None
    target: tuple[str, ...] | None = None  # endpoint 2, or None
    direction: str | None = None  # "in" / "out" / "inout", or None (undirected)
    line: int | None = _line


@dataclass(frozen=True)
class InterfaceDefinition:
    """`interface def <name> ;`"""

    name: str
    line: int | None = _line


@dataclass(frozen=True)
class InterfaceUsage:
    """`[<dir>] interface <name> [ : <type> ] [ connect <end> to <end> ] ;`

    An InterfaceUsage IS a ConnectionUsage; `source`/`target` are its two binary
    connector-end references (or both None). `direction` is the optional feature
    direction (Phase 8b)."""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None
    source: tuple[str, ...] | None = None  # endpoint 1, or None
    target: tuple[str, ...] | None = None  # endpoint 2, or None
    direction: str | None = None  # "in" / "out" / "inout", or None (undirected)
    line: int | None = _line


@dataclass(frozen=True)
class PackageDefinition:
    """`package <name> { <members> }` -- a named, nestable container."""

    name: str
    members: tuple["Member", ...] = field(default_factory=tuple)
    line: int | None = _line


# A member is any construct that can appear in a (package) body.
Member = (
    "PartDefinition | PartUsage | AttributeDefinition | AttributeUsage "
    "| ActionDefinition | ActionUsage | ConstraintDefinition | ConstraintUsage "
    "| RequirementDefinition | RequirementUsage | PortDefinition | PortUsage "
    "| ConnectionDefinition | ConnectionUsage | InterfaceDefinition "
    "| InterfaceUsage | PackageDefinition"
)


@dataclass(frozen=True)
class Package:
    """The top-level container of parsed members (the implicit root namespace)."""

    members: tuple[
        "PartDefinition | PartUsage | AttributeDefinition | AttributeUsage"
        " | ActionDefinition | ActionUsage | ConstraintDefinition | ConstraintUsage"
        " | RequirementDefinition | RequirementUsage | PortDefinition | PortUsage"
        " | ConnectionDefinition | ConnectionUsage | InterfaceDefinition"
        " | InterfaceUsage | PackageDefinition",
        ...,
    ] = field(default_factory=tuple)
