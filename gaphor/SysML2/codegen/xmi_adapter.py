"""Adapter: OMG normative MOF XMI -> Gaphor `.gaphor` model.

The M0 finding established that Gaphor generates Python `Base` subclasses from
`.gaphor` model files via `gaphor.codegen.coder`, not from external XMI. So the
realistic generator path is two-step:

    normative MOF XMI  --(this adapter)-->  .gaphor model  --(coder)-->  Python

The adapter introduces no SysML v2 semantics: it only translates the
abstract-syntax shape (classes, generalizations, primitive-typed attributes,
class-typed references/associations) into the `.gaphor` model elements the coder
reads (`UML:Package`, `UML:Class` with `generalization`, `UML:Property` with
`typeValue` for attributes or `type`+`association` for references, and
`UML:Association`).

Two entry points:

- `build_kerml_element_slice` (M1a): a single semantics-free class, used to
  prove the generator path.
- `build_kerml_kernel` (M1b): the transitive closure of the minimal KerML
  kernel classes, generated as a connected multi-class model.

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
    """A stored class-typed owned attribute (becomes a Python association)."""

    name: str
    target: str  # name of the target class within the slice
    composite: bool = False  # only the containment whitelist cascades on delete


@dataclass
class EnumAttribute:
    """An enumeration-typed owned attribute (becomes a Gaphor enumeration)."""

    name: str
    enum: str  # name of the target enumeration


@dataclass
class EnumType:
    """An enumeration reached from an in-scope class property."""

    name: str
    literals: list[str] = field(default_factory=list)


@dataclass
class DerivedAttribute:
    """A derived primitive/enum property: classified for audit, NOT persisted.

    KerML marks these `isDerived=true`; the behaviour layer computes them, so
    persisting them would create stale state. Kept as metadata so tests and docs
    can prove the exclusion is intentional.
    """

    name: str


@dataclass
class DerivedReference:
    """A derived class-typed property: classified for audit, NOT persisted."""

    name: str
    target: str


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


def _owned_type_idref(owned: ET.Element) -> tuple[str | None, str | None]:
    """Return (primitive_type_value, idref) for an ownedAttribute's type.

    Exactly one is non-None for a typed property: a primitive href yields a
    type_value; an in-model type yields an idref. Untyped -> (None, None).
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
        return (_PRIMITIVE_SUFFIXES.get(href.rsplit("#", 1)[-1]), None)
    return (None, idref)


def _enum_literals(enum_elem: ET.Element) -> list[str]:
    return [
        c.get("name")
        for c in enum_elem
        if c.tag.endswith("ownedLiteral") and c.get("name")
    ]


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


# --- M1b: multi-class kernel closure -----------------------------------------

# Seed classes of the minimal KerML kernel (kickoff plan, M1b). The full set is
# the transitive closure of these over generalizations and class-typed
# references; out-of-closure references are pruned so the model stays connected.
KERNEL_SEED = (
    "Element",
    "Relationship",
    "Namespace",
    "Membership",
    "OwningMembership",
    "Type",
    "Feature",
    "Specialization",
    "Import",
    "Documentation",
    # Classifier roots the SysML layer generalizes (PartDefinition -> ... ->
    # Classifier/Class/Structure). Added so the KerML kernel can serve as the
    # supermodel for the generated SysML classes, the way Core serves KerML.
    "Classifier",
    "Class",
    "Structure",
    # FeatureTyping carries the stored type/feature relation (typedFeature, type)
    # the M2 tracer needs to type a PartUsage by a PartDefinition.
    "FeatureTyping",
    # Package is a Namespace; the `package X { ... }` construct maps onto it and
    # nests members/sub-packages through the existing OwningMembership spine.
    "Package",
    # DataType is the KerML Classifier that AttributeDefinition generalizes;
    # needed as a supermodel root for the SysML attribute layer.
    "DataType",
    # BooleanExpression and Predicate are the KerML expression roots that the
    # SysML constraint layer generalizes (ConstraintUsage -> BooleanExpression,
    # ConstraintDefinition -> Predicate), which RequirementUsage/Definition build
    # on. Seeding them pulls their self-contained closure (Expression, Step,
    # Function, Behavior) into the supermodel so the SysML constraint/requirement
    # chain generalizes a real KerML super instead of silently dropping it.
    "BooleanExpression",
    "Predicate",
    # AssociationStructure and Connector are the KerML relationship roots the
    # SysML connection layer generalizes (ConnectionDefinition ->
    # AssociationStructure, ConnectorAsUsage -> Connector), which
    # ConnectionUsage/Definition build on. Seeding them pulls their self-contained
    # closure (Association) into the supermodel so the SysML connection chain
    # generalizes a real KerML super instead of silently dropping it. Connector's
    # own end properties (relatedFeature, connectorEnd, association) are derived,
    # so they are classified as metadata and NOT persisted -- no endpoint state is
    # stored; the connector-end semantics remain a later behavior-layer dependency.
    "AssociationStructure",
    "Connector",
)


