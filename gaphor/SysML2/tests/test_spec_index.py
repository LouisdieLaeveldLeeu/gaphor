"""Versioned spec-ingestion pipeline (completion-roadmap Phase 11).

The pipeline indexes an OMG MOF XMI's abstract syntax, diffs two versions, and turns
the diff into a FAIL-FAST review report so a future SysML/KerML release can be
assessed mechanically before any human mapping decision -- above all flagging a NEW
STORED REFERENCE, which needs an ownership policy. The diff/review logic is exercised
with small synthetic XMI version pairs; a drift guard pins the committed baseline
indexes to the live XMI; and the hash-refresh tool is checked against the real
artifacts.
"""

from __future__ import annotations

import hashlib

from gaphor.SysML2.codegen import spec_index as si
from gaphor.SysML2.codegen.spec_index import (
    MetamodelIndex,
    compute_manifest_rows,
    diff_indexes,
    has_review_findings,
    index_xmi,
    load_baseline,
    review_findings,
)

_XMI_NS = "http://www.omg.org/spec/XMI/20161101"
_STRING_HREF = "https://www.omg.org/spec/UML/20161101/PrimitiveTypes.xmi#String"


def _xmi_doc(*, derived_kids: bool = True, extra: str = "", base_extra: str = "") -> str:
    """A minimal XMI: `Base`, abstract `Derived :> Base` with a primitive attribute,
    a STORED reference, a (optionally) derived reference, and an enum-typed property;
    plus an enumeration. `extra`/`base_extra` inject changes for diff tests."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<uml:Model xmlns:uml="https://www.omg.org/spec/UML/20161101" xmlns:xmi="{_XMI_NS}">
  <packagedElement xmi:type="uml:Class" xmi:id="Base" name="Base">{base_extra}</packagedElement>
  <packagedElement xmi:type="uml:Class" xmi:id="Derived" name="Derived" isAbstract="true">
    <generalization xmi:type="uml:Generalization"><general xmi:idref="Base"/></generalization>
    <ownedAttribute xmi:id="p_label" name="label"><type href="{_STRING_HREF}"/></ownedAttribute>
    <ownedAttribute xmi:id="p_parent" name="parent"><type xmi:idref="Base"/></ownedAttribute>
    <ownedAttribute xmi:id="p_kids" name="kids"{' isDerived="true"' if derived_kids else ''}><type xmi:idref="Base"/></ownedAttribute>
    <ownedAttribute xmi:id="p_vis" name="vis"><type xmi:idref="Vis"/></ownedAttribute>
    {extra}
  </packagedElement>
  <packagedElement xmi:type="uml:Enumeration" xmi:id="Vis" name="Vis">
    <ownedLiteral name="pub"/><ownedLiteral name="priv"/>
  </packagedElement>
</uml:Model>
"""


def _index(tmp_path, xml: str, name: str = "M.xmi") -> MetamodelIndex:
    path = tmp_path / name
    path.write_text(xml, encoding="utf-8")
    return index_xmi(path)


# --- indexing ----------------------------------------------------------------


def test_index_captures_classes_properties_enums(tmp_path):
    index = _index(tmp_path, _xmi_doc())
    assert {c.name for c in index.classes} == {"Base", "Derived"}
    derived = index.class_("Derived")
    assert derived.abstract
    assert derived.generalizations == ("Base",)
    props = {p.name: p for p in derived.properties}
    assert props["label"].kind == si.ATTRIBUTE and props["label"].type == "str"
    assert props["parent"].kind == si.REFERENCE and props["parent"].stored_reference
    assert props["kids"].kind == si.REFERENCE and props["kids"].derived  # not stored
    assert props["vis"].kind == si.ENUM and props["vis"].type == "Vis"
    assert dict(index.enums) == {"Vis": ("pub", "priv")}  # document order preserved


def test_index_json_round_trips(tmp_path):
    index = _index(tmp_path, _xmi_doc())
    assert MetamodelIndex.from_json(index.to_json()) == index


# --- diff --------------------------------------------------------------------


def test_diff_of_identical_indexes_is_empty(tmp_path):
    a = _index(tmp_path, _xmi_doc(), "a.xmi")
    b = _index(tmp_path, _xmi_doc(), "b.xmi")
    assert diff_indexes(a, b).is_empty


