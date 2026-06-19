"""Pinned OMG machine-readable artifact checks.

The human-maintained provenance manifest is the Markdown table in
``docs/sysml-v2/omg/20250201/README.md``. That file is the single source of
truth for which OMG artifacts are pinned and for their recorded byte sizes and
SHA-256 hashes. These tests parse that manifest and enforce it against the bytes
on disk:

- every manifest row points at a file that exists;
- the file's SHA-256 (and byte size, where the manifest records one) match;
- KPAR archives are readable ZIPs that contain their expected internal entries;
- XMI abstract-syntax rows match their recorded hashes (no size column).

The Python structures below hold ONLY expectations that the prose manifest does
not naturally express: the required internal entries of each KPAR archive and a
scalar-value-type smoke check. Sizes and hashes deliberately live only in the
manifest so it cannot drift away from what the tests enforce.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import ZipFile, is_zipfile

import pytest


ROOT = Path(__file__).resolve().parents[3]
OMG_DIR = ROOT / "docs/sysml-v2/omg/20250201"
MANIFEST = OMG_DIR / "README.md"


# Structural expectations the prose manifest does not capture: the internal
# entries each KPAR archive must contain. Sizes/hashes are NOT duplicated here;
# they are read from the manifest table.
KPAR_ENTRIES = {
    "Semantic-Library.kpar": {
        "Kernel Semantic Library/.project.json",
        "Kernel Semantic Library/.meta.json",
        "Kernel Semantic Library/KerML.kerml",
        "Kernel Semantic Library/Base.kerml",
    },
    "Data-Type-Library.kpar": {
        "Kernel Data Type Library/.project.json",
        "Kernel Data Type Library/.meta.json",
        "Kernel Data Type Library/ScalarValues.kerml",
    },
    "Function-Library.kpar": {
        "Kernel Function Library/.project.json",
        "Kernel Function Library/.meta.json",
        "Kernel Function Library/RealFunctions.kerml",
        "Kernel Function Library/StringFunctions.kerml",
    },
    "Systems-Library.kpar": {
        "Systems Library/.project.json",
        "Systems Library/.meta.json",
        "Systems Library/SysML.sysml",
        "Systems Library/Parts.sysml",
    },
    "Analysis-Domain-Library.kpar": {
        "Analysis/.project.json",
        "Analysis/.meta.json",
        "Analysis/AnalysisTooling.sysml",
    },
    "Cause-and-Effect-Domain-Library.kpar": {
        "Cause and Effect/.project.json",
        "Cause and Effect/.meta.json",
        "Cause and Effect/CauseAndEffect.sysml",
    },
    "Geometry-Domain-Library.kpar": {
        "Geometry/.project.json",
        "Geometry/.meta.json",
        "Geometry/SpatialItems.sysml",
    },
    "Metadata-Domain-Library.kpar": {
        "Metadata/.project.json",
        "Metadata/.meta.json",
        "Metadata/ModelingMetadata.sysml",
    },
    "Quantities-and-Units-Domain-Library.kpar": {
        "Quantities and Units/.project.json",
        "Quantities and Units/.meta.json",
        "Quantities and Units/SI.sysml",
        "Quantities and Units/Quantities.sysml",
    },
    "Requirement-Derivation-Domain-Library.kpar": {
        "Requirement Derivation/.project.json",
        "Requirement Derivation/.meta.json",
        "Requirement Derivation/RequirementDerivation.sysml",
    },
}

# XMI abstract-syntax artifacts the manifest must list (provenance + hashes live
# in the manifest; presence is asserted so the manifest cannot silently drop a
# generator input).
EXPECTED_XMI = {"KerML.xmi", "SysML.xmi"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clean(cell: str) -> str:
    """Strip Markdown table padding and inline-code backticks from a cell."""
    return cell.strip().strip("`").strip()


def _parse_markdown_tables(md_text: str) -> list[dict[str, str]]:
    """Return one dict per data row across every Markdown table in the text.

    A table is a header line, then a `---` separator line, then `|`-delimited
    data rows. Rows are keyed by the header cells.
    """
    rows: list[dict[str, str]] = []
    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        is_separator = bool(nxt) and "-" in nxt and set(nxt) <= set("|-: ")
        if line.startswith("|") and is_separator:
            headers = [_clean(c) for c in line.strip("|").split("|")]
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                cells = [_clean(c) for c in lines[j].strip().strip("|").split("|")]
                if len(cells) == len(headers):
                    rows.append(dict(zip(headers, cells)))
                j += 1
            i = j
        else:
            i += 1
    return rows


def _artifact_rows() -> list[dict[str, str]]:
    rows = _parse_markdown_tables(MANIFEST.read_text(encoding="utf-8"))
    return [r for r in rows if r.get("File", "").endswith((".kpar", ".xmi"))]


ARTIFACT_ROWS = _artifact_rows()


def test_manifest_and_structural_expectations_agree():
    """README is the provenance source; the Python expectations must track it.

    The manifest must list both XMI inputs and exactly the KPAR set whose
    internal entries we structurally check, so neither side can drift without a
    failure.
    """
    listed = {r["File"] for r in ARTIFACT_ROWS}
    listed_kpars = {f for f in listed if f.endswith(".kpar")}

    assert EXPECTED_XMI <= listed
    assert listed_kpars == set(KPAR_ENTRIES)


@pytest.mark.parametrize(
    "row", ARTIFACT_ROWS, ids=[r["File"] for r in ARTIFACT_ROWS]
)
def test_manifest_row_matches_pinned_file(row):
    """Every manifest row resolves to a file whose bytes match the manifest."""
    path = OMG_DIR / row["File"]

    assert path.exists(), f"manifest lists {row['File']} but the file is missing"
    assert _sha256(path) == row["SHA-256"]
    # The KPAR table records byte sizes; the XMI table does not.
    if row.get("Bytes"):
        assert path.stat().st_size == int(row["Bytes"])


@pytest.mark.parametrize("filename", sorted(KPAR_ENTRIES))
def test_pinned_kpar_is_valid_zip_with_entries(filename):
    path = OMG_DIR / filename

    assert is_zipfile(path)
    with ZipFile(path) as zf:
        assert zf.testzip() is None
        names = set(zf.namelist())

    assert KPAR_ENTRIES[filename] <= names


def test_data_type_library_contains_scalar_value_types():
    path = OMG_DIR / "Data-Type-Library.kpar"
    with ZipFile(path) as zf:
        scalar_values = zf.read(
            "Kernel Data Type Library/ScalarValues.kerml"
        ).decode("utf-8")

    for value_type in ("Boolean", "String", "Real", "Integer", "Natural"):
        assert f"datatype {value_type}" in scalar_values