# Containment whitelist: the only references that own their target's lifetime
# (composite, cascade-on-delete). KerML's containment spine. The XMI carries no
# aggregation metadata, so this is an explicit, tested mapping decision rather
# than a heuristic; extend it only with a new tested decision.
COMPOSITE_REFS: frozenset[tuple[str, str]] = frozenset(
    {
        ("Element", "ownedRelationship"),
        ("Relationship", "ownedRelatedElement"),
    }
)


@dataclass
class KernelClass:
    name: str
    supers: list[str] = field(default_factory=list)
    attributes: list[Attribute] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    enum_attributes: list[EnumAttribute] = field(default_factory=list)
    # Derived properties (isDerived=true): classified for audit, NOT persisted.
    derived_attributes: list[DerivedAttribute] = field(default_factory=list)
    derived_references: list[DerivedReference] = field(default_factory=list)


@dataclass
class Kernel:
    classes: list[KernelClass] = field(default_factory=list)
    enums: list[EnumType] = field(default_factory=list)


def _href_class_name(href: str) -> str:
    """Resolve a cross-file generalization href to a KerML class name.

    SysML classes generalize KerML classes via an external href, e.g.
    `...KerML.xmi#Core-Features-Feature`. The fragment's final hyphen-segment is
    the class name (`Feature`).
    """
    return href.rsplit("#", 1)[-1].rsplit("-", 1)[-1]


def _generalizations(class_elem: ET.Element, index: dict[str, tuple]) -> list[str]:
    names: list[str] = []
    for child in class_elem:
        if not child.tag.endswith("generalization"):
            continue
        general = child.find("general")
        gid = child.get("general")
        href = None
        if general is not None:
            gid = general.get(XMI_NS + "idref") or general.get("idref")
            href = general.get("href")
        if href:
            names.append(_href_class_name(href))
        elif gid:
            tinfo = index.get(gid)
            if tinfo and tinfo[1]:
                names.append(tinfo[1])
    return names


