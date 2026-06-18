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


# --- derived properties are classified, not persisted ------------------------


def test_derived_properties_are_classified_as_metadata():
    """isDerived=true properties are captured as derived_* metadata (auditable),
    not as stored attributes/references."""
    kernel = _kernel()
    element = next(c for c in kernel.classes if c.name == "Element")
    derived_names = {d.name for d in element.derived_references} | {
        d.name for d in element.derived_attributes
    }
    # These are derived in the XMI and must be classified as such.
    for name in ("owner", "ownedElement", "owningNamespace", "qualifiedName", "name"):
        assert name in derived_names


def test_derived_properties_are_not_stored_structure():
    """Derived properties must not appear as stored attributes/references on the
    classes that declare them (no stale persisted state)."""
    kernel = _kernel()
    element = next(c for c in kernel.classes if c.name == "Element")
    stored = {a.name for a in element.attributes} | {r.name for r in element.references}
    for name in ("owner", "ownedElement", "owningNamespace", "qualifiedName"):
        assert name not in stored


def test_derived_properties_absent_from_generated_module_and_model():
    """The exclusion is intentional: derived names do not appear as generated
    associations/attributes in kerml.py or as references in models/KerML.gaphor."""
    module = KERNEL_MODULE.read_text(encoding="utf-8")
    model = KERNEL_MODEL.read_text(encoding="utf-8")
    for name in ("ownedElement", "owningNamespace", "qualifiedName"):
        assert f'association("{name}"' not in module
        assert f'_attribute("{name}"' not in module
        assert f"<val>{name}</val>" not in model


# --- composite is restricted to the containment whitelist --------------------


def test_only_whitelisted_references_are_composite():
    kernel = _kernel()
    composite = {
        (c.name, r.name)
        for c in kernel.classes
        for r in c.references
        if r.composite
    }
    assert composite == {
        ("Element", "ownedRelationship"),
        ("Relationship", "ownedRelatedElement"),
    }


def test_generated_module_has_exactly_two_composite_associations():
    module = KERNEL_MODULE.read_text(encoding="utf-8")
    assert module.count("composite=True") == 2


# --- fail-fast on a missing seed class ---------------------------------------


def test_missing_seed_class_fails_fast():
    with pytest.raises(ValueError, match="seed classes not found"):
        xmi_adapter.extract_kernel(KERML_XMI, seed=("Element", "NoSuchClass"))


# --- expression roots: the supermodel for the SysML constraint layer ----------


def test_kernel_includes_expression_roots_for_constraints():
    # BooleanExpression/Predicate (and their self-contained closure) are in the
    # kernel so the SysML constraint/requirement layer generalizes a real KerML
    # super instead of dropping it.
    class_names = {c.name for c in _kernel().classes}
    assert {
        "BooleanExpression",
        "Predicate",
        "Expression",
        "Function",
        "Step",
        "Behavior",
    } <= class_names


def test_expression_roots_have_faithful_generalization_chains():
    classes = {c.name: c for c in _kernel().classes}
    # BooleanExpression -> Expression -> Step -> Feature; Predicate -> Function
    # -> Behavior -> Class. Each super resolves within the kernel (nothing lost).
    assert "Expression" in classes["BooleanExpression"].supers
    assert "Step" in classes["Expression"].supers
    assert "Feature" in classes["Step"].supers
    assert "Function" in classes["Predicate"].supers
    assert "Behavior" in classes["Function"].supers
    assert "Class" in classes["Behavior"].supers


# --- relationship roots: the supermodel for the SysML connection layer --------


def test_kernel_includes_relationship_roots_for_connections():
    # AssociationStructure/Connector (and their closure Association) are in the
    # kernel so the SysML connection layer generalizes a real KerML super.
    class_names = {c.name for c in _kernel().classes}
    assert {"Association", "AssociationStructure", "Connector"} <= class_names


def test_relationship_roots_have_faithful_generalization_chains():
    classes = {c.name: c for c in _kernel().classes}
    # AssociationStructure -> {Association, Structure}; Association ->
    # {Classifier, Relationship}; Connector -> {Feature, Relationship}.
    assert "Association" in classes["AssociationStructure"].supers
    assert "Structure" in classes["AssociationStructure"].supers
    assert "Classifier" in classes["Association"].supers
    assert "Relationship" in classes["Association"].supers
    assert "Feature" in classes["Connector"].supers
    assert "Relationship" in classes["Connector"].supers


def test_connector_end_properties_are_not_persisted():
    # Connector's relatedFeature/connectorEnd/association are isDerived in the
    # XMI: classified as derived metadata, never stored structure (no stale
    # endpoint state). The connector-end semantics are a later behavior-layer
    # dependency, not faked here.
    connector = next(c for c in _kernel().classes if c.name == "Connector")
    stored = {r.name for r in connector.references}
    derived = {r.name for r in connector.derived_references}
    assert "connectorEnd" not in stored
    assert "relatedFeature" not in stored
    assert {"connectorEnd", "relatedFeature"} <= derived


def test_emitter_fails_fast_on_a_dropped_generalization():
    """A class that declares a super resolving to neither a generated class nor a
    supermodel super must raise, not silently drop the generalization."""
    from gaphor.SysML2.codegen.xmi_adapter import (
        Kernel,
        KernelClass,
        emit_gaphor_kernel_model,
    )

    kernel = Kernel(
        classes=[KernelClass(name="Derived", supers=["MissingSuper"])]
    )
    with pytest.raises(ValueError, match="resolve to neither"):
        emit_gaphor_kernel_model(kernel, package_name="X")


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
