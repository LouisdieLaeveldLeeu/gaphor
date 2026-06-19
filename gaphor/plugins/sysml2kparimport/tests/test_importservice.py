"""GUI KPAR import service tests (completion-roadmap Phase 3d).

The file chooser and dialogs are GTK and not unit-tested here; the import core
(`import_into_model`) is GTK-free and fully tested headless, including the
confirm-or-cancel (transaction rollback) semantics and action/menu registration.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from gaphor.plugins.sysml2kparimport import SysML2KparImport, diagnostics_detail
from gaphor.SysML2 import sysml2
from gaphor.SysML2.kpar.reader import KparNotAnArchiveError
from gaphor.ui.menufragment import MenuFragment

ROOT_DIR = "MyProject"


def _write_user_kpar(path: Path, members: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            f"{ROOT_DIR}/.project.json",
            json.dumps({"name": "My Project", "version": "1.0.0"}),
        )
        zf.writestr(f"{ROOT_DIR}/.meta.json", json.dumps({"index": {}}))
        for name, text in members.items():
            zf.writestr(f"{ROOT_DIR}/{name}", text)
    return path


@pytest.fixture
def service(event_manager, element_factory):
    return SysML2KparImport(event_manager, element_factory)


def test_valid_kpar_imports_into_current_model(service, element_factory, tmp_path):
    archive = _write_user_kpar(
        tmp_path / "p.kpar", {"V.sysml": "part def Engine;\npart e : Engine;"}
    )

    result = service.import_into_model(archive)

    assert not result.has_validation_errors
    assert {d.declaredName for d in element_factory.select(sysml2.PartDefinition)} == {
        "Engine"
    }


def test_validation_errors_are_refused_by_default(service, element_factory, tmp_path):
    # A duplicate `part def Engine` across members is a validation error; without
    # allow_invalid the imported subtree is removed so nothing is added.
    archive = _write_user_kpar(
        tmp_path / "p.kpar",
        {"A.sysml": "part def Engine;", "B.sysml": "part def Engine;"},
    )

    result = service.import_into_model(archive, allow_invalid=False)

    assert result.has_validation_errors
    assert not list(element_factory.select(sysml2.PartDefinition))


def test_refusal_leaves_existing_model_content_intact(service, element_factory, tmp_path):
    # Pre-existing content must survive a refused import (only this import's
    # subtree is removed).
    keep = _write_user_kpar(tmp_path / "keep.kpar", {"K.sysml": "part def Keep;"})
    service.import_into_model(keep)
    assert {d.declaredName for d in element_factory.select(sysml2.PartDefinition)} == {
        "Keep"
    }

    bad = _write_user_kpar(
        tmp_path / "bad.kpar",
        {"A.sysml": "part def Dup;", "B.sysml": "part def Dup;"},
    )
    service.import_into_model(bad, allow_invalid=False)

    # The refused import is gone; the earlier import remains.
    assert {d.declaredName for d in element_factory.select(sysml2.PartDefinition)} == {
        "Keep"
    }


def test_allow_invalid_commits_despite_errors(service, element_factory, tmp_path):
    archive = _write_user_kpar(
        tmp_path / "p.kpar",
        {"A.sysml": "part def Engine;", "B.sysml": "part def Engine;"},
    )

    result = service.import_into_model(archive, allow_invalid=True)

    assert result.has_validation_errors
    assert len(list(element_factory.select(sysml2.PartDefinition))) == 2


def test_malformed_archive_raises(service, tmp_path):
    bogus = tmp_path / "p.kpar"
    bogus.write_text("not a zip", encoding="utf-8")
    with pytest.raises(KparNotAnArchiveError):
        service.import_into_model(bogus)


def test_action_is_registered_and_added_to_import_menu(event_manager, element_factory):
    from gaphor.abc import ActionProvider
    from gaphor.ui.actiongroup import iter_actions

    fragment = MenuFragment()
    service = SysML2KparImport(event_manager, element_factory, import_menu=fragment)

    assert isinstance(service, ActionProvider)
    names = {action.name for _name, action in iter_actions(service, "win")}
    assert "file-import-kpar" in names
    # The action was contributed to the File -> Import menu fragment.
    assert fragment.menu.get_n_items() >= 1


def test_diagnostics_detail_lists_every_category(service, tmp_path):
    archive = _write_user_kpar(
        tmp_path / "p.kpar",
        {
            "Good.sysml": "part def Engine;\npart e : Missing;",
            "Bad.sysml": "garbage @@@",
        },
    )

    detail = diagnostics_detail(service.import_into_model(archive, allow_invalid=True))

    assert "Bad.sysml" in detail  # rejected member
    assert "Missing" in detail  # unresolved reference
