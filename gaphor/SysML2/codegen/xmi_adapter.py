"""Adapter: OMG normative MOF XMI slice -> Gaphor `.gaphor` model.

This is the de-risking core of the M1a generator feasibility spike. The M0
finding established that Gaphor generates Python `Base` subclasses from
`.gaphor` model files via `gaphor.codegen.coder`, not from external XMI. So the
realistic generator path is two-step:

    normative MOF XMI  --(this adapter)-->  .gaphor model  --(coder)-->  Python

This module performs the first step for a *small slice* of the metamodel. It
introduces no SysML v2 semantics: it only translates the abstract-syntax shape
(classes, primitive-typed attributes, class-typed references/associations) into
the `.gaphor` model elements the coder reads (`UML:Package`, `UML:Class`,
`UML:Property` with `typeValue` for attributes or `type`+`association` for
references, and `UML:Association`).

The source XMI files are immutable OMG artifacts checked in under
`docs/sysml-v2/omg/20250201/` (provenance + SHA-256 in that directory's
README). They are never edited; this adapter reads them.
"""

from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

XMI_NS = "{http://www.omg.org/spec/XMI/20161101}"

# UML PrimitiveTypes hrefs map to Gaphor attribute `typeValue` strings. Anything
# else that is class-typed becomes a reference (association end).
_PRIMITIVE_SUFFIXES = {
    "String": "str",
    "Boolean": "bool",
    "Integer": "int",
    "UnlimitedNatural": "int",
    "Real": "float",
}


def _xmi(elem: ET.Element, key: str) -> str | None:
    return elem.get(XMI_NS + key) or elem.get(key)


@dataclass
class Attribute:
    """A primitive-typed owned attribute (becomes a Python attribute)."""

    name: str
    type_value: str  # Gaphor `typeValue`, e.g. "str", "bool"


@dataclass
class Reference:
    """A class-typed owned attribute (becomes a Python reference)."""

    name: str
    target: str  # name of the target class within the slice


@dataclass
class SliceClass:
    name: str
    attributes: list[Attribute] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)


def _classify_attribute(owned: ET.Element) -> tuple[str, str] | None:
    """Return ("attr", type_value) or ("ref", target_class) or None.

    Primitive attributes carry an href into UML PrimitiveTypes; class-typed
    references carry an idref to a class id within the metamodel.
    """
    type_child = owned.find("type")
    href = None
    idref = None
    if type_child is not None:
        idref = type_child.get(XMI_NS + "idref") or type_child.get("idref")
        href = type_child.get("href")
        if href is None:
            nested = type_child.find("*")
            if nested is not None:
                href = nested.get("href")
    idref = idref or owned.get("type")

    if href:
        suffix = href.rsplit("#", 1)[-1]
        type_value = _PRIMITIVE_SUFFIXES.get(suffix)
        if type_value:
            return ("attr", type_value)
        return None
    if idref:
        return ("ref", idref)
    return None


