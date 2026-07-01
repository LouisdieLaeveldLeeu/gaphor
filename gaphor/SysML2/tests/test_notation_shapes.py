"""SysML v2 notation toolkit (completion-roadmap Phase 15).

The toolkit (`gaphor/SysML2/shapes.py`) is the single source of the faithful notation
per the pinned SysML v2 Language spec 8.2.3: keyword-by-metaclass («part def» / «part»),
the `[direction] name [: Type]` line, and labelled feature compartments. These tests
pin that mapping and the composed shape trees, and check that every keyword is
documented in the notation table.
"""

from __future__ import annotations

import types
from pathlib import Path

import pytest

from gaphor.core.modeling import ElementFactory
from gaphor.diagram.shapes import Box, Text, draw_border
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.shapes import (
    features_compartment,
    keyword_label,
    name_compartment,
    name_label,
    node_shape,
    sysml_keyword,
)

# Every projectable construct -> its SysML v2 notation keyword (Language spec 8.2.3).
_KEYWORDS = {
    sysml2.PartDefinition: "part def",
    sysml2.PartUsage: "part",
    sysml2.AttributeDefinition: "attribute def",
    sysml2.AttributeUsage: "attribute",
    sysml2.ActionDefinition: "action def",
    sysml2.ActionUsage: "action",
    sysml2.ConstraintDefinition: "constraint def",
    sysml2.ConstraintUsage: "constraint",
    sysml2.RequirementDefinition: "requirement def",
    sysml2.RequirementUsage: "requirement",
    sysml2.ConcernDefinition: "concern def",
    sysml2.ConcernUsage: "concern",
    sysml2.PortDefinition: "port def",
    sysml2.PortUsage: "port",
    sysml2.ConnectionDefinition: "connection def",
    sysml2.ConnectionUsage: "connection",
    sysml2.InterfaceDefinition: "interface def",
    sysml2.InterfaceUsage: "interface",
    sysml2.FlowUsage: "flow",
    sysml2.SuccessionAsUsage: "succession",
    kerml.Package: "package",
}


def _item(subject):
    """A minimal stand-in presentation exposing `.subject` for the shape builders."""
    return types.SimpleNamespace(subject=subject)


def _texts(shape) -> list[str]:
    """Every rendered Text string in a composed shape tree, depth-first."""
    out: list[str] = []
    stack = [shape]
    while stack:
        node = stack.pop()
        if isinstance(node, Text):
            out.append(node.text())
        else:
            try:
                stack.extend(reversed(list(node)))
            except TypeError:
                pass
    return out


# --- keyword mapping ---------------------------------------------------------


@pytest.mark.parametrize(
    "cls,keyword", list(_KEYWORDS.items()), ids=[c.__name__ for c in _KEYWORDS]
)
def test_keyword_per_metaclass(cls, keyword):
    element = ElementFactory().create(cls)
    assert sysml_keyword(element) == keyword
    assert keyword_label(element) == f"«{keyword}»"


def test_keyword_matches_subclass_via_mro():
    # A ConjugatedPortDefinition is a PortDefinition subclass -> «port def».
    element = ElementFactory().create(sysml2.ConjugatedPortDefinition)
    assert sysml_keyword(element) == "port def"


def test_no_keyword_for_plumbing():
    factory = ElementFactory()
    assert sysml_keyword(factory.create(kerml.FeatureTyping)) is None
    assert keyword_label(factory.create(kerml.OwningMembership)) == ""
    assert sysml_keyword(None) is None


# --- name line ---------------------------------------------------------------


def test_name_label_includes_direction_and_typing():
    factory = ElementFactory()
    map_package(
        parse("package P { attribute def T; in attribute x : T; attribute y; }"),
        factory,
    )
    x = next(a for a in factory.select(sysml2.AttributeUsage) if a.declaredName == "x")
    y = next(a for a in factory.select(sysml2.AttributeUsage) if a.declaredName == "y")
    definition = next(
        d for d in factory.select(sysml2.AttributeDefinition) if d.declaredName == "T"
    )
    assert name_label(x) == "in x : T"  # direction + name + typing
    assert name_label(y) == "y"  # bare usage
    assert name_label(definition) == "T"  # a definition has no direction/typing


# --- composed shapes ---------------------------------------------------------


def test_name_compartment_renders_keyword_over_name():
    part_def = ElementFactory().create(sysml2.PartDefinition)
    part_def.declaredName = "Engine"
    texts = _texts(name_compartment(_item(part_def)))
    assert texts == ["«part def»", "Engine"]


def test_features_compartment_lists_labelled_features_or_none():
    factory = ElementFactory()
    a = factory.create(sysml2.AttributeUsage)
    a.declaredName = "power"
    b = factory.create(sysml2.AttributeUsage)
    b.declaredName = "mass"

    compartment = features_compartment("attributes", [a, b])
    assert _texts(compartment) == ["attributes", "power", "mass"]
    assert features_compartment("attributes", []) is None  # empty -> not drawn


def test_node_shape_is_a_bordered_compartment_stack():
    part_def = ElementFactory().create(sysml2.PartDefinition)
    part_def.declaredName = "Engine"
    attr = ElementFactory().create(sysml2.AttributeUsage)
    attr.declaredName = "power"

    shape = node_shape(_item(part_def), features_compartment("attributes", [attr]))
    assert isinstance(shape, Box)
    assert shape._draw_border is draw_border  # the outer box draws the node border
    assert _texts(shape) == ["«part def»", "Engine", "attributes", "power"]


# --- notation table coverage -------------------------------------------------


def test_every_keyword_is_documented_in_the_notation_table():
    table = (
        Path(__file__).resolve().parents[1] / ".." / ".." / "docs" / "sysml-v2" / "DIAGRAM_NOTATION.md"
    ).read_text(encoding="utf-8")
    for keyword in set(_KEYWORDS.values()):
        assert f"«{keyword}»" in table, f"{keyword!r} missing from DIAGRAM_NOTATION.md"
