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
    # A reference to a type that is neither in this KPAR nor a standard-library
    # value type stays unresolved and is recorded (not invented). (Standard
    # library value types like Real now resolve -- see Phase 4.)
    archive = tmp_path / "proj.kpar"
    _write_user_kpar(archive, {"C.sysml": "attribute x : NotALibraryType;"})

    result = import_user_kpar(archive)

    assert "NotALibraryType" in {ref.type_name for ref in result.unresolved_references}
    # No phantom type was invented for the unresolved reference.
    assert not list(result.factory.select(sysml2.AttributeDefinition))


def test_unresolved_reference_carries_provenance(tmp_path):
    archive = tmp_path / "proj.kpar"
    _write_user_kpar(archive, {"C.sysml": "part def Engine;\npart e : Missing;"})

    result = import_user_kpar(archive)

    ref = next(r for r in result.unresolved_references if r.type_name == "Missing")
    assert ref.source == "e"
    assert ref.member == f"{ROOT_DIR}/C.sysml"
    assert ref.line == 2
    assert ref.declaration == "part e : Missing;"


def test_broken_connection_endpoint_carries_provenance(tmp_path):
    # A connector endpoint is a reference too: a broken end gets the same
    # provenance-rich unresolved-reference record as a type reference.
    archive = tmp_path / "proj.kpar"
    _write_user_kpar(
        archive, {"C.sysml": "part a;\nconnection c connect a to missing;"}
    )

    result = import_user_kpar(archive)

    ref = next(r for r in result.unresolved_references if r.type_name == "missing")
    assert ref.reason == "unresolved-endpoint"
    assert ref.source == "c"
    assert ref.member == f"{ROOT_DIR}/C.sysml"
    assert ref.line == 2
    assert ref.declaration == "connection c connect a to missing;"


def test_broken_frame_reference_is_recorded_and_gated(tmp_path):
    # A framed-concern reference (`frame <existing>`) that does not resolve to a
    # ConcernUsage is an unresolved reference too (Phase 6d-2): it must be recorded
    # with provenance AND gate the import, not pass clean.
    archive = tmp_path / "proj.kpar"
    _write_user_kpar(archive, {"R.sysml": "requirement def R { frame missing; }"})

    result = import_user_kpar(archive)

    ref = next(r for r in result.unresolved_references if r.type_name == "missing")
    assert ref.reason == "unresolved-frame-reference"
    assert ref.member == f"{ROOT_DIR}/R.sysml"
    assert ref.line == 1
    assert any(
        d.rule == "broken-frame-reference" for d in result.validation_diagnostics
    )


def test_imported_elements_carry_per_element_provenance(tmp_path):
    archive = tmp_path / "proj.kpar"
    _write_user_kpar(archive, {"V.sysml": "part def Engine;\npart e : Engine;"})

    result = import_user_kpar(archive)

    by_qname = {
        p.qualified_name: p for p in result.element_provenance.values()
    }
    assert by_qname["Engine"].member == f"{ROOT_DIR}/V.sysml"
    assert by_qname["Engine"].line == 1
    assert by_qname["Engine"].declaration == "part def Engine;"
    assert by_qname["e"].line == 2
    assert by_qname["e"].declaration == "part e : Engine;"


def test_resolved_typing_relationship_carries_provenance(tmp_path):
    archive = tmp_path / "proj.kpar"
    _write_user_kpar(archive, {"V.sysml": "part def Engine;\npart e : Engine;"})

    result = import_user_kpar(archive)

    typing = next(iter(result.factory.select(kerml.FeatureTyping)))
    prov = result.provenance_of(typing)
    assert prov is not None
    assert prov.member == f"{ROOT_DIR}/V.sysml"
    assert prov.line == 2
    assert prov.declaration == "part e : Engine;"


def test_nested_elements_carry_provenance(tmp_path):
    archive = tmp_path / "proj.kpar"
    _write_user_kpar(
        archive,
        {"V.sysml": "package A {\n  part def Engine;\n}"},
    )

    result = import_user_kpar(archive)

    engine = next(
        e for e in result.factory.select(sysml2.PartDefinition)
        if e.declaredName == "Engine"
    )
    prov = result.provenance_of(engine)
    assert prov is not None
    assert prov.qualified_name == "A::Engine"
    assert prov.member == f"{ROOT_DIR}/V.sysml"
    assert prov.line == 2


def test_duplicate_elements_distinguished_by_provenance(tmp_path):
    # Two members each declare `part def Engine`; both are imported and their
    # provenance distinguishes them by source member.
    archive = tmp_path / "proj.kpar"
    _write_user_kpar(
        archive,
        {"A.sysml": "part def Engine;", "B.sysml": "part def Engine;"},
    )

    result = import_user_kpar(archive)

    engines = [
        e for e in result.factory.select(sysml2.PartDefinition)
        if e.declaredName == "Engine"
    ]
    assert len(engines) == 2
    members = {result.provenance_of(e).member for e in engines}
    assert members == {f"{ROOT_DIR}/A.sysml", f"{ROOT_DIR}/B.sysml"}


def test_validation_gates_only_on_import_caused_diagnostics(element_factory, tmp_path):
    # Importing valid content into a factory that already has a validation error
    # must not be blamed for the pre-existing error.
    bad = tmp_path / "bad.kpar"
    _write_user_kpar(bad, {"A.sysml": "part def Dup;", "B.sysml": "part def Dup;"})
    import_user_kpar(bad, factory=element_factory)  # leaves a duplicate-name error

    good = tmp_path / "good.kpar"
    _write_user_kpar(good, {"V.sysml": "part def Valid;"})
    result = import_user_kpar(good, factory=element_factory)

    assert not result.has_validation_errors
    assert not result.validation_diagnostics
    assert result.preexisting_diagnostics  # the duplicate is recorded separately


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


def test_kpar_import_cli_refuses_validation_errors(tmp_path, capsys):
    # Two members both declaring `part def Engine` produce a duplicate-name
    # validation error; the CLI must refuse to save by default (like
    # sysml2-import), not exit 0 with a written model.
    archive = tmp_path / "proj.kpar"
    _write_user_kpar(
        archive,
        {"A.sysml": "part def Engine;", "B.sysml": "part def Engine;"},
    )
    model = tmp_path / "out.gaphor"

    parser = cli.kpar_import_parser()
    args = parser.parse_args([str(archive), str(model)])
    assert args.command(args) == cli.ERROR_EXIT_CODE
    assert "import refused" in capsys.readouterr().err
    assert not model.exists()


def test_kpar_import_cli_allow_invalid_overrides(tmp_path):
    archive = tmp_path / "proj.kpar"
    _write_user_kpar(
        archive,
        {"A.sysml": "part def Engine;", "B.sysml": "part def Engine;"},
    )
    model = tmp_path / "out.gaphor"

    parser = cli.kpar_import_parser()
    args = parser.parse_args([str(archive), str(model), "--allow-invalid"])
    assert args.command(args) == 0
    assert model.exists()


def test_kpar_import_cli_reports_archive_error(tmp_path, capsys):
    bogus = tmp_path / "proj.kpar"
    bogus.write_text("not a zip", encoding="utf-8")
    model = tmp_path / "out.gaphor"

    parser = cli.kpar_import_parser()
    args = parser.parse_args([str(bogus), str(model)])
    assert args.command(args) == cli.ERROR_EXIT_CODE
    assert "kpar error" in capsys.readouterr().err
