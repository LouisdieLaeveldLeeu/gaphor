"""Versioned spec-ingestion pipeline (completion-roadmap Phase 11).

Maintainer tooling to assess a FUTURE OMG SysML/KerML release MECHANICALLY before any
human mapping decision. It does NOT change the model or the generator; it reads the
pinned XMI abstract syntax and reports what a new release would change.

Four parts, surfaced as `poe` tasks (no user-facing CLI):

- INDEX (`index_xmi`): parse an XMI into a `MetamodelIndex` -- every class (name,
  abstractness, generalizations, owned properties with type / stored-vs-derived /
  attribute-vs-reference-vs-enum) and every enumeration's literals. A committed JSON
  BASELINE of each pinned XMI is the "current pinned" snapshot a new release is
  assessed against; a test guards that the baseline still matches the live XMI.
- DIFF (`diff_indexes`): added/removed classes, added/removed/changed properties,
  derived<->stored flips, type changes, and added/removed enumerations and literals.
- REVIEW (`review_findings`): a FAIL-FAST report of changes that need a human mapping
  decision -- above all a NEW STORED REFERENCE, which needs an ownership policy (is it
  composite/cascade? -- checked against `xmi_adapter.COMPOSITE_REFS`), plus new/removed
  classes, removed properties, derived<->stored flips, and removed enum literals.
- MANIFEST REFRESH (`compute_manifest_rows`): SHA-256 + byte size for each pinned
  artifact, to refresh the provenance manifest when bumping the pin.

The versioned workflow needs no arguments: pin a new XMI (replace the file), run
`poe sysml2-spec-diff` to diff the committed baseline against the live XMI and get the
review report (non-zero exit on review findings), make the mapping decisions, then run
`poe sysml2-spec-index` to accept the new version (regenerate the baseline).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from gaphor.SysML2.codegen.xmi_adapter import (
    COMPOSITE_REFS,
    _enum_literals,
    _href_class_name,
    _owned_type_idref,
    _xmi,
)

#: The pinned artifact directory and the XMIs whose baselines are committed.
OMG_DIR = Path(__file__).resolve().parents[1] / ".." / ".." / "docs" / "sysml-v2" / "omg" / "20250201"
_INDEXED_XMI = ("KerML.xmi", "SysML.xmi")
#: Where the committed JSON baseline indexes live (one per XMI).
BASELINE_DIR = Path(__file__).resolve().parent / "spec_baseline"

# A property kind: a primitive attribute, an enumeration-typed attribute, or a
# class-typed reference (an association end).
ATTRIBUTE, ENUM, REFERENCE = "attribute", "enum", "reference"


# --- the metamodel index -----------------------------------------------------


@dataclass(frozen=True)
class Property:
    """An owned property of a metaclass."""

    name: str
    type: str  # primitive ("str"/"bool"/...), enum name, target class name, or ""
    kind: str  # ATTRIBUTE | ENUM | REFERENCE
    derived: bool  # isDerived=true -> computed, NOT stored

    @property
    def stored_reference(self) -> bool:
        """A class-typed property that is PERSISTED (the ones needing an ownership
        policy: composite/cascade or not)."""
        return self.kind == REFERENCE and not self.derived

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type,
            "kind": self.kind,
            "derived": self.derived,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Property:
        return cls(data["name"], data["type"], data["kind"], data["derived"])


@dataclass(frozen=True)
class Class:
    """A metaclass: its name, abstractness, supertype names, and owned properties."""

    name: str
    abstract: bool
    generalizations: tuple[str, ...]
    properties: tuple[Property, ...]

    def property(self, name: str) -> Property | None:
        return next((p for p in self.properties if p.name == name), None)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "abstract": self.abstract,
            "generalizations": list(self.generalizations),
            "properties": [p.to_dict() for p in self.properties],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Class:
        return cls(
            data["name"],
            data["abstract"],
            tuple(data["generalizations"]),
            tuple(Property.from_dict(p) for p in data["properties"]),
        )


@dataclass(frozen=True)
class MetamodelIndex:
    """The indexed abstract syntax of one XMI: its classes and enumerations."""

    source: str
    classes: tuple[Class, ...]
    enums: tuple[tuple[str, tuple[str, ...]], ...]  # (enum name, literals)

    def class_(self, name: str) -> Class | None:
        return next((c for c in self.classes if c.name == name), None)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "classes": [c.to_dict() for c in self.classes],
            "enums": [{"name": n, "literals": list(ls)} for n, ls in self.enums],
        }

    @classmethod
    def from_dict(cls, data: dict) -> MetamodelIndex:
        return cls(
            data["source"],
            tuple(Class.from_dict(c) for c in data["classes"]),
            tuple((e["name"], tuple(e["literals"])) for e in data["enums"]),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=False) + "\n"

    @classmethod
    def from_json(cls, text: str) -> MetamodelIndex:
        return cls.from_dict(json.loads(text))


def index_xmi(path: str | Path) -> MetamodelIndex:
    """Index one OMG MOF XMI into a `MetamodelIndex` (deterministic, sorted)."""
    path = Path(path)
    root = ET.parse(path).getroot()

    id_to_name: dict[str, str] = {}
    enum_ids: set[str] = set()
    for element in root.iter():
        if not element.tag.endswith("packagedElement"):
            continue
        element_id = _xmi(element, "id")
        name = element.get("name")
        if element_id and name:
            id_to_name[element_id] = name
        if element_id and _xmi(element, "type") == "uml:Enumeration":
            enum_ids.add(element_id)

    classes: list[Class] = []
    enums: list[tuple[str, tuple[str, ...]]] = []
    for element in root.iter():
        if not element.tag.endswith("packagedElement"):
            continue
        name = element.get("name")
        if not name:
            continue
        kind = _xmi(element, "type")
        if kind == "uml:Class":
            classes.append(_index_class(element, name, id_to_name, enum_ids))
        elif kind == "uml:Enumeration":
            enums.append((name, tuple(_enum_literals(element))))

    return MetamodelIndex(
        source=path.name,
        classes=tuple(sorted(classes, key=lambda c: c.name)),
        enums=tuple(sorted(enums)),
    )


def _type_href(owned: ET.Element) -> str | None:
    """The href of an ownedAttribute's type (direct or nested), or None -- the same
    extraction `_owned_type_idref` uses, exposed so a NON-primitive external type
    (a SysML property typed by a KerML class) can be resolved instead of dropped."""
    type_child = owned.find("type")
    if type_child is None:
        return None
    href = type_child.get("href")
    if href is None:
        nested = type_child.find("*")
        if nested is not None:
            href = nested.get("href")
    return href


def _index_class(
    element: ET.Element, name: str, id_to_name: dict[str, str], enum_ids: set[str]
) -> Class:
    generalizations: set[str] = set()
    properties: list[Property] = []
    for child in element:
        if child.tag.endswith("generalization"):
            general = child.find("general")
            # A SAME-document supertype is an xmi:idref; a CROSS-document one (a SysML
            # class generalizing a KerML class) is an href -- resolve both, else the
            # index silently drops external supers (e.g. FlowDefinition :> Interaction).
            href = general.get("href") if general is not None else None
            gid = (
                (_xmi(general, "idref") if general is not None else None)
                or child.get("general")
            )
            if href:
                generalizations.add(_href_class_name(href))
            elif gid:
                generalizations.add(id_to_name.get(gid, gid))
        elif child.tag.endswith("ownedAttribute"):
            prop_name = child.get("name")
            if not prop_name:
                continue
            primitive, idref = _owned_type_idref(child)
            if primitive is not None:
                kind, type_name = ATTRIBUTE, primitive
            elif idref is not None:
                kind = ENUM if idref in enum_ids else REFERENCE
                type_name = id_to_name.get(idref, idref)
            elif (href := _type_href(child)) is not None:
                # A cross-document property type (a SysML property typed by a KerML
                # class, e.g. ...#Kernel-Functions-Expression) -- resolve it like a
                # generalization href, else a future change between two external
                # targets (Expression -> Predicate) is invisible to the diff.
                kind, type_name = REFERENCE, _href_class_name(href)
            else:
                kind, type_name = REFERENCE, ""
            properties.append(
                Property(
                    prop_name, type_name, kind, child.get("isDerived") == "true"
                )
            )
    return Class(
        name=name,
        abstract=element.get("isAbstract") == "true",
        generalizations=tuple(sorted(generalizations)),
        properties=tuple(sorted(properties, key=lambda p: p.name)),
    )


# --- the diff ----------------------------------------------------------------


@dataclass(frozen=True)
class MetamodelDiff:
    """The delta from `old` to `new` (everything empty when identical)."""

    source: str
    added_classes: tuple[Class, ...]
    removed_classes: tuple[str, ...]
    # Class-level changes for a class that exists in BOTH (its generalizations or
    # abstractness changed even if its properties did not): (class, old, new).
    changed_generalizations: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...]
    changed_abstractness: tuple[tuple[str, bool, bool], ...]
    added_properties: tuple[tuple[str, Property], ...]  # (class name, new property)
    removed_properties: tuple[tuple[str, str], ...]  # (class name, property name)
    changed_properties: tuple[tuple[str, Property, Property], ...]  # (class, old, new)
    added_enums: tuple[str, ...]
    removed_enums: tuple[str, ...]
    added_enum_literals: tuple[tuple[str, str], ...]  # (enum, literal)
    removed_enum_literals: tuple[tuple[str, str], ...]

    @property
    def is_empty(self) -> bool:
        return not any(
            (
                self.added_classes,
                self.removed_classes,
                self.changed_generalizations,
                self.changed_abstractness,
                self.added_properties,
                self.removed_properties,
                self.changed_properties,
                self.added_enums,
                self.removed_enums,
                self.added_enum_literals,
                self.removed_enum_literals,
            )
        )


def diff_indexes(old: MetamodelIndex, new: MetamodelIndex) -> MetamodelDiff:
    """Compare two metamodel indexes, reporting every abstract-syntax change."""
    old_classes = {c.name: c for c in old.classes}
    new_classes = {c.name: c for c in new.classes}

    added_classes = tuple(
        new_classes[name] for name in sorted(new_classes.keys() - old_classes.keys())
    )
    removed_classes = tuple(sorted(old_classes.keys() - new_classes.keys()))

    changed_generalizations: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []
    changed_abstractness: list[tuple[str, bool, bool]] = []
    added_properties: list[tuple[str, Property]] = []
    removed_properties: list[tuple[str, str]] = []
    changed_properties: list[tuple[str, Property, Property]] = []
    for name in sorted(old_classes.keys() & new_classes.keys()):
        old_class, new_class = old_classes[name], new_classes[name]
        if old_class.generalizations != new_class.generalizations:
            changed_generalizations.append(
                (name, old_class.generalizations, new_class.generalizations)
            )
        if old_class.abstract != new_class.abstract:
            changed_abstractness.append((name, old_class.abstract, new_class.abstract))
        old_props = {p.name: p for p in old_classes[name].properties}
        new_props = {p.name: p for p in new_classes[name].properties}
        for prop in sorted(new_props.keys() - old_props.keys()):
            added_properties.append((name, new_props[prop]))
        for prop in sorted(old_props.keys() - new_props.keys()):
            removed_properties.append((name, prop))
        for prop in sorted(old_props.keys() & new_props.keys()):
            if old_props[prop] != new_props[prop]:
                changed_properties.append((name, old_props[prop], new_props[prop]))

    old_enums = dict(old.enums)
    new_enums = dict(new.enums)
    added_enums = tuple(sorted(new_enums.keys() - old_enums.keys()))
    removed_enums = tuple(sorted(old_enums.keys() - new_enums.keys()))
    added_enum_literals: list[tuple[str, str]] = []
    removed_enum_literals: list[tuple[str, str]] = []
    for enum in sorted(old_enums.keys() & new_enums.keys()):
        old_lits, new_lits = set(old_enums[enum]), set(new_enums[enum])
        added_enum_literals += [(enum, lit) for lit in sorted(new_lits - old_lits)]
        removed_enum_literals += [(enum, lit) for lit in sorted(old_lits - new_lits)]

    return MetamodelDiff(
        source=new.source,
        added_classes=added_classes,
        removed_classes=removed_classes,
        changed_generalizations=tuple(changed_generalizations),
        changed_abstractness=tuple(changed_abstractness),
        added_properties=tuple(added_properties),
        removed_properties=tuple(removed_properties),
        changed_properties=tuple(changed_properties),
        added_enums=added_enums,
        removed_enums=removed_enums,
        added_enum_literals=tuple(added_enum_literals),
        removed_enum_literals=tuple(removed_enum_literals),
    )


# --- the fail-fast review report ---------------------------------------------

#: A finding that BLOCKS (needs a human mapping decision) vs one that is informational.
REVIEW, INFO = "review", "info"


@dataclass(frozen=True)
class ReviewFinding:
    severity: str  # REVIEW | INFO
    kind: str
    message: str


def review_findings(
    diff: MetamodelDiff, composite_refs: frozenset[tuple[str, str]] = COMPOSITE_REFS
) -> list[ReviewFinding]:
    """Turn a diff into a review report. A REVIEW finding needs a human mapping
    decision before the new release is adopted; an INFO finding is recorded but
    safe. The central rule: a NEW STORED REFERENCE needs an explicit ownership policy
    -- it cascades on delete only if listed in `composite_refs` (the containment
    whitelist), which a new reference is NOT, so it is always flagged for a decision.
    """
    findings: list[ReviewFinding] = []

    def stored_reference_finding(class_name: str, prop: Property) -> ReviewFinding:
        has_policy = (class_name, prop.name) in composite_refs
        return ReviewFinding(
            REVIEW,
            "new-stored-reference",
            f"new STORED reference {class_name}.{prop.name} -> {prop.type or '?'}: "
            + (
                "listed in the ownership whitelist (composite/cascade)"
                if has_policy
                else "no ownership policy -- decide composite (cascade) vs non-composite"
            ),
        )

    for cls in diff.added_classes:
        findings.append(
            ReviewFinding(
                REVIEW,
                "new-class",
                f"new class {cls.name}"
                + (f" :> {', '.join(cls.generalizations)}" if cls.generalizations else "")
                + ": decide whether to seed/map it",
            )
        )
        for prop in cls.properties:
            if prop.stored_reference:
                findings.append(stored_reference_finding(cls.name, prop))

    for class_name, prop in diff.added_properties:
        if prop.stored_reference:
            findings.append(stored_reference_finding(class_name, prop))
        else:
            findings.append(
                ReviewFinding(
                    INFO,
                    "new-property",
                    f"new {prop.kind} {class_name}.{prop.name}"
                    + (" (derived, not stored)" if prop.derived else ""),
                )
            )

    for class_name, old_supers, new_supers in diff.changed_generalizations:
        findings.append(
            ReviewFinding(
                REVIEW,
                "generalization-change",
                f"{class_name}: supertypes {', '.join(old_supers) or '(none)'} -> "
                f"{', '.join(new_supers) or '(none)'} -- inheritance drives the "
                "generated shape and mapping assumptions",
            )
        )
    for class_name, _old, new_abstract in diff.changed_abstractness:
        findings.append(
            ReviewFinding(
                REVIEW,
                "abstractness-change",
                f"{class_name}: {'concrete -> abstract' if new_abstract else 'abstract -> concrete'}",
            )
        )

    for class_name in diff.removed_classes:
        findings.append(
            ReviewFinding(
                REVIEW, "removed-class", f"removed class {class_name}: a mapping may use it"
            )
        )
    for class_name, prop_name in diff.removed_properties:
        findings.append(
            ReviewFinding(
                REVIEW,
                "removed-property",
                f"removed property {class_name}.{prop_name}: a stored end may be dropped",
            )
        )
    for class_name, old, new in diff.changed_properties:
        if old.derived != new.derived:
            direction = "derived->STORED" if old.derived else "stored->derived"
            findings.append(
                ReviewFinding(
                    REVIEW,
                    "stored-derived-change",
                    f"{class_name}.{new.name}: {direction}"
                    + (
                        " -- a new stored end needs an ownership policy"
                        if not new.derived
                        else ""
                    ),
                )
            )
        if old.type != new.type or old.kind != new.kind:
            findings.append(
                ReviewFinding(
                    REVIEW,
                    "type-change",
                    f"{class_name}.{new.name}: type {old.kind}:{old.type or '?'} "
                    f"-> {new.kind}:{new.type or '?'}",
                )
            )

    for enum in diff.added_enums:
        findings.append(ReviewFinding(INFO, "new-enum", f"new enumeration {enum}"))
    for enum in diff.removed_enums:
        findings.append(
            ReviewFinding(REVIEW, "removed-enum", f"removed enumeration {enum}")
        )
    for enum, lit in diff.added_enum_literals:
        findings.append(
            ReviewFinding(INFO, "new-enum-literal", f"new literal {enum}::{lit}")
        )
    for enum, lit in diff.removed_enum_literals:
        findings.append(
            ReviewFinding(
                REVIEW, "removed-enum-literal", f"removed literal {enum}::{lit}"
            )
        )

    return findings


def has_review_findings(findings: list[ReviewFinding]) -> bool:
    """True if any finding needs a human mapping decision (the fail-fast trigger)."""
    return any(f.severity == REVIEW for f in findings)


# --- provenance / hash refresh -----------------------------------------------


def compute_manifest_rows(omg_dir: str | Path = OMG_DIR) -> list[tuple[str, str, int]]:
    """`(file name, SHA-256, byte size)` for each pinned artifact (XMI/KPAR), sorted.

    Refreshes the provenance hashes when bumping the pin; the maintainer pastes the
    result into the manifest table (`docs/sysml-v2/omg/<ver>/README.md`)."""
    rows: list[tuple[str, str, int]] = []
    for path in sorted(Path(omg_dir).iterdir()):
        if path.is_file() and path.suffix in (".xmi", ".kpar"):
            rows.append((path.name, _sha256(path), path.stat().st_size))
    return rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()


# --- baseline index files + poe entry points ---------------------------------


def _baseline_path(xmi_name: str) -> Path:
    return BASELINE_DIR / (xmi_name + ".index.json")


def write_baselines() -> list[Path]:
    """Regenerate the committed JSON baseline index for each pinned XMI (the
    `poe sysml2-spec-index` task: accept the current pinned XMIs as the baseline)."""
    BASELINE_DIR.mkdir(exist_ok=True)
    written: list[Path] = []
    for xmi_name in _INDEXED_XMI:
        path = _baseline_path(xmi_name)
        path.write_text(index_xmi(OMG_DIR / xmi_name).to_json(), encoding="utf-8")
        written.append(path)
    return written


def load_baseline(xmi_name: str) -> MetamodelIndex:
    return MetamodelIndex.from_json(_baseline_path(xmi_name).read_text(encoding="utf-8"))


def _cmd_index() -> int:
    for path in write_baselines():
        print(f"wrote {path}")
    return 0


def _cmd_diff() -> int:
    """Diff each committed baseline against the LIVE pinned XMI and print a review
    report; exit non-zero if any change needs a human mapping decision."""
    blocked = False
    for xmi_name in _INDEXED_XMI:
        diff = diff_indexes(load_baseline(xmi_name), index_xmi(OMG_DIR / xmi_name))
        findings = review_findings(diff)
        if diff.is_empty:
            print(f"{xmi_name}: no change from baseline")
            continue
        print(f"{xmi_name}: {len(findings)} finding(s)")
        for finding in findings:
            print(f"  [{finding.severity}] {finding.kind}: {finding.message}")
        blocked = blocked or has_review_findings(findings)
    if blocked:
        print("\nReview required before adopting the new release.", file=sys.stderr)
        return 1
    return 0


def _cmd_manifest() -> int:
    for name, sha, size in compute_manifest_rows():
        print(f"{name}\t{sha}\t{size}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("index", help="regenerate the committed baseline indexes")
    sub.add_parser("diff", help="diff the baseline against the live XMI (review report)")
    sub.add_parser("manifest", help="print refreshed artifact hashes")
    args = parser.parse_args(argv)
    return {"index": _cmd_index, "diff": _cmd_diff, "manifest": _cmd_manifest}[
        args.command
    ]()


if __name__ == "__main__":
    raise SystemExit(main())