def extract_slice(
    xmi_path: Path, class_name: str, attributes: list[str], references: list[str]
) -> SliceClass:
    """Extract one class from the XMI, keeping only the named attributes/refs.

    `attributes` and `references` name which ownedAttributes of `class_name` to
    carry into the slice. References are kept only when the target resolves to
    the slice class itself (self-references), so the slice stays a single class
    with no semantics and no dangling targets.
    """
    root = ET.parse(xmi_path).getroot()

    # Index every element id -> (xmi:type, name) to resolve reference targets.
    index: dict[str, tuple[str | None, str | None]] = {}
    for elem in root.iter():
        cid = _xmi(elem, "id")
        if cid:
            index[cid] = (_xmi(elem, "type"), elem.get("name"))

    target_class = None
    for elem in root.iter():
        if _xmi(elem, "type") == "uml:Class" and elem.get("name") == class_name:
            target_class = elem
            break
    if target_class is None:
        raise ValueError(f"class {class_name!r} not found in {xmi_path}")

    class_id = _xmi(target_class, "id")
    result = SliceClass(name=class_name)
    wanted_attrs = set(attributes)
    wanted_refs = set(references)
    found_attrs: set[str] = set()
    found_refs: set[str] = set()
    misclassified: list[str] = []

    for owned in target_class:
        if not owned.tag.endswith("ownedAttribute"):
            continue
        pname = owned.get("name")
        if pname is None:
            continue
        kind = _classify_attribute(owned)
        if kind is None:
            # A requested name that exists but is neither a usable primitive
            # attribute nor a resolvable class reference is a spec-shape
            # mismatch, not something to skip silently.
            if pname in wanted_attrs or pname in wanted_refs:
                misclassified.append(pname)
            continue
        if pname in wanted_attrs:
            if kind[0] != "attr":
                misclassified.append(pname)
                continue
            result.attributes.append(Attribute(pname, kind[1]))
            found_attrs.add(pname)
        elif pname in wanted_refs:
            if kind[0] != "ref":
                misclassified.append(pname)
                continue
            tinfo = index.get(kind[1])
            target_name = tinfo[1] if tinfo else None
            # Keep self-references only (single-class slice, no dangling target).
            if target_name == class_name or kind[1] == class_id:
                result.references.append(Reference(pname, class_name))
                found_refs.add(pname)
            else:
                # Requested as a reference but targets another class: outside
                # the single-class slice contract.
                misclassified.append(pname)

    # Fail fast: a typo or spec-shape mismatch must surface as a clear adapter
    # error, never as a silently incomplete kernel.
    missing_attrs = sorted(wanted_attrs - found_attrs)
    missing_refs = sorted(wanted_refs - found_refs)
    if missing_attrs or missing_refs or misclassified:
        raise ValueError(
            f"slice extraction for class {class_name!r} incomplete: "
            f"missing attributes={missing_attrs}, missing references={missing_refs}, "
            f"unusable/misclassified={sorted(set(misclassified))}"
        )

    return result


# --- .gaphor model emission --------------------------------------------------

_MODEL_NS = "https://gaphor.org/model"
_UML_NS = "https://gaphor.org/modelinglanguage/UML"


# Fixed namespace UUID for deterministic, name-derived element ids. Stable ids
# keep the emitted `.gaphor` model byte-identical across runs, so regeneration
# (`poe sysml2-slice-model`) never dirties the worktree.
_ID_NAMESPACE = uuid.UUID("6f9b4d2e-3c1a-5e7f-8a0b-2d4c6e8f1a3b")


def _id(*parts: str) -> str:
    return str(uuid.uuid5(_ID_NAMESPACE, "/".join(parts)))


