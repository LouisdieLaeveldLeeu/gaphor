"""Pinned OMG machine-readable artifact checks."""

from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import ZipFile, is_zipfile

import pytest


ROOT = Path(__file__).resolve().parents[3]
OMG_DIR = ROOT / "docs/sysml-v2/omg/20250201"

KPAR_ARTIFACTS = {
    "Semantic-Library.kpar": {
        "size": 33031,
        "sha256": "6d9e311646a557cb08b64313cab6a7931109751b2ac7fbfcefad5c2216a6167b",
        "entries": {
            "Kernel Semantic Library/.project.json",
            "Kernel Semantic Library/.meta.json",
            "Kernel Semantic Library/KerML.kerml",
            "Kernel Semantic Library/Base.kerml",
        },
    },
    "Data-Type-Library.kpar": {
        "size": 4260,
        "sha256": "957e4ff5c60f7fc5eedaf0b6d4f776856061c0aa7a424e260eeccb8d6ed7bfbd",
        "entries": {
            "Kernel Data Type Library/.project.json",
            "Kernel Data Type Library/.meta.json",
            "Kernel Data Type Library/ScalarValues.kerml",
        },
    },
    "Function-Library.kpar": {
        "size": 15929,
        "sha256": "a8319da3ab1d8ffc0f390ea1aef29d85a00451655c41a9267ce396845c2b1c8d",
        "entries": {
            "Kernel Function Library/.project.json",
            "Kernel Function Library/.meta.json",
            "Kernel Function Library/RealFunctions.kerml",
            "Kernel Function Library/StringFunctions.kerml",
        },
    },
    "Systems-Library.kpar": {
        "size": 27577,
        "sha256": "df7d8b2c6e08232ca7ce123a63148949c383fcbeaeba8d89c27ceece43793a1f",
        "entries": {
            "Systems Library/.project.json",
            "Systems Library/.meta.json",
            "Systems Library/SysML.sysml",
            "Systems Library/Parts.sysml",
        },
    },
    "Analysis-Domain-Library.kpar": {
        "size": 6035,
        "sha256": "96f0230cd7091faa2d27345b7f7748e0249fb42cfbdc48265ce6e82d6ecc1b38",
        "entries": {
            "Analysis/.project.json",
            "Analysis/.meta.json",
            "Analysis/AnalysisTooling.sysml",
        },
    },
    "Cause-and-Effect-Domain-Library.kpar": {
        "size": 3135,
        "sha256": "c097c70232b8c9d38acbc92b402d8caa3b67f4d847dade0f29994164a4e25e94",
        "entries": {
            "Cause and Effect/.project.json",
            "Cause and Effect/.meta.json",
            "Cause and Effect/CauseAndEffect.sysml",
        },
    },
    "Geometry-Domain-Library.kpar": {
        "size": 7169,
        "sha256": "9cc40d628dfe8717b79af74297a7115103e3469708a54221cac0e42344ed8427",
        "entries": {
            "Geometry/.project.json",
            "Geometry/.meta.json",
            "Geometry/SpatialItems.sysml",
        },
    },
    "Metadata-Domain-Library.kpar": {
        "size": 4573,
        "sha256": "5c51cd3b21b60c89742dbba0f59f25bdbc34224d05e32975d77bb93092458b9b",
        "entries": {
            "Metadata/.project.json",
            "Metadata/.meta.json",
            "Metadata/ModelingMetadata.sysml",
        },
    },
    "Quantities-and-Units-Domain-Library.kpar": {
        "size": 154748,
        "sha256": "81a6e7264a9f287e482ec5b35f8ef98725b81f393e0b2e82dae3599511c0adc7",
        "entries": {
            "Quantities and Units/.project.json",
            "Quantities and Units/.meta.json",
            "Quantities and Units/SI.sysml",
            "Quantities and Units/Quantities.sysml",
        },
    },
    "Requirement-Derivation-Domain-Library.kpar": {
        "size": 2650,
        "sha256": "a136e72ac6afbd96ede220cfec77fd54c75242d577d3f5ab9e5278b25baee6e5",
        "entries": {
            "Requirement Derivation/.project.json",
            "Requirement Derivation/.meta.json",
            "Requirement Derivation/RequirementDerivation.sysml",
        },
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@pytest.mark.parametrize("filename", sorted(KPAR_ARTIFACTS))
def test_pinned_kpar_artifact_matches_manifest(filename):
    expected = KPAR_ARTIFACTS[filename]
    path = OMG_DIR / filename

    assert path.exists()
    assert path.stat().st_size == expected["size"]
    assert _sha256(path) == expected["sha256"]
    assert is_zipfile(path)

    with ZipFile(path) as zf:
        assert zf.testzip() is None
        names = set(zf.namelist())

    assert expected["entries"] <= names


def test_data_type_library_contains_scalar_value_types():
    path = OMG_DIR / "Data-Type-Library.kpar"
    with ZipFile(path) as zf:
        scalar_values = zf.read(
            "Kernel Data Type Library/ScalarValues.kerml"
        ).decode("utf-8")

    for value_type in ("Boolean", "String", "Real", "Integer", "Natural"):
        assert f"datatype {value_type}" in scalar_values
