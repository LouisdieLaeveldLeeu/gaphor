"""General user KPAR project import (completion-roadmap Phase 3c).

Imports a *user* KPAR project (as opposed to the read-only normative libraries of
Phase 3b) through the existing SysML2 text pipeline, per the decisions ratified
at the Phase 3c review gate:

- **Editable, persisted content.** Imported content becomes normal Gaphor model
  elements in the target ElementFactory -- editable and savable into `.gaphor`,
  exactly like importing a `.sysml` text file. (Normative libraries stay
  read-only and regenerated; user imports do not.)
- **Per-member partial import.** Each model member is parsed independently: a
  member that parses is imported; a member that does not is recorded as a
  rejected member with its parse error. One unsupported member never blocks the
  rest, and nothing is silently dropped.
- **Self-contained resolution.** Type references resolve project-wide against the
  members imported from the *same* KPAR. References to normative libraries,
  external dependencies, or unimported members stay unresolved and are recorded
  (cross-library resolution into the Phase 3b library is Phase 4).
- **Provenance, not read-only.** The result carries provenance/diagnostics, but
  imported elements are ordinary editable model content.

Entry surface: this Python API plus the `sysml2-kpar-import` CLI command.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from gaphor.SysML2.kpar.reader import read_kpar, read_member_text

if TYPE_CHECKING:
    from gaphor.core.modeling import ElementFactory
    from gaphor.SysML2 import kerml


@dataclass(frozen=True)
class ProjectProvenance:
    """Where an imported project came from."""

    kpar_path: Path
    kpar_sha256: str
    project_name: str


@dataclass(frozen=True)
class ImportedMember:
    """A model member that parsed and was imported."""

    member: str  # archive entry, e.g. "MyProject/Vehicles.sysml"
    declared_names: tuple[str, ...]  # top-level names declared in the member


@dataclass(frozen=True)
class RejectedMember:
    """A model member that could not be parsed; recorded, never silently dropped."""

    member: str
    message: str


@dataclass(frozen=True)
class UnresolvedTypeReference:
    """A type reference that did not resolve within the imported project."""

    type_name: str
    reason: str  # "unresolved" or "wrong-kind: <ResolvedKind>"


@dataclass(frozen=True)
class ExternalDependency:
    """A `.project.json` `usage` dependency on content outside this project.

    Recorded as a diagnostic (a dependency gap): Phase 3c imports self-contained
    project content, so declared dependencies on normative libraries or other
    KPARs are not resolved/imported here (that is Phase 4 / later).
    """

    resource: str
    version_constraint: str | None


@dataclass
class UserKparImport:
    """The result of importing a user KPAR project."""

    factory: ElementFactory
    root: kerml.Namespace
    provenance: ProjectProvenance
    imported_members: tuple[ImportedMember, ...]
    rejected_members: tuple[RejectedMember, ...] = field(default_factory=tuple)
    unresolved_references: tuple[UnresolvedTypeReference, ...] = field(
        default_factory=tuple
    )
    external_dependencies: tuple[ExternalDependency, ...] = field(
        default_factory=tuple
    )

    @property
    def imported_any(self) -> bool:
        return bool(self.imported_members)


def import_user_kpar(
    kpar_path: str | Path, factory: ElementFactory | None = None
) -> UserKparImport:
    """Import a user KPAR project into a Gaphor ElementFactory.

    Validates the archive (raising a
    :class:`~gaphor.SysML2.kpar.reader.KparError` subclass on a malformed one),
    then parses each model member independently, imports the parseable ones into
    a single project namespace with project-wide type resolution, and records
    rejected members and unresolved references.
    """
    from gaphor.core.modeling import ElementFactory
    from gaphor.SysML2.grammar.parser import parse
    from gaphor.SysML2.mapping import map_project

    archive = read_kpar(kpar_path)
    provenance = ProjectProvenance(
        kpar_path=Path(kpar_path),
        kpar_sha256=_sha256(Path(kpar_path)),
        project_name=archive.project.name,
    )

    parsed: list = []
    imported_members: list[ImportedMember] = []
    rejected_members: list[RejectedMember] = []
    for model_file in archive.model_files:
        text = read_member_text(archive, model_file.member)
        try:
            package = parse(text)
        except SyntaxError as exc:
            rejected_members.append(RejectedMember(model_file.member, str(exc)))
            continue
        parsed.append(package)
        imported_members.append(
            ImportedMember(
                member=model_file.member,
                declared_names=tuple(member.name for member in package.members),
            )
        )

    factory = factory if factory is not None else ElementFactory()
    result = map_project(parsed, factory)

    unresolved = [
        UnresolvedTypeReference(type_name=name, reason="unresolved")
        for name in result.unresolved_types.values()
    ]
    unresolved.extend(
        UnresolvedTypeReference(type_name=name, reason=f"wrong-kind: {kind}")
        for name, kind in result.mistyped.values()
    )

    external_dependencies = tuple(
        ExternalDependency(usage.resource, usage.version_constraint)
        for usage in archive.project.usage
    )

    return UserKparImport(
        factory=factory,
        root=result.root,
        provenance=provenance,
        imported_members=tuple(imported_members),
        rejected_members=tuple(rejected_members),
        unresolved_references=tuple(unresolved),
        external_dependencies=external_dependencies,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