def test_diff_reports_every_change_kind(tmp_path):
    old = _index(tmp_path, _xmi_doc(), "old.xmi")
    new = _index(
        tmp_path,
        _xmi_doc(
            derived_kids=False,  # kids: derived -> stored
            extra='<ownedAttribute xmi:id="p_new" name="link"><type xmi:idref="Base"/></ownedAttribute>',
            base_extra='<ownedLiteral name="ignored"/>',  # harmless
        ).replace(
            '<ownedAttribute xmi:id="p_label" name="label"><type href="' + _STRING_HREF + '"/></ownedAttribute>',
            "",  # remove `label`
        ),
        "new.xmi",
    )
    diff = diff_indexes(old, new)
    assert ("Derived", new.class_("Derived").property("link")) in diff.added_properties
    assert ("Derived", "label") in diff.removed_properties
    assert any(
        cls == "Derived" and o.name == "kids" and o.derived and not n.derived
        for cls, o, n in diff.changed_properties
    )


def test_diff_reports_added_and_removed_classes_and_literals(tmp_path):
    old = _index(tmp_path, _xmi_doc(), "old.xmi")
    new_xml = _xmi_doc().replace(
        '<ownedLiteral name="priv"/>', '<ownedLiteral name="protected"/>'
    ).replace(
        "</uml:Model>",
        '<packagedElement xmi:type="uml:Class" xmi:id="Extra" name="Extra"/></uml:Model>',
    )
    new = _index(tmp_path, new_xml, "new.xmi")
    diff = diff_indexes(old, new)
    assert any(c.name == "Extra" for c in diff.added_classes)
    assert ("Vis", "protected") in diff.added_enum_literals
    assert ("Vis", "priv") in diff.removed_enum_literals


# --- review report -----------------------------------------------------------


def test_new_stored_reference_is_a_review_finding(tmp_path):
    old = _index(tmp_path, _xmi_doc(), "old.xmi")
    new = _index(
        tmp_path,
        _xmi_doc(
            extra='<ownedAttribute xmi:id="p_owner" name="owner"><type xmi:idref="Base"/></ownedAttribute>'
        ),
        "new.xmi",
    )
    findings = review_findings(diff_indexes(old, new), composite_refs=frozenset())
    stored = [f for f in findings if f.kind == "new-stored-reference"]
    assert len(stored) == 1
    assert "Derived.owner" in stored[0].message
    assert stored[0].severity == si.REVIEW
    assert has_review_findings(findings)


def test_new_derived_reference_and_attribute_are_info_only(tmp_path):
    old = _index(tmp_path, _xmi_doc(), "old.xmi")
    new = _index(
        tmp_path,
        _xmi_doc(
            extra=(
                '<ownedAttribute xmi:id="p_d" name="d" isDerived="true"><type xmi:idref="Base"/></ownedAttribute>'
                '<ownedAttribute xmi:id="p_n" name="n"><type href="' + _STRING_HREF + '"/></ownedAttribute>'
            )
        ),
        "new.xmi",
    )
    findings = review_findings(diff_indexes(old, new))
    assert findings and not has_review_findings(findings)  # all INFO


def test_derived_to_stored_flip_needs_review(tmp_path):
    old = _index(tmp_path, _xmi_doc(derived_kids=True), "old.xmi")
    new = _index(tmp_path, _xmi_doc(derived_kids=False), "new.xmi")
    findings = review_findings(diff_indexes(old, new))
    assert any(f.kind == "stored-derived-change" for f in findings)
    assert has_review_findings(findings)


def test_empty_diff_has_no_findings(tmp_path):
    same = _index(tmp_path, _xmi_doc())
    findings = review_findings(diff_indexes(same, same))
    assert findings == [] and not has_review_findings(findings)


# --- committed baseline drift guard ------------------------------------------


def test_committed_baseline_matches_live_xmi():
    # If a pinned XMI changes without `poe sysml2-spec-index`, this fails -- the same
    # regen discipline the generated code uses.
    for xmi_name in si._INDEXED_XMI:
        assert index_xmi(si.OMG_DIR / xmi_name) == load_baseline(xmi_name)


# --- manifest hash refresh ---------------------------------------------------


def test_manifest_rows_match_artifact_bytes():
    rows = compute_manifest_rows()
    assert rows  # the pinned artifacts exist
    for name, sha, size in rows:
        path = si.OMG_DIR / name
        assert path.stat().st_size == size
        assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
