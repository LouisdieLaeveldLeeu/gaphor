"""SysML v2 default diagram CSS (completion-roadmap Phase 15).

The system style sheet (`gaphor/diagram.css`) gained a SysML v2 section styling the
notation toolkit's CssNodes: the «keyword» line and compartment labels (x-small,
italic, centered), feature lines (left-aligned), bold names on SysML2 boxes, rounded
action boxes, and an opaque port square. The bare `keyword`/`compartment-label`/
`feature` selectors are leak-safe because ONLY `gaphor/SysML2/shapes.py` produces
those CssNode names; shared names (`name`, `icon`) are scoped by SysML2 item-type
selectors. Leak guards below pin that other languages' styling is untouched.
"""

from __future__ import annotations

from gaphor.core.modeling.stylesheet import SYSTEM_STYLE_SHEET, StyleSheet
from gaphor.core.styling import (
    CompiledStyleSheet,
    FontStyle,
    FontWeight,
    TextAlign,
)
from gaphor.core.styling.tests.test_compiler import Node


def _style(node: Node) -> dict:
    return CompiledStyleSheet(SYSTEM_STYLE_SHEET).compute_style(node)


def _item_child(item_name: str, child_name: str) -> Node:
    diagram = Node("diagram")
    item = Node(item_name, parent=diagram, classes=["item"])
    return Node(child_name, parent=item)


def _heading_font_size() -> float:
    """UML's `compartment heading` computed font size -- the shipped x-small
    convention the SysML2 keyword/compartment-label rules mirror. Comparing against
    it keeps the tests robust to theme/default-font changes."""
    diagram = Node("diagram")
    item = Node("class", parent=diagram, classes=["item"])
    compartment = Node("compartment", parent=item)
    heading = Node("heading", parent=compartment)
    return _style(heading)["font-size"]


# --- SysML2-only CssNode names (bare, leak-safe selectors) ---------------------


def test_keyword_line_is_small_italic_centered():
    style = _style(_item_child("partdefinition", "keyword"))
    assert style["font-size"] == _heading_font_size()  # the x-small convention
    assert style["font-style"] is FontStyle.ITALIC
    assert style["text-align"] is TextAlign.CENTER


def test_compartment_label_is_styled_like_a_heading():
    # A feature compartment's label sits inside a second+ compartment, which
    # inherits text-align: left -- the explicit CENTER must beat that.
    diagram = Node("diagram")
    item = Node("partdefinition", parent=diagram, classes=["item"])
    Node("compartment", parent=item)  # first compartment (the name compartment)
    second = Node("compartment", parent=item)
    label = Node("compartment-label", parent=second)

    style = CompiledStyleSheet(SYSTEM_STYLE_SHEET).compute_style(label)
    assert style["font-size"] == _heading_font_size()  # the x-small convention
    assert style["font-style"] is FontStyle.ITALIC
    assert style["text-align"] is TextAlign.CENTER
    assert style["padding"] == (0, 0, 4, 0)


def test_feature_lines_are_left_aligned():
    style = _style(_item_child("partdefinition", "feature"))
    assert style["text-align"] is TextAlign.LEFT


# --- scoped rules on shared names ----------------------------------------------


def test_sysml2_box_names_are_bold_but_port_label_is_not():
    assert _style(_item_child("partdefinition", "name"))["font-weight"] is FontWeight.BOLD
    assert _style(_item_child("actionusage", "name"))["font-weight"] is FontWeight.BOLD
    # The boundary-square label stays plain, like UML proxy ports.
    assert "font-weight" not in _style(_item_child("portusage", "name"))


def test_action_boxes_are_rounded_and_parts_are_not():
    diagram = Node("diagram")
    action = Node("actionusage", parent=diagram, classes=["item"])
    part = Node("partusage", parent=diagram, classes=["item"])
    assert _style(action)["border-radius"] == 15
    assert "border-radius" not in _style(part)


def test_port_square_icon_is_opaque_like_proxy_ports():
    port_icon = _style(_item_child("portusage", "icon"))
    proxy_icon = _style(_item_child("proxyport", "icon"))
    assert "background-color" in port_icon
    assert port_icon["background-color"] == proxy_icon["background-color"]


# --- leak guards: other languages' rendering is untouched ----------------------


def test_general_line_item_is_not_restyled():
    # `line` is the general-purpose Line item's css name; the SysML2 section must
    # not add typography to it.
    diagram = Node("diagram")
    line = Node("line", parent=diagram, classes=["item"])
    style = _style(line)
    assert "font-style" not in style
    assert "border-radius" not in style


def test_uml_class_styling_is_untouched():
    # UML `class name` stays bold (its own rule) and `class` gains no radius.
    diagram = Node("diagram")
    klass = Node("class", parent=diagram, classes=["item"])
    name = Node("name", parent=klass)
    assert _style(name)["font-weight"] is FontWeight.BOLD
    klass_style = _style(klass)
    assert "border-radius" not in klass_style
    # ...and UML's name node gets no SysML2 keyword typography.
    assert "font-style" not in _style(name)


# --- end to end with a real item ------------------------------------------------


def test_real_action_item_computes_rounded_border(element_factory):
    from gaphor.core.modeling.diagram import StyledItem
    from gaphor.SysML2 import sysml2
    from gaphor.SysML2.diagramitems import ActionUsageItem
    from gaphor.SysML2.diagramtype import SysML2Diagram

    diagram = element_factory.create(SysML2Diagram)
    item = diagram.create(ActionUsageItem)
    item.subject = element_factory.create(sysml2.ActionUsage)

    style = StyleSheet().compute_style(StyledItem(item))
    assert style["border-radius"] == 15
