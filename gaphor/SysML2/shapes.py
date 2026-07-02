"""SysML v2 diagram-notation toolkit (completion-roadmap Phase 15).

Faithful graphical notation per the pinned SysML v2 Language spec, clause 8.2.3
"Graphical Notation" (see `docs/sysml-v2/DIAGRAM_NOTATION.md` for the per-construct
mapping and clause citations). Per 8.2.3.6-.21 a node's NAME COMPARTMENT is the
keyword in guillemets -- `«<keyword> def»` for a definition, `«<keyword>»` for a
usage -- optionally over the name/typing line, followed by a stack of LABELLED feature
compartments (`attributes`, `parts`, ...).

This module is the shared toolkit the SysML2 diagram items build their shapes from, so
keyword/compartment rendering lives in ONE place and cannot drift between items. It is
pure view (invariant 4): it reads the subject, never mutates the model.
"""

from __future__ import annotations

from collections.abc import Sequence

from gaphor.core.modeling import Base
from gaphor.diagram.presentation import Presentation
from gaphor.diagram.shapes import Box, CssNode, Text, draw_border, draw_top_separator
from gaphor.SysML2 import kerml, shortnames, sysml2
from gaphor.SysML2 import kerml_kernel as kk

# Metaclass name -> SysML v2 notation keyword (Language spec 8.2.3.7-.21). A
# definition keyword carries the trailing "def"; the usage keyword does not.
_KEYWORDS: dict[str, str] = {
    "PartDefinition": "part def",
    "PartUsage": "part",
    "AttributeDefinition": "attribute def",
    "AttributeUsage": "attribute",
    "ActionDefinition": "action def",
    "ActionUsage": "action",
    "ConstraintDefinition": "constraint def",
    "ConstraintUsage": "constraint",
    "RequirementDefinition": "requirement def",
    "RequirementUsage": "requirement",
    "ConcernDefinition": "concern def",
    "ConcernUsage": "concern",
    "PortDefinition": "port def",
    "PortUsage": "port",
    "ConnectionDefinition": "connection def",
    "ConnectionUsage": "connection",
    "InterfaceDefinition": "interface def",
    "InterfaceUsage": "interface",
    "FlowUsage": "flow",
    "SuccessionAsUsage": "succession",
    "Package": "package",
}


def sysml_keyword(element: Base | None) -> str | None:
    """The SysML v2 notation keyword for `element` (e.g. ``"part def"`` / ``"part"``).

    Matched against the metaclass MRO, so a subclass resolves to its base keyword (a
    `ConjugatedPortDefinition` -> ``"port def"``). None when the element has no
    notation keyword.
    """
    if element is None:
        return None
    for klass in type(element).__mro__:
        keyword = _KEYWORDS.get(klass.__name__)
        if keyword is not None:
            return keyword
    return None


def keyword_label(element: Base | None) -> str:
    """The guillemet keyword string (``"«part def»"``), or ``""`` when there is none."""
    keyword = sysml_keyword(element)
    return f"«{keyword}»" if keyword else ""


def name_label(subject: Base | None) -> str:
    """The node's name line: ``[direction] name [: Type]``.

    Direction (``in``/``out``/``inout``) prefixes a directed feature; a typed feature
    gets the ``: Type`` suffix from its `FeatureTyping` (spec usage declaration).
    """
    if subject is None:
        return ""
    name = getattr(subject, "declaredName", None) or ""
    # A declared short name renders in the DECLARATION line (`<M> R`), per the spec's
    # definition/usage name-with-alias -- e.g. a requirement's reqId. It is NOT a
    # compartment (8.2.3.21 defines none for it). The value is encoded with the shared
    # short-name quoting rules (`<'1.1.3'>`, `<'A\'B'>`), never interpolated raw.
    if short := getattr(subject, "declaredShortName", None):
        name = f"<{shortnames.encode(short)}> {name}".strip()
    direction = getattr(subject, "direction", None)
    label = f"{direction} {name}".strip() if direction else name
    if isinstance(subject, kerml.Feature):
        type_ = kk.feature_type(subject)
        if type_ is not None and (type_name := getattr(type_, "declaredName", None)):
            label = f"{label} : {type_name}".strip()
    return label


# --- shape builders ----------------------------------------------------------


def _keyword_node(item: Presentation) -> CssNode:
    return CssNode(
        "keyword", item.subject, Text(text=lambda: keyword_label(item.subject))
    )