def emit_gaphor_model(slice_: SliceClass, package_name: str) -> str:
    """Render a SliceClass as a coder-ready `.gaphor` model XML string.

    The slice class generalizes Gaphor's `Base` so the generated class subclasses
    `Base` and integrates with `ElementFactory`/persistence. `Base` is emitted as
    an imported class in a `Core` package; running the coder with Core as a
    supermodel resolves it to `gaphor.core.modeling.base.Base` rather than
    regenerating it.
    """
    cls = slice_.name
    pkg_id = _id(package_name)
    class_id = _id(package_name, cls)
    core_pkg_id = _id("Core")
    base_id = _id("Core", "Base")
    generalization_id = _id(package_name, cls, "generalization", "Base")

    owned_attr_ids: list[str] = []
    property_blocks: list[str] = []
    association_blocks: list[str] = []

    # Primitive attributes: UML:Property with typeValue.
    for attr in slice_.attributes:
        pid = _id(package_name, cls, "attr", attr.name)
        owned_attr_ids.append(pid)
        property_blocks.append(
            f'<UML:Property id="{pid}">\n'
            f"<name><val>{escape(attr.name)}</val></name>\n"
            f'<structuredClassifier><ref refid="{class_id}"/></structuredClassifier>\n'
            f"<typeValue><val>{escape(attr.type_value)}</val></typeValue>\n"
            f"</UML:Property>"
        )

    # References: each is a self-association end (Property with type + association).
    for ref in slice_.references:
        end_id = _id(package_name, cls, "ref", ref.name)
        opposite_id = _id(package_name, cls, "ref", ref.name, "opposite")
        assoc_id = _id(package_name, cls, "assoc", ref.name)
        owned_attr_ids.append(end_id)
        property_blocks.append(
            f'<UML:Property id="{end_id}">\n'
            f"<aggregation><val>composite</val></aggregation>\n"
            f'<association><ref refid="{assoc_id}"/></association>\n'
            f"<name><val>{escape(ref.name)}</val></name>\n"
            f'<structuredClassifier><ref refid="{class_id}"/></structuredClassifier>\n'
            f'<type><ref refid="{class_id}"/></type>\n'
            f"</UML:Property>"
        )
        # Opposite (owned) end so the association has two member ends.
        property_blocks.append(
            f'<UML:Property id="{opposite_id}">\n'
            f"<name><val>{escape(ref.name)}_of</val></name>\n"
            f'<type><ref refid="{class_id}"/></type>\n'
            f'<owningAssociation><ref refid="{assoc_id}"/></owningAssociation>\n'
            f"</UML:Property>"
        )
        association_blocks.append(
            f'<UML:Association id="{assoc_id}">\n'
            f"<memberEnd><reflist>"
            f'<ref refid="{end_id}"/><ref refid="{opposite_id}"/>'
            f"</reflist></memberEnd>\n"
            f'<owningPackage><ref refid="{pkg_id}"/></owningPackage>\n'
            f'<package><ref refid="{pkg_id}"/></package>\n'
            f"</UML:Association>"
        )

    owned_reflist = "\n".join(f'<ref refid="{i}"/>' for i in owned_attr_ids)
    class_block = (
        f'<UML:Class id="{class_id}">\n'
        f"<name><val>{escape(slice_.name)}</val></name>\n"
        f"<ownedAttribute><reflist>\n{owned_reflist}\n</reflist></ownedAttribute>\n"
        f"<generalization><reflist>"
        f'<ref refid="{generalization_id}"/>'
        f"</reflist></generalization>\n"
        f'<owningPackage><ref refid="{pkg_id}"/></owningPackage>\n'
        f'<package><ref refid="{pkg_id}"/></package>\n'
        f"</UML:Class>"
    )

    package_block = (
        f'<UML:Package id="{pkg_id}">\n'
        f"<name><val>{escape(package_name)}</val></name>\n"
        f"</UML:Package>"
    )

    # Base, imported from the Core supermodel: a Core package + a Base class +
    # the Generalization linking the slice class to Base.
    core_package_block = (
        f'<UML:Package id="{core_pkg_id}">\n'
        f"<name><val>Core</val></name>\n"
        f"</UML:Package>"
    )
    base_class_block = (
        f'<UML:Class id="{base_id}">\n'
        f"<name><val>Base</val></name>\n"
        f'<owningPackage><ref refid="{core_pkg_id}"/></owningPackage>\n'
        f'<package><ref refid="{core_pkg_id}"/></package>\n'
        f"</UML:Class>"
    )
    generalization_block = (
        f'<UML:Generalization id="{generalization_id}">\n'
        f'<general><ref refid="{base_id}"/></general>\n'
        f'<specific><ref refid="{class_id}"/></specific>\n'
        f"</UML:Generalization>"
    )

    body = "\n".join(
        [
            package_block,
            class_block,
            core_package_block,
            base_class_block,
            generalization_block,
            *property_blocks,
            *association_blocks,
        ]
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<gaphor xmlns="{_MODEL_NS}" xmlns:UML="{_UML_NS}" '
        f'version="4" gaphor-version="3.1.0">\n'
        f"<model>\n{body}\n</model>\n"
        f"</gaphor>\n"
    )


def build_kerml_element_slice(xmi_path: Path) -> str:
    """The M1a slice: KerML `Element` with two primitive attributes and one
    self-reference, rendered as a coder-ready `.gaphor` model.
    """
    slice_ = extract_slice(
        xmi_path,
        class_name="Element",
        attributes=["declaredName", "isLibraryElement"],
        references=["ownedElement"],
    )
    return emit_gaphor_model(slice_, package_name="KerMLSlice")


def main(xmi_path: str, out_path: str) -> None:
    model_xml = build_kerml_element_slice(Path(xmi_path))
    Path(out_path).write_text(model_xml, encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    import sys

    main(sys.argv[1], sys.argv[2])