def extract_kernel(xmi_path: Path, seed: tuple[str, ...] = KERNEL_SEED) -> Kernel:
    """Extract the transitive closure of `seed` classes from the XMI.

    Each owned property is classified three ways:

    - primitive href  -> a `typeValue` attribute;
    - `uml:Class`      -> a reference; the class closure follows it;
    - `uml:Enumeration`-> an enum attribute; the enumeration is collected as a
      value-domain dependency but is NOT a class and does not extend the closure.

    A property whose type is none of these (an unknown target-type category)
    raises, so spec-shape surprises fail fast rather than silently dropping a
    real KerML property. The result (classes + enums) is sorted for determinism.
    """
    root = ET.parse(xmi_path).getroot()

    # Index every element id -> (xmi:type, name, element).
    index: dict[str, tuple[str | None, str | None, ET.Element]] = {}
    for elem in root.iter():
        cid = _xmi(elem, "id")
        if cid:
            index[cid] = (_xmi(elem, "type"), elem.get("name"), elem)

    by_name: dict[str, ET.Element] = {}
    for elem in root.iter():
        if _xmi(elem, "type") == "uml:Class" and elem.get("name"):
            by_name.setdefault(elem.get("name"), elem)

    # Fail fast: every seed name must be a real class in the XMI. A typo or spec
    # rename must not silently shrink the kernel.
    missing_seed = sorted(n for n in seed if n not in by_name)
    if missing_seed:
        raise ValueError(
            f"seed classes not found in {xmi_path}: {missing_seed}"
        )

    def index_name(idref: str) -> tuple[str | None, str | None]:
        info = index.get(idref)
        return (info[0], info[1]) if info else (None, None)

    @dataclass
    class _Raw:
        attrs: list[Attribute] = field(default_factory=list)
        refs: list[Reference] = field(default_factory=list)
        enum_attrs: list[EnumAttribute] = field(default_factory=list)
        derived_attrs: list[DerivedAttribute] = field(default_factory=list)
        derived_refs: list[DerivedReference] = field(default_factory=list)

    # Per-class extraction. `isDerived=true` properties are classified into
    # `derived_*` (audit metadata, NOT persisted); only non-derived properties
    # become persisted structure. `enum_targets` accumulates enum ids reached
    # from NON-derived enum attributes (the only enums actually emitted).
    def raw(class_elem: ET.Element, enum_targets: set[str]) -> _Raw:
        out = _Raw()
        for owned in class_elem:
            if not owned.tag.endswith("ownedAttribute"):
                continue
            pname = owned.get("name")
            if not pname:
                continue
            derived = owned.get("isDerived") == "true"
            type_value, idref = _owned_type_idref(owned)

            if type_value is not None:
                if derived:
                    out.derived_attrs.append(DerivedAttribute(pname))
                else:
                    out.attrs.append(Attribute(pname, type_value))
                continue
            if idref is None:
                continue  # untyped (e.g. derived with no declared type): nothing
            target_type, target_name = index_name(idref)

            if target_type == "uml:Class" and target_name:
                if derived:
                    out.derived_refs.append(DerivedReference(pname, target_name))
                else:
                    composite = (class_elem.get("name"), pname) in COMPOSITE_REFS
                    out.refs.append(Reference(pname, target_name, composite=composite))
            elif target_type == "uml:Enumeration" and target_name:
                if derived:
                    out.derived_attrs.append(DerivedAttribute(pname))
                else:
                    enum_targets.add(idref)
                    out.enum_attrs.append(EnumAttribute(pname, target_name))
            elif target_type is None:
                # Unresolvable href to an external primitive we don't map -> skip.
                continue
            else:
                raise ValueError(
                    f"{class_elem.get('name')}.{pname}: unsupported target type "
                    f"{target_type!r} (target {target_name!r}); add an explicit "
                    f"handling/deferral rule rather than dropping it silently"
                )
        return out

    # Compute the class closure. Follows generalizations and STORED class refs
    # only -- derived refs are semantic views and must not extend the closure.
    scratch: set[str] = set()
    closure: set[str] = set()
    frontier = set(seed)
    while frontier:
        name = frontier.pop()
        if name in closure or name not in by_name:
            closure.add(name)
            continue
        closure.add(name)
        elem = by_name[name]
        for s in _generalizations(elem, index):
            if s not in closure:
                frontier.add(s)
        for ref in raw(elem, scratch).refs:
            if ref.target not in closure:
                frontier.add(ref.target)

    present = sorted(n for n in closure if n in by_name)

    classes: list[KernelClass] = []
    enum_targets: set[str] = set()
    for name in present:
        elem = by_name[name]
        r = raw(elem, enum_targets)
        # Keep all super names (in-closure or external/supermodel); the emitter
        # resolves each to a full class, a supermodel import stub, or Base.
        supers = _generalizations(elem, index)
        kept_refs = [ref for ref in r.refs if ref.target in closure]
        classes.append(
            KernelClass(
                name=name,
                supers=supers,
                attributes=r.attrs,
                references=kept_refs,
                enum_attributes=r.enum_attrs,
                derived_attributes=r.derived_attrs,
                derived_references=r.derived_refs,
            )
        )

    enums: list[EnumType] = []
    for eid in sorted(enum_targets, key=lambda i: index[i][1] or ""):
        _etype, ename, eelem = index[eid]
        enums.append(EnumType(name=ename, literals=_enum_literals(eelem)))

    return Kernel(classes=classes, enums=enums)


