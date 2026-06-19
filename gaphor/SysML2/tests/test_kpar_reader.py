"""Read-only KPAR reader tests (completion-roadmap Phase 2).

Exercised against the pinned OMG KPAR artifacts under docs/sysml-v2/omg/20250201
plus synthetic archives for the failure diagnostics.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from gaphor.SysML2 import cli
from gaphor.SysML2.kpar import (
    KparLayoutError,
    KparMetadataError,
    KparNotAnArchiveError,
    KparNotFoundError,
    read_kpar,
)

ROOT = Path(__file__).resolve().parents[3]
OMG_DIR = ROOT / "docs/sysml-v2/omg/20250201"

DATA_TYPE = OMG_DIR / "Data-Type-Library.kpar"
SYSTEMS = OMG_DIR / "Systems-Library.kpar"


# --- Pinned-artifact inspection ---------------------------------------------


def test_reads_pinned_data_type_library():
    archive = read_kpar(DATA_TYPE)

    assert archive.root == "Kernel Data Type Library"
    assert archive.project.name == "Kernel Data Type Library"
    assert archive.project.version == "1.0.0"
    assert archive.meta.metamodel == "https://www.omg.org/spec/KerML/20250201"

    names = {model_file.name for model_file in archive.model_files}
    assert "ScalarValues.kerml" in names
    # Every file the .meta.json index points at is a discovered model file.
    assert set(archive.meta.index.values()) <= names


def test_data_type_library_declares_its_usage():
    archive = read_kpar(DATA_TYPE)
    resources = [usage.resource for usage in archive.project.usage]
    assert "https://www.omg.org/spec/KerML/20250201/Semantic-Library.kpar" in resources


def test_model_file_discovery_matches_zip_layout():
    archive = read_kpar(DATA_TYPE)
    with zipfile.ZipFile(DATA_TYPE) as zf:
        expected = sorted(
            name.split("/", 1)[1]
            for name in zf.namelist()
            if name.endswith((".kerml", ".sysml")) and not name.endswith("/")
        )
    assert [model_file.name for model_file in archive.model_files] == expected
    assert all(model_file.size > 0 for model_file in archive.model_files)


def test_systems_library_ignores_macosx_noise():
    # Systems-Library.kpar ships a __MACOSX/ cruft dir; it must be skipped, not
    # treated as a second project or a stray entry that fails the layout check.
    archive = read_kpar(SYSTEMS)

    assert archive.root == "Systems Library"
    assert archive.model_files
    assert all("__MACOSX" not in model_file.member for model_file in archive.model_files)


@pytest.mark.parametrize(
    "kpar", sorted(OMG_DIR.glob("*.kpar")), ids=lambda p: p.name
)
def test_all_pinned_kpars_inspect_without_error(kpar):
    archive = read_kpar(kpar)
    assert archive.project.name
    assert archive.model_files  # every pinned library ships model files


def test_inspection_is_deterministic():
    assert read_kpar(DATA_TYPE) == read_kpar(DATA_TYPE)


def test_meta_index_is_read_only():
    # The frozen result contract must hold for the nested index too: a caller
    # cannot mutate it.
    archive = read_kpar(DATA_TYPE)
    with pytest.raises(TypeError):
        archive.meta.index["Injected"] = "Injected.kerml"


# --- Diagnostics on malformed/unsupported archives --------------------------


def test_missing_path_raises_not_found(tmp_path):
    with pytest.raises(KparNotFoundError):
        read_kpar(tmp_path / "nope.kpar")


def test_non_zip_raises_not_an_archive(tmp_path):
    bogus = tmp_path / "plain.kpar"
    bogus.write_text("not a zip", encoding="utf-8")
    with pytest.raises(KparNotAnArchiveError):
        read_kpar(bogus)


def test_missing_project_descriptor_raises_layout(tmp_path):
    archive = tmp_path / "noproject.kpar"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("Lib/SomeModel.kerml", "datatype X;")
    with pytest.raises(KparLayoutError):
        read_kpar(archive)


def test_entries_outside_project_dir_raise_layout(tmp_path):
    archive = tmp_path / "stray.kpar"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("Lib/.project.json", json.dumps({"name": "Lib"}))
        zf.writestr("Lib/.meta.json", json.dumps({"index": {}}))
        zf.writestr("Other/Stray.kerml", "datatype X;")
    with pytest.raises(KparLayoutError):
        read_kpar(archive)


def test_multiple_projects_raise_layout(tmp_path):
    archive = tmp_path / "multi.kpar"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("A/.project.json", json.dumps({"name": "A"}))
        zf.writestr("A/.meta.json", json.dumps({"index": {}}))
        zf.writestr("B/.project.json", json.dumps({"name": "B"}))
        zf.writestr("B/.meta.json", json.dumps({"index": {}}))
    with pytest.raises(KparLayoutError):
        read_kpar(archive)


def test_malformed_project_json_raises_metadata(tmp_path):
    archive = tmp_path / "badjson.kpar"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("Lib/.project.json", "{ not valid json")
        zf.writestr("Lib/.meta.json", json.dumps({"index": {}}))
    with pytest.raises(KparMetadataError):
        read_kpar(archive)


def test_project_without_name_raises_metadata(tmp_path):
    archive = tmp_path / "noname.kpar"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("Lib/.project.json", json.dumps({"version": "1.0.0"}))
        zf.writestr("Lib/.meta.json", json.dumps({"index": {}}))
    with pytest.raises(KparMetadataError):
        read_kpar(archive)


def test_non_string_index_entry_raises_metadata(tmp_path):
    # A malformed index must fail loudly, not be silently coerced to strings.
    archive = tmp_path / "badindex.kpar"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("Lib/.project.json", json.dumps({"name": "Lib"}))
        zf.writestr("Lib/.meta.json", json.dumps({"index": {"X": 12}}))
    with pytest.raises(KparMetadataError):
        read_kpar(archive)


def test_missing_meta_raises_metadata(tmp_path):
    archive = tmp_path / "nometa.kpar"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("Lib/.project.json", json.dumps({"name": "Lib"}))
        zf.writestr("Lib/Model.kerml", "datatype X;")
    with pytest.raises(KparMetadataError):
        read_kpar(archive)


def test_synthetic_happy_path_tolerates_benign_noise(tmp_path):
    archive = tmp_path / "good.kpar"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(
            "Lib/.project.json",
            json.dumps(
                {
                    "name": "Lib",
                    "version": "1.2.3",
                    "description": "a library",
                    "usage": [{"resource": "X", "versionConstraint": "1.0.0"}],
                }
            ),
        )
        zf.writestr(
            "Lib/.meta.json",
            json.dumps(
                {
                    "index": {"X": "X.kerml"},
                    "created": "2025-01-01T00:00:00Z",
                    "metamodel": "mm",
                }
            ),
        )
        zf.writestr("Lib/X.kerml", "datatype X;")
        zf.writestr("Lib/.DS_Store", "noise")  # benign macOS noise, tolerated
        zf.writestr("__MACOSX/Lib/._X.kerml", "noise")  # benign zip noise, tolerated

    result = read_kpar(archive)
    assert result.project.version == "1.2.3"
    assert result.project.description == "a library"
    assert result.project.usage[0].resource == "X"
    assert result.project.usage[0].version_constraint == "1.0.0"
    assert [model_file.name for model_file in result.model_files] == ["X.kerml"]


# --- CLI: sysml2-kpar-info ---------------------------------------------------


def test_kpar_info_in_parser_names():
    assert "sysml2-kpar-info" in cli.parser_names()


def test_kpar_info_cli_reports_pinned_archive(capsys):
    parser = cli.kpar_info_parser()
    args = parser.parse_args([str(DATA_TYPE)])
    assert args.command(args) == 0

    out = capsys.readouterr().out
    assert "Kernel Data Type Library" in out
    assert "ScalarValues.kerml" in out


def test_kpar_info_cli_reports_error(tmp_path, capsys):
    bogus = tmp_path / "plain.kpar"
    bogus.write_text("not a zip", encoding="utf-8")
    parser = cli.kpar_info_parser()
    args = parser.parse_args([str(bogus)])
    assert args.command(args) == cli.ERROR_EXIT_CODE
    assert "kpar error" in capsys.readouterr().err
