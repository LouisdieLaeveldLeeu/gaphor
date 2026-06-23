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
    visibility: str | None = None  # "public" / "private", or None (unmarked)
    line: int | None = _line


@dataclass(frozen=True)
class PartUsage:
    """`[<dir>] part <name> [ : <type> ] ;`"""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None
    direction: str | None = None  # "in" / "out" / "inout", or None (undirected)
    visibility: str | None = None  # "public" / "private", or None (unmarked)
    line: int | None = _line


@dataclass(frozen=True)
class AttributeDefinition:
    """`attribute def <name> ;`"""

    name: str
    visibility: str | None = None  # "public" / "private", or None (unmarked)
    line: int | None = _line


@dataclass(frozen=True)
class AttributeUsage:
    """`[<dir>] attribute <name> [ : <type> ] ;`"""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None
    direction: str | None = None  # "in" / "out" / "inout", or None (undirected)
    visibility: str | None = None  # "public" / "private", or None (unmarked)
    line: int | None = _line


@dataclass(frozen=True)
class ActionDefinition:
    """`action def <name> ( ; | { <body> } )`

    `members` are the action body's nested members -- steps, directed in/out
    parameters, successions, flows, and other usages (Phase 7)."""

    name: str
    members: tuple["Member", ...] = ()
    visibility: str | None = None  # "public" / "private", or None (unmarked)
    line: int | None = _line


@dataclass(frozen=True)
class ActionUsage:
    """`[<dir>] action <name> [ : <type> ] ( ; | { <body> } )`"""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None
    direction: str | None = None  # "in" / "out" / "inout", or None (undirected)
    members: tuple["Member", ...] = ()
    visibility: str | None = None  # "public" / "private", or None (unmarked)
    line: int | None = _line


@dataclass(frozen=True)
class SuccessionUsage:
    """`succession [<name>] first <end> then <end> ;` (Phase 7).

    A binary control-flow connector usage: `source`/`target` are the two step
    references (qualified-name segments)."""

    source: tuple[str, ...]  # the `first` end
    target: tuple[str, ...]  # the `then` end
    name: str | None = None
    visibility: str | None = None  # "public" / "private", or None (unmarked)
    line: int | None = _line


@dataclass(frozen=True)
class FlowUsage:
    """`flow [<name>] from <end> to <end> ;` (Phase 7).

    A binary item-flow connector usage: `source`/`target` are the two feature
    references (qualified-name segments)."""

    source: tuple[str, ...]  # the `from` end
    target: tuple[str, ...]  # the `to` end
    name: str | None = None
    visibility: str | None = None  # "public" / "private", or None (unmarked)
    line: int | None = _line


@dataclass(frozen=True)
class ConstraintDefinition:
    """`constraint def <name> ( ; | { <body> } )`

    `body` is the opaque expression text between the braces (or None), preserved
    verbatim -- NOT parsed into an expression tree (Phase 6a)."""

    name: str
    body: str | None = None
    visibility: str | None = None  # "public" / "private", or None (unmarked)
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
    visibility: str | None = None  # "public" / "private", or None (unmarked)
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
class FrameClause:
    """`frame concern <name> [ : <type> ]` inside a requirement body (Phase 6d-1).

    The DECLARE form: it owns a NEW ConcernUsage `name` (typed by the concern
    definition `type_name`, if any) via a FramedConcernMembership."""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None


@dataclass(frozen=True)
class FrameReference:
    """`frame <existing>` inside a requirement body (Phase 6d-2).

    The REFERENCE form: it owns an anonymous ConcernUsage that REFERENCES the
    existing concern `target` (a qualified name) via a ReferenceSubsetting."""

    target: tuple[str, ...]  # qualified name segments of the referenced concern


@dataclass(frozen=True)
class RequirementDefinition:
    """`requirement def [<reqId>] <name> ( ; | { <clauses> } )`

    `reqId` is the requirement short name (Phase 6c); `subject`/`assume`/`require`
    (Phase 6b), `actors`/`stakeholders` (Phase 6c), and `framedConcerns` (Phase 6d)
    come from the body; `assume`/`require` are opaque constraint body texts
    (reusing 6a)."""

    name: str
    reqId: str | None = None  # the requirement short name, or None
    subject: SubjectClause | None = None
    assume: tuple[str, ...] = ()  # assumed-constraint body texts
    require: tuple[str, ...] = ()  # required-constraint body texts
    actors: tuple[ActorClause, ...] = ()
    stakeholders: tuple[StakeholderClause, ...] = ()
    framedConcerns: tuple[FrameClause | FrameReference, ...] = ()
    visibility: str | None = None  # "public" / "private", or None (unmarked)
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
    framedConcerns: tuple[FrameClause | FrameReference, ...] = ()
    visibility: str | None = None  # "public" / "private", or None (unmarked)
    line: int | None = _line


