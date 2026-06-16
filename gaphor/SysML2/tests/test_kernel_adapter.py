"""Adapter-level tests for the M1b kernel: closure shape, enums, freshness.

Enumerations are value-domain types, not classes: they must be emitted as
`UML:Enumeration` (and as `enum.StrEnum` after the coder runs) with enum-typed
properties, never folded into the class closure and never silently dropped.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gaphor.codegen.coder import main as coder_main
from gaphor.SysML2 import kerml
from gaphor.SysML2.codegen import xmi_adapter

KERML_XMI = Path("docs/sysml-v2/omg/20250201/KerML.xmi")
KERNEL_MODEL = Path("models/KerML.gaphor")
KERNEL_MODULE = Path(kerml.__file__)


def _kernel():
    return xmi_adapter.extract_kernel(KERML_XMI)


# --- enums are value-domain types, not classes -------------------------------


def test_enumeration_is_not_in_class_closure():
    kernel = _kernel()
    class_names = {c.name for c in kernel.classes}
    assert "FeatureDirectionKind" not in class_names
    assert "VisibilityKind" not in class_names


def test_enumerations_are_collected_with_literals():
    kernel = _kernel()
    enums = {e.name: e.literals for e in kernel.enums}
    assert enums["FeatureDirectionKind"] == ["in", "inout", "out"]
    assert enums["VisibilityKind"] == ["private", "protected", "public"]


def test_feature_direction_is_an_enum_attribute_not_a_reference():
    kernel = _kernel()
    feature = next(c for c in kernel.classes if c.name == "Feature")
    assert "direction" in {e.name for e in feature.enum_attributes}
    assert "direction" not in {r.name for r in feature.references}


def test_generated_module_has_enum_stranum_and_enumeration_property():
    source = KERNEL_MODULE.read_text(encoding="utf-8")
    assert "class FeatureDirectionKind(enum.StrEnum):" in source
    assert "class VisibilityKind(enum.StrEnum):" in source
    # direction is an _enumeration, not a relation_many association.
    assert '_enumeration("direction", FeatureDirectionKind' in source
    assert "direction: relation_many" not in source


def test_unknown_target_type_fails_fast(tmp_path):
    """A property whose type is neither primitive, class, nor enumeration must
    raise, not be silently dropped (fail-fast invariant)."""
    xmi = tmp_path / "weird.xmi"
    xmi.write_text(
        """<?xml version='1.0' encoding='UTF-8'?>
<xmi:XMI xmlns:xmi="http://www.omg.org/spec/XMI/20161101"
         xmlns:uml="http://www.omg.org/spec/UML/20161101">
  <uml:Package xmi:id="P" name="P">
    <packagedElement xmi:id="Weird" xmi:type="uml:DataType" name="Weird"/>
    <packagedElement xmi:id="Element" xmi:type="uml:Class" name="Element">
      <ownedAttribute xmi:id="Element-odd" name="odd">
        <type xmi:idref="Weird"/>
      </ownedAttribute>
    </packagedElement>
  </uml:Package>
</xmi:XMI>
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unsupported target type"):
        xmi_adapter.extract_kernel(xmi, seed=("Element",))


def test_kernel_model_has_no_dangling_refs():
    import xml.etree.ElementTree as ET

    ns = {"g": "https://gaphor.org/model"}
    root = ET.fromstring(KERNEL_MODEL.read_text(encoding="utf-8"))
    model = root.find("g:model", ns)
    ids = {el.get("id") for el in model}
    refs = [r.get("refid") for r in model.iter() if r.tag.endswith("ref")]
    dangling = [r for r in refs if r not in ids]
    assert dangling == []


# --- determinism + freshness -------------------------------------------------


def test_kernel_model_is_deterministic():
    assert xmi_adapter.build_kerml_kernel(KERML_XMI) == xmi_adapter.build_kerml_kernel(
        KERML_XMI
    )


def test_committed_kernel_model_is_up_to_date():
    assert xmi_adapter.build_kerml_kernel(KERML_XMI) == KERNEL_MODEL.read_text(
        encoding="utf-8"
    ), "models/KerML.gaphor is stale; run `poe sysml2-kernel-model`."


def test_committed_kernel_module_is_up_to_date(tmp_path):
    outfile = tmp_path / "kerml.py"
    coder_main(
        modelfile=str(KERNEL_MODEL),
        outfile=str(outfile),
        supermodelfiles=[("Core", "models/Core.gaphor")],
    )
    assert outfile.read_text(encoding="utf-8") == KERNEL_MODULE.read_text(
        encoding="utf-8"
    ), "gaphor/SysML2/kerml.py is stale; run `poe sysml2-kernel`."