def emit_gaphor_kernel_model(
    kernel: Kernel,
    package_name: str,
    supermodel_supers: frozenset[str] = frozenset(),
    supermodel_package: str | None = None,
) -> str:
    """Render a multi-class kernel as a coder-ready `.gaphor` model.

    Generalization resolution per super name:
    - a super that is a generated class in this model -> a full class reference;
    - a super in `supermodel_supers` -> an imported stub in `supermodel_package`
      (resolved by the coder via that supermodel, e.g. SysML2 classes -> KerML);
    - otherwise, a root class -> Gaphor `Base` via the Core supermodel.

    Each class-typed reference is a one-directional association end; enumeration
    properties point at emitted `UML:Enumeration` value-domain types.
    """
    classes = kernel.classes
    class_names = {c.name for c in classes}
    pkg_id = _id(package_name)
    core_pkg_id = _id("Core")
    base_id = _id("Core", "Base")
    # Supermodel stubs (e.g. KerML classes the SysML layer generalizes).
    supermodel_pkg_id = _id(supermodel_package) if supermodel_package else None
    supermodel_ids = {
        name: _id(supermodel_package or "", "super", name)
        for name in supermodel_supers
    }
    class_ids = {c.name: _id(package_name, c.name) for c in classes}
    enum_ids = {e.name: _id(package_name, "enum", e.name) for e in kernel.enums}

    blocks: list[str] = []
    enum_blocks: list[str] = []
    generalization_blocks: list[str] = []
    property_blocks: list[str] = []
    association_blocks: list[str] = []

    # Enumerations (value-domain types): UML:Enumeration + UML:EnumerationLiteral.
    for enum in kernel.enums:
        literal_ids: list[str] = []
        for literal in enum.literals:
            lid = _id(package_name, "enum", enum.name, "literal", literal)
            literal_ids.append(lid)
            enum_blocks.append(
                f'<UML:EnumerationLiteral id="{lid}">\n'
                f'<enumeration><ref refid="{enum_ids[enum.name]}"/></enumeration>\n'
                f"<name><val>{escape(literal)}</val></name>\n"
                f"</UML:EnumerationLiteral>"
            )
        literal_reflist = "\n".join(f'<ref refid="{i}"/>' for i in literal_ids)
        enum_blocks.append(
            f'<UML:Enumeration id="{enum_ids[enum.name]}">\n'
            f"<name><val>{escape(enum.name)}</val></name>\n"
            f"<ownedLiteral><reflist>\n{literal_reflist}\n</reflist></ownedLiteral>\n"
            f'<owningPackage><ref refid="{pkg_id}"/></owningPackage>\n'
            f'<package><ref refid="{pkg_id}"/></package>\n'
            f"</UML:Enumeration>"
        )

    for c in classes:
        owned_attr_ids: list[str] = []
        gen_ids: list[str] = []

        for attr in c.attributes:
            pid = _id(package_name, c.name, "attr", attr.name)
            owned_attr_ids.append(pid)
            property_blocks.append(
                f'<UML:Property id="{pid}">\n'
                f"<name><val>{escape(attr.name)}</val></name>\n"
                f'<structuredClassifier><ref refid="{class_ids[c.name]}"/></structuredClassifier>\n'
                f"<typeValue><val>{escape(attr.type_value)}</val></typeValue>\n"
                f"</UML:Property>"
            )

        for enum_attr in c.enum_attributes:
            pid = _id(package_name, c.name, "enumattr", enum_attr.name)
            owned_attr_ids.append(pid)
            property_blocks.append(
                f'<UML:Property id="{pid}">\n'
                f"<name><val>{escape(enum_attr.name)}</val></name>\n"
                f'<structuredClassifier><ref refid="{class_ids[c.name]}"/></structuredClassifier>\n'
                f'<type><ref refid="{enum_ids[enum_attr.enum]}"/></type>\n'
                f"</UML:Property>"
            )

        for ref in c.references:
            end_id = _id(package_name, c.name, "ref", ref.name)
            opposite_id = _id(package_name, c.name, "ref", ref.name, "opposite")
            assoc_id = _id(package_name, c.name, "assoc", ref.name)
            owned_attr_ids.append(end_id)
            # Composite only for the containment whitelist (cascade on delete);
            # all other references are plain (non-owning) and must not cascade.
            aggregation = (
                "<aggregation><val>composite</val></aggregation>\n"
                if ref.composite
                else ""
            )
            property_blocks.append(
                f'<UML:Property id="{end_id}">\n'
                f"{aggregation}"
                f'<association><ref refid="{assoc_id}"/></association>\n'
                f"<name><val>{escape(ref.name)}</val></name>\n"
                f'<structuredClassifier><ref refid="{class_ids[c.name]}"/></structuredClassifier>\n'
                f'<type><ref refid="{class_ids[ref.target]}"/></type>\n'
                f"</UML:Property>"
            )
            property_blocks.append(
                f'<UML:Property id="{opposite_id}">\n'
                f"<name><val>{escape(c.name)}_{escape(ref.name)}_of</val></name>\n"
                f'<type><ref refid="{class_ids[c.name]}"/></type>\n'
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

        # Generalizations: resolve each super to a full class (in this model), a
        # supermodel stub, or Base for true roots.
        resolved_supers = [
            s for s in c.supers if s in class_names or s in supermodel_supers
        ]
        # Fail fast (invariant 8: never silently drop syntax/structure): if a
        # class declares supers but some do not resolve to a generated class or a
        # supermodel stub, the generated class would lose a real generalization.
        # A genuine root (no declared supers at all) legitimately becomes Base.
        if c.supers and len(resolved_supers) != len(c.supers):
            dropped = [
                s for s in c.supers if s not in class_names and s not in supermodel_supers
            ]
            raise ValueError(
                f"{c.name}: generalization(s) {dropped} resolve to neither a "
                f"generated class nor a supermodel super; seed the missing "
                f"supermodel class(es) instead of dropping the generalization"
            )
        if not resolved_supers:
            resolved_supers = ["Base"]
        for super_name in resolved_supers:
            gid = _id(package_name, c.name, "generalization", super_name)
            gen_ids.append(gid)
            if super_name == "Base":
                general_ref = base_id
            elif super_name in class_names:
                general_ref = class_ids[super_name]
            else:  # supermodel stub
                general_ref = supermodel_ids[super_name]
            generalization_blocks.append(
                f'<UML:Generalization id="{gid}">\n'
                f'<general><ref refid="{general_ref}"/></general>\n'
                f'<specific><ref refid="{class_ids[c.name]}"/></specific>\n'
                f"</UML:Generalization>"
            )

        owned_reflist = "\n".join(f'<ref refid="{i}"/>' for i in owned_attr_ids)
        gen_reflist = "\n".join(f'<ref refid="{i}"/>' for i in gen_ids)
        blocks.append(
            f'<UML:Class id="{class_ids[c.name]}">\n'
            f"<name><val>{escape(c.name)}</val></name>\n"
            f"<ownedAttribute><reflist>\n{owned_reflist}\n</reflist></ownedAttribute>\n"
            f"<generalization><reflist>\n{gen_reflist}\n</reflist></generalization>\n"
            f'<owningPackage><ref refid="{pkg_id}"/></owningPackage>\n'
            f'<package><ref refid="{pkg_id}"/></package>\n'
            f"</UML:Class>"
        )

    package_block = (
        f'<UML:Package id="{pkg_id}">\n'
        f"<name><val>{escape(package_name)}</val></name>\n"
        f"</UML:Package>"
    )
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

    # Supermodel package + imported stubs (e.g. the KerML classes the SysML
    # layer generalizes). Only emitted for supers actually used by this model.
    supermodel_blocks: list[str] = []
    used_supermodel_supers = sorted(
        s for c in classes for s in c.supers if s in supermodel_supers
    )
    if supermodel_package and used_supermodel_supers:
        supermodel_blocks.append(
            f'<UML:Package id="{supermodel_pkg_id}">\n'
            f"<name><val>{escape(supermodel_package)}</val></name>\n"
            f"</UML:Package>"
        )
        for super_name in dict.fromkeys(used_supermodel_supers):
            supermodel_blocks.append(
                f'<UML:Class id="{supermodel_ids[super_name]}">\n'
                f"<name><val>{escape(super_name)}</val></name>\n"
                f'<owningPackage><ref refid="{supermodel_pkg_id}"/></owningPackage>\n'
                f'<package><ref refid="{supermodel_pkg_id}"/></package>\n'
                f"</UML:Class>"
            )

    body = "\n".join(
        [
            package_block,
            core_package_block,
            base_class_block,
            *supermodel_blocks,
            *enum_blocks,
            *blocks,
            *generalization_blocks,
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


def build_kerml_kernel(xmi_path: Path) -> str:
    """The M1b kernel: transitive closure of the minimal KerML kernel classes,
    rendered as a coder-ready multi-class `.gaphor` model.
    """
    classes = extract_kernel(xmi_path)
    # The class package must NOT be named with the supermodel key ("KerML"):
    # the coder's in_super_model resolves a supermodel super only when it is
    # found in a package that is itself NOT a supermodel key. The KerML
    # modeling language still resolves these classes under the "KerML" namespace.
    return emit_gaphor_kernel_model(classes, package_name="KerMLKernel")


# --- M2: SysML user-concept layer on the KerML kernel ------------------------

# Seed of the SysML vertical-tracer slice (PartDefinition/PartUsage and their
# stored-reference closure within SysML.xmi). Their generalizations to KerML
# classes are resolved against the KerML kernel supermodel, not regenerated.
SYSML_SEED = (
    "PartDefinition",
    "PartUsage",
    "AttributeDefinition",
    "AttributeUsage",
    "ActionDefinition",
    "ActionUsage",
    # RequirementDefinition/Usage generalize ConstraintDefinition/Usage, which in
    # turn generalize the KerML expression roots Predicate/BooleanExpression (now
    # in the kernel supermodel). Constraint is seeded explicitly because it is the
    # requirement's direct super and a construct in its own right.
    "ConstraintDefinition",
    "ConstraintUsage",
    "RequirementDefinition",
    "RequirementUsage",
    # PortDefinition/Usage for the declaration-and-typing surface. Their supers
    # (Structure, OccurrenceDefinition, OccurrenceUsage) are already in the
    # model, so no kernel growth is needed. Port conjugation (PortConjugation /
    # KerML Conjugation) and interface/flow semantics are deliberately NOT pulled
    # in -- that is a named later dependency, not unused structure added now.
    "PortDefinition",
    "PortUsage",
    # ConnectionDefinition/Usage for the declaration-and-typing surface, plus
    # ConnectorAsUsage (their connector super, pulled into the closure). Their
    # KerML supers AssociationStructure/Connector are now in the kernel. The
    # connector-end properties (relatedFeature/connectorEnd/association) are
    # derived and never persisted: connecting two ends is a named later
    # behavior-layer dependency, not a faked stored endpoint here.
    "ConnectionDefinition",
    "ConnectionUsage",
)

# KerML classes that the generated SysML kernel must already provide as a
# supermodel (the SysML closure generalizes these). Kept here so the generator
# can verify the supermodel actually supplies them.
SYSML_KERML_SUPERS = (
    "Definition",  # SysML-internal, but its supers are KerML
    "Usage",
)


def extract_sysml(xmi_path: Path, seed: tuple[str, ...] = SYSML_SEED) -> Kernel:
    """Extract the SysML closure over STORED refs within SysML.xmi.

    Generalizations to KerML classes (external hrefs) are recorded as super
    names; the closure does not try to pull KerML classes out of SysML.xmi
    (they live in the KerML supermodel). Same three-way property classification
    and fail-fast rules as `extract_kernel`.
    """
    return extract_kernel(xmi_path, seed=seed)


def build_sysml_model(xmi_path: Path, kerml_class_names: frozenset[str]) -> str:
    """Render the SysML closure, generalizing KerML supers as supermodel imports.

    `kerml_class_names` is the set of class names the KerML supermodel provides;
    any SysML super in that set is emitted as an imported stub in a `KerML`
    package (resolved by the coder via the supermodel), not as a full class.
    """
    kernel = extract_sysml(xmi_path)
    return emit_gaphor_kernel_model(
        kernel,
        package_name="SysML2",
        supermodel_supers=kerml_class_names,
        supermodel_package="KerML",
    )


def kerml_class_names(xmi_path: Path) -> frozenset[str]:
    """The class names the generated KerML kernel provides (for supermodel use)."""
    return frozenset(c.name for c in extract_kernel(xmi_path).classes)


def main(xmi_path: str, out_path: str) -> None:
    model_xml = build_kerml_element_slice(Path(xmi_path))
    Path(out_path).write_text(model_xml, encoding="utf-8")
    print(f"wrote {out_path}")


def main_kernel(xmi_path: str, out_path: str) -> None:
    model_xml = build_kerml_kernel(Path(xmi_path))
    Path(out_path).write_text(model_xml, encoding="utf-8")
    print(f"wrote {out_path}")


def main_sysml(sysml_xmi_path: str, kerml_xmi_path: str, out_path: str) -> None:
    supers = kerml_class_names(Path(kerml_xmi_path))
    model_xml = build_sysml_model(Path(sysml_xmi_path), supers)
    Path(out_path).write_text(model_xml, encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    import sys

    main(sys.argv[1], sys.argv[2])