def _name_node(item: Presentation) -> CssNode:
    return CssNode("name", item.subject, Text(text=lambda: name_label(item.subject)))


def name_compartment(item: Presentation) -> CssNode:
    """The name compartment: the «keyword» over the name/typing line."""
    return CssNode("compartment", None, Box(_keyword_node(item), _name_node(item)))


def features_compartment(label: str, features: Sequence[Base]) -> CssNode | None:
    """A labelled feature compartment (e.g. ``"attributes"``, ``"parts"``) listing one
    ``name_label`` line per feature. Returns None when `features` is empty, so an empty
    compartment is never drawn (spec: compartments are shown only when non-empty)."""
    if not features:
        return None
    return CssNode(
        "compartment",
        None,
        Box(
            CssNode("compartment-label", None, Text(text=lambda: label)),
            *[
                CssNode("feature", f, Text(text=(lambda f=f: name_label(f))))
                for f in features
            ],
            draw=draw_top_separator,
        ),
    )


def node_shape(item: Presentation, *compartments: CssNode | None) -> Box:
    """The standard SysML v2 node shape: the name compartment plus any (non-empty)
    feature compartments, in a bordered box -- the compartment stack of 8.2.3.6."""
    stack = [name_compartment(item), *(c for c in compartments if c is not None)]
    return Box(*stack, draw=draw_border)


# --- owned-feature compartments ----------------------------------------------

# Owned features are grouped into the spec's labelled compartments by usage kind
# (8.2.3.7 attributes, .11 parts, .12 ports, .17 actions, ...); anything unclassified
# falls into a generic "features" compartment. Most-specific kinds come first.
_FEATURE_KINDS: tuple[tuple[str, type], ...] = (
    ("attributes", sysml2.AttributeUsage),
    ("ports", sysml2.PortUsage),
    ("parts", sysml2.PartUsage),
    ("actions", sysml2.ActionUsage),
    ("constraints", sysml2.ConstraintUsage),
    ("requirements", sysml2.RequirementUsage),
    ("concerns", sysml2.ConcernUsage),
    ("connections", sysml2.ConnectionUsage),
)


def owned_features(subject: Base | None) -> list[kerml.Feature]:
    """The subject's directly-owned feature usages (a definition's/usage's members that
    are features), excluding library proxies and feature-chain helpers -- the elements
    that populate its feature compartments."""
    if not isinstance(subject, kerml.Type):
        return []
    return [
        member
        for member in kk.members(subject)
        if isinstance(member, kerml.Feature)
        and not kk.is_library_proxy(member)
        and not kk.is_feature_chain(member)
    ]


def text_compartment(label: str, lines: Sequence[str]) -> CssNode | None:
    """A labelled compartment of literal text lines (a constraint expression, a
    requirement's subject/assume/require, ...), omitted when there is no content."""
    content = [line for line in lines if line]
    if not content:
        return None
    return CssNode(
        "compartment",
        None,
        Box(
            CssNode("compartment-label", None, Text(text=lambda: label)),
            *[
                CssNode("line", None, Text(text=(lambda line=line: line)))
                for line in content
            ],
            draw=draw_top_separator,
        ),
    )


def group_feature_compartments(features: Sequence[Base]) -> list[CssNode]:
    """Group `features` into labelled compartments by kind (empty groups omitted)."""
    remaining = list(features)
    compartments: list[CssNode] = []
    for label, kind in _FEATURE_KINDS:
        group = [f for f in remaining if isinstance(f, kind)]
        if group:
            compartment = features_compartment(label, group)
            if compartment is not None:
                compartments.append(compartment)
            remaining = [f for f in remaining if f not in group]
    if remaining:
        leftover = features_compartment("features", remaining)
        if leftover is not None:
            compartments.append(leftover)
    return compartments


def feature_compartments(
    subject: Base | None, *, include_ports: bool = True
) -> list[CssNode]:
    """The subject's owned features as labelled compartments grouped by kind.

    `include_ports=False` drops PortUsages, for a diagram that shows ports as boundary
    squares instead of a `ports` compartment (Phase 15 PortDisplayMode)."""
    features = owned_features(subject)
    if not include_ports:
        features = [f for f in features if not isinstance(f, sysml2.PortUsage)]
    return group_feature_compartments(features)
