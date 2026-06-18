"""AST node types for the SysML v2 textual grammar (M2 slice).

These are deliberately small, pure-data nodes: parsing produces them, and the
mapping layer (M2 sub-step 2) consumes them to build KerML/SysML semantic
elements. They carry no semantics themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PartDefinition:
    """`part def <name> ;`"""

    name: str


@dataclass(frozen=True)
class PartUsage:
    """`part <name> [ : <type> ] ;`"""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None


@dataclass(frozen=True)
class AttributeDefinition:
    """`attribute def <name> ;`"""

    name: str


@dataclass(frozen=True)
class AttributeUsage:
    """`attribute <name> [ : <type> ] ;`"""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None


@dataclass(frozen=True)
class ActionDefinition:
    """`action def <name> ;`"""

    name: str


@dataclass(frozen=True)
class ActionUsage:
    """`action <name> [ : <type> ] ;`"""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None


@dataclass(frozen=True)
class ConstraintDefinition:
    """`constraint def <name> ;`"""

    name: str


@dataclass(frozen=True)
class ConstraintUsage:
    """`constraint <name> [ : <type> ] ;`"""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None


@dataclass(frozen=True)
class RequirementDefinition:
    """`requirement def <name> ;`"""

    name: str


@dataclass(frozen=True)
class RequirementUsage:
    """`requirement <name> [ : <type> ] ;`"""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None


@dataclass(frozen=True)
class PortDefinition:
    """`port def <name> ;`"""

    name: str


@dataclass(frozen=True)
class PortUsage:
    """`port <name> [ : <type> ] ;` (unconjugated)."""

    name: str
    type_name: tuple[str, ...] | None = None  # qualified name segments, or None


@dataclass(frozen=True)
class PackageDefinition:
    """`package <name> { <members> }` -- a named, nestable container."""

    name: str
    members: tuple["Member", ...] = field(default_factory=tuple)


# A member is any construct that can appear in a (package) body.
Member = (
    "PartDefinition | PartUsage | AttributeDefinition | AttributeUsage "
    "| ActionDefinition | ActionUsage | ConstraintDefinition | ConstraintUsage "
    "| RequirementDefinition | RequirementUsage | PortDefinition | PortUsage "
    "| PackageDefinition"
)


@dataclass(frozen=True)
class Package:
    """The top-level container of parsed members (the implicit root namespace)."""

    members: tuple[
        "PartDefinition | PartUsage | AttributeDefinition | AttributeUsage"
        " | ActionDefinition | ActionUsage | ConstraintDefinition | ConstraintUsage"
        " | RequirementDefinition | RequirementUsage | PortDefinition | PortUsage"
        " | PackageDefinition",
        ...,
    ] = field(default_factory=tuple)
