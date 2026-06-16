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
class Package:
    """The top-level container of parsed members."""

    members: tuple[PartDefinition | PartUsage, ...] = field(default_factory=tuple)
