"""Minimal normative-library KPAR import tests (completion-roadmap Phase 3b).

Verifies that the real KerML ScalarValues value types are imported from the
pinned Data-Type-Library.kpar as read-only kernel elements with provenance, that
value-type resolution queries are answered, that cross-library references are
recorded (not dropped), and that the import is closed-world over the pinned
artifacts and regenerated on load.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from gaphor.SysML2 import kerml
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.kpar import (
    LibraryImportError,
    KparNotFoundError,
    import_scalar_values_library,
)

ROOT = Path(__file__).resolve().parents[3]
OMG_DIR = ROOT / "docs/sysml-v2/omg/20250201"
DATA_TYPE = OMG_DIR / "Data-Type-Library.kpar"
MEMBER = "Kernel Data Type Library/ScalarValues.kerml"

# The roadmap's required value types plus the rest of the ScalarValues closure.
REQUIRED_VALUE_TYPES = ("Real", "String", "Boolean", "Integer", "Natural")
ALL_SCALAR_TYPES = (
    "ScalarValue",
    "Boolean",
    "String",
    "NumericalValue",
    "Number",
    "Complex",
    "Real",
    "Rational",
    "Integer",
    "Natural",
    "Positive",
)


def _member_text() -> str:
    with zipfile.ZipFile(DATA_TYPE) as zf:
        return zf.read(MEMBER).decode("utf-8")


def _sha256_of(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def library():
    return import_scalar_values_library()


def test_imports_required_value_types_as_kerml_datatypes(library):
    for name in REQUIRED_VALUE_TYPES:
        element = library.resolve(f"ScalarValues::{name}")
        assert isinstance(element, kerml.DataType), name
        assert element.declaredName == name


def test_imports_the_full_scalar_closure(library):
    for name in ALL_SCALAR_TYPES:
        assert isinstance(library.resolve(f"ScalarValues::{name}"), kerml.DataType)


def test_owning_package_is_imported(library):
    package = library.resolve("ScalarValues")
    assert isinstance(package, kerml.Package)
    assert package.declaredName == "ScalarValues"
    assert kk.qualified_name(package) == "ScalarValues"


def test_simple_and_qualified_names_both_resolve(library):
    assert library.resolve("Real") is library.resolve("ScalarValues::Real")


def test_unknown_name_does_not_resolve(library):
    assert library.resolve("ScalarValues::Nope") is None
    assert library.resolve("Imaginary") is None


def test_abstract_flag_matches_source(library):
    # The normative source marks these abstract; the concrete value types are not.
    assert library.resolve("ScalarValues::ScalarValue").isAbstract is True
    assert library.resolve("ScalarValues::NumericalValue").isAbstract is True
    assert library.resolve("ScalarValues::Number").isAbstract is True
    assert library.resolve("ScalarValues::Real").isAbstract is False
    assert library.resolve("ScalarValues::Integer").isAbstract is False


def test_intra_library_specialization_chain(library):
    # Real :> Complex; Integer :> Rational -- real specialization edges, resolved
    # to the imported kernel elements (not strings).
    real = library.resolve("ScalarValues::Real")
    complex_ = library.resolve("ScalarValues::Complex")
    assert complex_ in library.supertypes(real)

    integer = library.resolve("ScalarValues::Integer")
    rational = library.resolve("ScalarValues::Rational")
    assert rational in library.supertypes(integer)


def test_cross_library_super_is_recorded_not_dropped(library):
    # ScalarValue specializes Base::DataValue, which is outside the minimal
    # closure; it must be an explicit unresolved record, and no Specialization to
    # a missing element may be created.
    targets = {(u.source, u.target) for u in library.unresolved}
    assert ("ScalarValues::ScalarValue", "DataValue") in targets

    scalar_value = library.resolve("ScalarValues::ScalarValue")
    # Its only specialization target is unresolved, so it has no resolved supers.
    assert library.supertypes(scalar_value) == ()


def test_unresolved_reference_carries_full_provenance(library):
    ref = next(
        u
        for u in library.unresolved
        if u.source == "ScalarValues::ScalarValue" and u.target == "DataValue"
    )
    assert ref.kpar_path == DATA_TYPE
    assert ref.member == MEMBER
    assert ref.line > 0
    assert ref.declaration in _member_text()
    assert ref.kpar_sha256 == _sha256_of(DATA_TYPE)


def test_scalar_values_member_fully_parsed_no_unsupported(library):
    # The whole ScalarValues package is within the supported subset, so nothing
    # is recorded as unsupported.
    assert library.unsupported == ()


def test_every_element_and_relationship_traces_to_pinned_source(library):
    member_text = _member_text()
    # Relationships (Specializations) are imported elements too and must carry
    # provenance, not just the package and datatypes.
    assert library.relationships
    for element in (*library.elements, *library.relationships):
        prov = library.provenance_of(element)
        assert prov is not None
        assert prov.kpar_path == DATA_TYPE
        assert prov.member == MEMBER
        assert prov.line > 0
        # No hand-authored stubs: the recorded declaration really appears in the
        # pinned member's bytes.
        assert prov.declaration in member_text


def test_provenance_sha_matches_pinned_artifact(library):
    real = library.resolve("ScalarValues::Real")
    assert library.provenance_of(real).kpar_sha256 == _sha256_of(DATA_TYPE)


def test_usage_dependencies_resolve_to_pinned_artifacts(library):
    # Data-Type-Library declares a usage dependency on Semantic-Library; it must
    # be resolved (closed-world) to the pinned artifact.
    resolved = {dep.filename for dep in library.dependencies}
    assert "Semantic-Library.kpar" in resolved
    for dep in library.dependencies:
        assert dep.path == OMG_DIR / dep.filename
        assert dep.path.is_file()


def test_missing_usage_dependency_fails(tmp_path):
    # A pinned set containing Data-Type-Library.kpar but NOT its declared
    # Semantic-Library.kpar dependency must fail the import, not silently succeed.
    import shutil

    shutil.copy(DATA_TYPE, tmp_path / "Data-Type-Library.kpar")
    with pytest.raises(LibraryImportError):
        import_scalar_values_library(omg_dir=tmp_path)


def test_bogus_dependency_artifact_is_rejected(tmp_path):
    # A file named like the dependency but that is not a readable KPAR must be
    # rejected: "resolved" means a real pinned KPAR, not just a matching name.
    import shutil

    shutil.copy(DATA_TYPE, tmp_path / "Data-Type-Library.kpar")
    (tmp_path / "Semantic-Library.kpar").write_text("not a zip", encoding="utf-8")
    with pytest.raises(LibraryImportError):
        import_scalar_values_library(omg_dir=tmp_path)


def _write_kpar(path, root, project, members):
    import json

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"{root}/.project.json", json.dumps(project))
        zf.writestr(f"{root}/.meta.json", json.dumps({"index": {}}))
        for name, text in members.items():
            zf.writestr(f"{root}/{name}", text)


def test_exact_version_mismatch_is_rejected(tmp_path):
    # When the usage constraint is an exact version, a pinned dependency whose
    # project version differs must fail the import.
    _write_kpar(
        tmp_path / "Data-Type-Library.kpar",
        "Kernel Data Type Library",
        {
            "name": "Kernel Data Type Library",
            "version": "1.0.0",
            "usage": [
                {
                    "resource": "https://example.org/MyDep.kpar",
                    "versionConstraint": "9.9.9",
                }
            ],
        },
        {"ScalarValues.kerml": "standard library package ScalarValues {\n\tdatatype Boolean;\n}"},
    )
    _write_kpar(
        tmp_path / "MyDep.kpar",
        "Dep",
        {"name": "Dep", "version": "1.0.0"},
        {"D.kerml": "standard library package Dep {\n}"},
    )
    with pytest.raises(LibraryImportError):
        import_scalar_values_library(omg_dir=tmp_path)


def test_resolved_dependency_records_pinned_version(library):
    semantic = next(
        dep for dep in library.dependencies if dep.filename == "Semantic-Library.kpar"
    )
    assert semantic.version_constraint == "1.0.0"
    assert semantic.version == "1.0.0"


def test_import_is_regenerated_on_load():
    # Two imports yield equivalent content in independent factories (read-only,
    # regenerated-on-load): same qualified names, fresh element instances.
    first = import_scalar_values_library()
    second = import_scalar_values_library()
    assert first.qualified_names == second.qualified_names
    assert first.resolve("ScalarValues::Real") is not second.resolve(
        "ScalarValues::Real"
    )


def test_closed_world_missing_artifact_raises(tmp_path):
    # Pointed at a directory without the pinned KPAR, the importer fails loudly
    # rather than fetching anything.
    with pytest.raises(KparNotFoundError):
        import_scalar_values_library(omg_dir=tmp_path)


def test_missing_member_raises_library_import_error(tmp_path):
    # A Data-Type-Library.kpar that lacks ScalarValues.kerml fails with a clear
    # library-import error, not a wrong-but-silent result.
    fake = tmp_path / "Data-Type-Library.kpar"
    with zipfile.ZipFile(fake, "w") as zf:
        zf.writestr("Kernel Data Type Library/.project.json", '{"name": "X"}')
        zf.writestr("Kernel Data Type Library/.meta.json", '{"index": {}}')
        zf.writestr("Kernel Data Type Library/Other.kerml", "package Other {}")
    with pytest.raises(LibraryImportError):
        import_scalar_values_library(omg_dir=tmp_path)
