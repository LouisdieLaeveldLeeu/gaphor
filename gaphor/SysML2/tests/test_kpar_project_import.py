"""General user KPAR project import tests (completion-roadmap Phase 3c).

User KPAR import behaves like importing .sysml text: parseable members become
editable, persistable Gaphor model content; unparseable members are recorded;
type references resolve project-wide within the KPAR, and references outside it
stay unresolved (recorded). Exercised with synthetic user KPARs plus the
sysml2-kpar-import CLI.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from gaphor.SysML2 import cli, kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.kpar import import_user_kpar
from gaphor.SysML2.kpar.reader import KparNotAnArchiveError

ROOT_DIR = "MyProject"


def _write_user_kpar(path: Path, members: dict[str, str], usage=None) -> None:
    project = {"name": "My Project", "version": "1.0.0"}
    if usage is not None:
        project["usage"] = usage
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"{ROOT_DIR}/.project.json", json.dumps(project))
        zf.writestr(f"{ROOT_DIR}/.meta.json", json.dumps({"index": {}}))
        for name, text in members.items():
            zf.writestr(f"{ROOT_DIR}/{name}", text)


def test_imports_parseable_members_as_model_content(tmp_path):
    archive = tmp_path / "proj.kpar"
    _write_user_kpar(archive, {"Vehicles.sysml": "part def Engine;\npart e : Engine;"})

    result = import_user_kpar(archive)

    assert result.imported_any
    assert len(result.imported_members) == 1
    assert not result.rejected_members

    definitions = list(result.factory.select(sysml2.PartDefinition))
    usages = list(result.factory.select(sysml2.PartUsage))
    assert {d.declaredName for d in definitions} == {"Engine"}
    assert {u.declaredName for u in usages} == {"e"}
    # The usage is typed by the definition (resolution worked).
    assert kk.feature_type(usages[0]) is definitions[0]


def test_cross_file_resolution_within_project(tmp_path):
    # A reference in one member to a definition in another member of the SAME
    # project resolves (project-wide), proving map_project shares one namespace.
    archive = tmp_path / "proj.kpar"
    _write_user_kpar(
        archive,
        {
            "A.sysml": "package A { part def Engine; }",
            "B.sysml": "package B { part e : A::Engine; }",
        },
    )

    result = import_user_kpar(archive)

    assert len(result.imported_members) == 2
    assert not result.unresolved_references
    usage = next(iter(result.factory.select(sysml2.PartUsage)))
    typed = kk.feature_type(usage)
    assert isinstance(typed, sysml2.PartDefinition)
    assert typed.declaredName == "Engine"


def test_unsupported_member_is_recorded_not_dropped(tmp_path):
    archive = tmp_path / "proj.kpar"
    _write_user_kpar(
        archive,
        {
            "Good.sysml": "part def Engine;",
            "Bad.sysml": "this is not valid sysml @@@",
        },
    )

    result = import_user_kpar(archive)

    # The good member still imports; the bad one is recorded, not silently lost.
    assert {m.member for m in result.imported_members} == {f"{ROOT_DIR}/Good.sysml"}
    assert {m.member for m in result.rejected_members} == {f"{ROOT_DIR}/Bad.sysml"}
    assert result.rejected_members[0].message


def test_external_reference_is_unresolved_not_invented(tmp_path):
    # A reference to a library/external type (not in this KPAR) stays unresolved
    # and is recorded -- cross-library resolution is Phase 4.
    archive = tmp_path / "proj.kpar"
    _write_user_kpar(archive, {"C.sysml": "attribute x : Real;"})

    result = import_user_kpar(archive)

    assert "Real" in {ref.type_name for ref in result.unresolved_references}
    # No phantom type was invented for the unresolved reference.
    assert not list(result.factory.select(sysml2.AttributeDefinition))


def test_declared_names_recorded_per_member(tmp_path):
    archive = tmp_path / "proj.kpar"
    _write_user_kpar(archive, {"A.sysml": "package A { part def Engine; }"})

    result = import_user_kpar(archive)

    assert result.imported_members[0].declared_names == ("A",)


def test_declared_dependencies_recorded_as_diagnostics(tmp_path):
    # A user KPAR that declares a usage dependency surfaces it as an external
    # dependency (a dependency gap), since Phase 3c imports self-contained.
    archive = tmp_path / "proj.kpar"
    _write_user_kpar(
        archive,
        {"A.sysml": "part def Engine;"},
        usage=[
            {
                "resource": "https://www.omg.org/spec/KerML/20250201/Semantic-Library.kpar",
                "versionConstraint": "1.0.0",
            }
        ],
    )

    result = import_user_kpar(archive)

    resources = {dep.resource for dep in result.external_dependencies}
    assert "https://www.omg.org/spec/KerML/20250201/Semantic-Library.kpar" in resources


def test_provenance_traces_to_archive(tmp_path):
    import hashlib

    archive = tmp_path / "proj.kpar"
    _write_user_kpar(archive, {"A.sysml": "part def Engine;"})

    result = import_user_kpar(archive)

    assert result.provenance.kpar_path == archive
    assert result.provenance.project_name == "My Project"
    assert result.provenance.kpar_sha256 == hashlib.sha256(
        archive.read_bytes()
    ).hexdigest()


def test_malformed_archive_raises(tmp_path):
    bogus = tmp_path / "proj.kpar"
    bogus.write_text("not a zip", encoding="utf-8")
    with pytest.raises(KparNotAnArchiveError):
        import_user_kpar(bogus)


# --- CLI: sysml2-kpar-import ------------------------------------------------


def test_kpar_import_in_parser_names():
    assert "sysml2-kpar-import" in cli.parser_names()


def test_kpar_import_cli_saves_editable_model(tmp_path):
    archive = tmp_path / "proj.kpar"
    _write_user_kpar(archive, {"Vehicles.sysml": "part def Engine;\npart e : Engine;"})
    model = tmp_path / "out.gaphor"

    parser = cli.kpar_import_parser()
    args = parser.parse_args([str(archive), str(model)])
    assert args.command(args) == 0
    assert model.exists()

    # Reload the saved model: imported content persists as ordinary, editable
    # Gaphor model elements.
    import gaphor.storage as storage
    from gaphor.core.modeling import ElementFactory

    reloaded = ElementFactory()
    with open(model, encoding="utf-8") as f:
        storage.load(
            f, element_factory=reloaded, modeling_language=cli._modeling_language()
        )
    assert {d.declaredName for d in reloaded.select(sysml2.PartDefinition)} == {"Engine"}


def test_kpar_import_cli_reports_and_fails_when_nothing_imports(tmp_path, capsys):
    archive = tmp_path / "proj.kpar"
    _write_user_kpar(archive, {"Bad.sysml": "not valid @@@"})
    model = tmp_path / "out.gaphor"

    parser = cli.kpar_import_parser()
    args = parser.parse_args([str(archive), str(model)])
    assert args.command(args) == cli.ERROR_EXIT_CODE
    err = capsys.readouterr().err
    assert "skipped unsupported member" in err
    assert not model.exists()


def test_kpar_import_cli_reports_archive_error(tmp_path, capsys):
    bogus = tmp_path / "proj.kpar"
    bogus.write_text("not a zip", encoding="utf-8")
    model = tmp_path / "out.gaphor"

    parser = cli.kpar_import_parser()
    args = parser.parse_args([str(bogus), str(model)])
    assert args.command(args) == cli.ERROR_EXIT_CODE
    assert "kpar error" in capsys.readouterr().err
