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
from gaphor.SysML2 import kerml
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