@dataclass(frozen=True)
class ConcernDefinition:
    """`concern def [<reqId>] <name> ( ; | { <clauses> } )` (Phase 6d).

    A ConcernDefinition IS a RequirementDefinition, so it carries the same body
    parts (reqId/subject/assume/require/actors/stakeholders/framedConcerns)."""

    name: str
    reqId: str | None = None
    subject: SubjectClause | None = None
    assume: tuple[str, ...] = ()
    require: tuple[str, ...] = ()
    actors: tuple[ActorClause, ...] = ()
    stakeholders: tuple[StakeholderClause, ...] = ()
    framedConcerns: tuple[FrameClause | FrameReference, ...] = ()
    visibility: str | None = None  # "public" / "private", or None (unmarked)
    line: int | None = _line


@dataclass(frozen=True)
class ConcernUsage:
    """`[<dir>] concern [<reqId>] <name> [ : <type> ] ( ; | { <clauses> } )` (Phase 6d).

    A ConcernUsage IS a RequirementUsage, so it carries the same body parts."""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None
    direction: str | None = None  # "in" / "out" / "inout", or None (undirected)
    reqId: str | None = None
    subject: SubjectClause | None = None
    assume: tuple[str, ...] = ()
    require: tuple[str, ...] = ()
    actors: tuple[ActorClause, ...] = ()
    stakeholders: tuple[StakeholderClause, ...] = ()
    framedConcerns: tuple[FrameClause | FrameReference, ...] = ()
    visibility: str | None = None  # "public" / "private", or None (unmarked)
    line: int | None = _line


@dataclass(frozen=True)
class PortDefinition:
    """`port def <name> ;`"""

    name: str
    visibility: str | None = None  # "public" / "private", or None (unmarked)
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
    visibility: str | None = None  # "public" / "private", or None (unmarked)
    line: int | None = _line


@dataclass(frozen=True)
class ConnectionDefinition:
    """`connection def <name> ;`"""

    name: str
    visibility: str | None = None  # "public" / "private", or None (unmarked)
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
    visibility: str | None = None  # "public" / "private", or None (unmarked)
    line: int | None = _line


@dataclass(frozen=True)
class InterfaceDefinition:
    """`interface def <name> ;`"""

    name: str
    visibility: str | None = None  # "public" / "private", or None (unmarked)
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
    visibility: str | None = None  # "public" / "private", or None (unmarked)
    line: int | None = _line


@dataclass(frozen=True)
class PackageDefinition:
    """`package <name> { <members> }` -- a named, nestable container."""

    name: str
    members: tuple["Member", ...] = field(default_factory=tuple)
    visibility: str | None = None  # "public" / "private", or None (unmarked)
    line: int | None = _line


@dataclass(frozen=True)
class Import:
    """`[<vis>] import <QName> [ ::* ] ;` (Phase 5a).

    `target` is the imported qualified name; `wildcard` is True for the `::*`
    import-all form (the namespace's public members) and False for a named import
    (the single element). `visibility` is the import's own public/private (default
    private, the KerML import default), set by the shared member visibility prefix."""

    target: tuple[str, ...]  # qualified name segments
    wildcard: bool = False
    visibility: str | None = None  # "public" / "private", or None (unmarked)
    line: int | None = _line


@dataclass(frozen=True)
class Alias:
    """`[<vis>] alias <Name> for <QName> ;` (Phase 5b).

    Gives an existing element an additional name in the namespace: `name` is the
    alias, `target` the aliased element's qualified name. Maps to a non-owning
    `Membership` (memberName=name, memberElement=target). `visibility` is the
    alias's own public/private (default public, the member default), set by the
    shared member visibility prefix."""

    name: str
    target: tuple[str, ...]  # aliased element's qualified name segments
    visibility: str | None = None  # "public" / "private", or None (unmarked)
    line: int | None = _line


# A member is any construct that can appear in a (package) body.
Member = (
    "PartDefinition | PartUsage | AttributeDefinition | AttributeUsage "
    "| ActionDefinition | ActionUsage | SuccessionUsage | FlowUsage "
    "| ConstraintDefinition | ConstraintUsage "
    "| RequirementDefinition | RequirementUsage | ConcernDefinition | ConcernUsage "
    "| PortDefinition | PortUsage "
    "| ConnectionDefinition | ConnectionUsage | InterfaceDefinition "
    "| InterfaceUsage | PackageDefinition | Import | Alias"
)


@dataclass(frozen=True)
class Package:
    """The top-level container of parsed members (the implicit root namespace)."""

    members: tuple[
        "PartDefinition | PartUsage | AttributeDefinition | AttributeUsage"
        " | ActionDefinition | ActionUsage | SuccessionUsage | FlowUsage"
        " | ConstraintDefinition | ConstraintUsage"
        " | RequirementDefinition | RequirementUsage | ConcernDefinition | ConcernUsage"
        " | PortDefinition | PortUsage"
        " | ConnectionDefinition | ConnectionUsage | InterfaceDefinition"
        " | InterfaceUsage | PackageDefinition",
        ...,
    ] = field(default_factory=tuple)
