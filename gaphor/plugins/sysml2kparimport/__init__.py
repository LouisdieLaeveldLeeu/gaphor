"""GUI service: import a user KPAR project from the Gaphor UI (Phase 3d).

Exposes the Phase 3c importer (:mod:`gaphor.SysML2.kpar.project_import`) through
the File -> Import menu. Importing adds the parseable content of a ``.kpar``
project to the *current* model as ordinary, editable, undoable Gaphor elements --
the same semantics as the ``sysml2-kpar-import`` CLI. Diagnostics (rejected
members, unresolved references, validation errors) are surfaced without losing
detail: a summary toast plus a details dialog. Validation errors require explicit
confirmation; otherwise the import is rolled back, mirroring the CLI's
refuse-by-default + ``--allow-invalid`` policy.

The import core (:meth:`SysML2KparImport.import_into_model`) is GTK-free and
unit-tested headless; the file chooser and dialogs are the thin GUI layer (only
they import ``gi``).
"""

from __future__ import annotations

from pathlib import Path

from gaphor.abc import ActionProvider, Service
from gaphor.core import action, gettext
from gaphor.event import Notification
from gaphor.SysML2.kpar.project_import import UserKparImport, import_user_kpar
from gaphor.SysML2.kpar.reader import KparError
from gaphor.transaction import Transaction


class SysML2KparImport(Service, ActionProvider):
    """Import a user KPAR project into the current model from the UI."""

    def __init__(
        self,
        event_manager,
        element_factory,
        import_menu=None,
        main_window=None,
    ):
        self.event_manager = event_manager
        self.element_factory = element_factory
        self.import_menu = import_menu
        self.main_window = main_window
        if import_menu:
            import_menu.add_actions(self)

    def shutdown(self):
        if self.import_menu:
            self.import_menu.remove_actions(self)

    # --- GTK-free import core (unit-tested headless) -------------------------

    def import_into_model(
        self, path: Path, allow_invalid: bool = False
    ) -> UserKparImport:
        """Import a KPAR into the current model within one transaction.

        Parseable members become editable model elements. The just-imported
        subtree is removed again (so nothing is added to the model) when either
        nothing parseable was imported -- matching the CLI's "no supported
        content" refusal, rather than leaving an empty root namespace behind --
        or the import has validation errors and ``allow_invalid`` is False. The
        returned result still carries the diagnostics. Raises a
        :class:`KparError` subclass for a malformed archive.

        The whole import is one transaction (so it is a single undoable step and
        the model browser updates). Removal unlinks the import's own root
        namespace, whose composite containment cascades to every imported
        element -- this does not depend on an undo manager being active, and only
        ever touches content from this import, never pre-existing model content.
        """
        with Transaction(self.event_manager):
            result = import_user_kpar(path, factory=self.element_factory)
            refuse = result.has_validation_errors and not allow_invalid
            if not result.imported_any or refuse:
                result.root.unlink()
        return result

    # --- GUI layer (file chooser + dialogs) ---------------------------------

    @action(
        name="file-import-kpar",
        label=gettext("Import KPAR Project…"),
        tooltip=gettext("Import a SysML v2 KPAR project into the current model"),
    )
    async def import_kpar_action(self):
        from gaphor.ui.filedialog import open_file_dialog

        parent = self.main_window.window if self.main_window else None
        path = await open_file_dialog(
            gettext("Import KPAR Project"),
            parent=parent,
            filters=[(gettext("KPAR Projects"), "*.kpar", "application/zip")],
            multiple=False,
        )
        if not path:
            return
        if isinstance(path, list):
            path = path[0]

        try:
            result = self.import_into_model(path)
        except KparError as exc:
            await self._alert(gettext("Could not import KPAR project"), str(exc))
            return

        if not result.imported_any:
            await self._alert(
                gettext("No supported content found"),
                diagnostics_detail(result)
                or gettext("The KPAR contains no importable SysML v2 content."),
            )
            return

        if result.has_validation_errors:
            if await self._confirm_import_with_errors(result):
                result = self.import_into_model(path, allow_invalid=True)
            else:
                self._notify(gettext("KPAR import cancelled"))
                return

        await self._report(result)

    async def _report(self, result: UserKparImport) -> None:
        summary = gettext(
            "Imported {imported} member(s); {skipped} skipped, "
            "{unresolved} unresolved reference(s)"
        ).format(
            imported=len(result.imported_members),
            skipped=len(result.rejected_members),
            unresolved=len(result.unresolved_references),
        )
        self._notify(summary)
        detail = diagnostics_detail(result)
        if detail:
            await self._alert(gettext("KPAR import diagnostics"), f"{summary}\n\n{detail}")

    def _notify(self, message: str) -> None:
        self.event_manager.handle(Notification(message))

    async def _confirm_import_with_errors(self, result: UserKparImport) -> bool:
        from gi.repository import Adw

        body = (
            gettext("The imported project has validation errors. Import anyway?")
            + "\n\n"
            + diagnostics_detail(result)
        )
        dialog = Adw.AlertDialog.new(gettext("Import with validation errors?"), body)
        dialog.add_response("cancel", gettext("Cancel"))
        dialog.add_response("import", gettext("Import Anyway"))
        dialog.set_response_appearance("import", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        parent = self.main_window.window if self.main_window else None
        return (await dialog.choose(parent)) == "import"

    async def _alert(self, heading: str, body: str) -> None:
        from gi.repository import Adw

        dialog = Adw.AlertDialog.new(heading, body)
        dialog.add_response("close", gettext("Close"))
        dialog.set_default_response("close")
        dialog.set_close_response("close")
        parent = self.main_window.window if self.main_window else None
        await dialog.choose(parent)


def diagnostics_detail(result: UserKparImport) -> str:
    """A human-readable, detail-preserving listing of import diagnostics."""
    lines: list[str] = []
    for rejected in result.rejected_members:
        lines.append(
            gettext("Skipped {member}: {message}").format(
                member=rejected.member, message=rejected.message
            )
        )
    for ref in result.unresolved_references:
        lines.append(
            gettext("Unresolved {type_name} in {member}:{line} ({reason})").format(
                type_name=ref.type_name,
                member=ref.member,
                line=ref.line,
                reason=ref.reason,
            )
        )
    for diagnostic in result.validation_diagnostics:
        lines.append(
            f"{diagnostic.severity}: {diagnostic.rule}: {diagnostic.message}"
        )
    for dep in result.external_dependencies:
        lines.append(
            gettext("External dependency not imported: {resource}").format(
                resource=dep.resource
            )
        )
    # Pre-existing model problems are shown separately: they are not caused by
    # this import and do not gate it.
    for diagnostic in result.preexisting_diagnostics:
        lines.append(
            gettext("Pre-existing: {severity}: {rule}: {message}").format(
                severity=diagnostic.severity,
                rule=diagnostic.rule,
                message=diagnostic.message,
            )
        )
    return "\n".join(lines)
