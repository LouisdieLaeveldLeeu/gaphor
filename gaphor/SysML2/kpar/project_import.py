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
- **Provenance, not read-only.** Every imported element and every unresolved
  reference traces to its KPAR, member, source declaration text, and line; but
  imported elements are ordinary editable model content.
- **Validation.** The mapped model is validated; callers (the CLI) refuse to
  persist a model with validation errors unless explicitly overridden.

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
class ElementImportProvenance:
    """Traces one imported element back to its source declaration."""

    qualified_name: str
    member: str  # archive entry the element was declared in
    line: int | None  # 1-based source line, when available
    declaration: str  # the source declaration text


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
    source: str  # qualified name of the referring usage
    member: str  # archive entry the reference was declared in
    line: int | None  # 1-based source line, when available
    declaration: str  # the source declaration text the reference came from


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
    external_dependencies: tuple[ExternalDependency, ...] = field(default_factory=tuple)
    element_provenance: dict[str, ElementImportProvenance] = field(default_factory=dict)
    # Diagnostics caused by THIS import (used to gate the import).
    validation_diagnostics: tuple = field(default_factory=tuple)
    # Diagnostics already present in the target factory before this import, kept
    # separate so a valid import is not blamed for pre-existing model problems.
    preexisting_diagnostics: tuple = field(default_factory=tuple)
    has_validation_errors: bool = False

    @property
    def imported_any(self) -> bool:
        return bool(self.imported_members)

    def provenance_of(self, element) -> ElementImportProvenance | None:
        return self.element_provenance.get(element.id)


def import_user_kpar(
    kpar_path: str | Path, factory: ElementFactory | None = None
) -> UserKparImport:
    """Import a user KPAR project into a Gaphor ElementFactory.

    Validates the archive (raising a
    :class:`~gaphor.SysML2.kpar.reader.KparError` subclass on a malformed one),
    parses each model member independently, imports the parseable ones into a
    single project namespace with project-wide type resolution, validates the
    result, and records per-element/per-reference provenance plus rejected
    members, unresolved references, and external-dependency diagnostics.
    """
    from gaphor.core.modeling import ElementFactory
    from gaphor.SysML2 import kerml_kernel as kk
    from gaphor.SysML2.grammar.parser import parse
    from gaphor.SysML2.mapping import map_project_members
    from gaphor.SysML2.validation import has_errors, validate

    archive = read_kpar(kpar_path)
    provenance = ProjectProvenance(
        kpar_path=Path(kpar_path),
        kpar_sha256=_sha256(Path(kpar_path)),
        project_name=archive.project.name,
    )

    named_packages: list = []
    member_lines: dict[str, list[str]] = {}
    imported_members: list[ImportedMember] = []
    rejected_members: list[RejectedMember] = []
    for model_file in archive.model_files:
        text = read_member_text(archive, model_file.member)
        try:
            package = parse(text)
        except SyntaxError as exc:
            rejected_members.append(RejectedMember(model_file.member, str(exc)))
            continue
        named_packages.append((model_file.member, package))
        member_lines[model_file.member] = text.splitlines()
        imported_members.append(
            ImportedMember(
                member=model_file.member,
                declared_names=tuple(member.name for member in package.members),
            )
        )

    factory = factory if factory is not None else ElementFactory()
    # Snapshot diagnostics already present in the target factory BEFORE building
    # this import, so a valid import into a model that already has problems is
    # not blamed for them (the GUI gates only on import-caused diagnostics).
    preexisting = list(validate(factory, {}, {}))
    preexisting_set = set(preexisting)

    result, node_provenance = map_project_members(named_packages, factory)

    def source_of(member, node) -> tuple[int | None, str]:
        line = getattr(node, "line", None)
        lines = member_lines.get(member, [])
        text = lines[line - 1].strip() if line and 0 < line <= len(lines) else ""
        return line, text

    def qualified_name(element) -> str:
        # The import root is unnamed, so kk.qualified_name yields a leading "::";
        # strip it so provenance reads "A::Engine", not "::A::Engine".
        if element is None:
            return ""
        name = kk.qualified_name(element)
        return name[2:] if name.startswith("::") else name

    element_provenance: dict[str, ElementImportProvenance] = {}
    for element_id, (member, node) in node_provenance.items():
        element = factory.lookup(element_id)
        line, declaration = source_of(member, node)
        element_provenance[element_id] = ElementImportProvenance(
            qualified_name=qualified_name(element),
            member=member,
            line=line,
            declaration=declaration,
        )

    def make_unresolved(usage_id, type_name, reason) -> UnresolvedTypeReference:
        member, node = node_provenance.get(usage_id, ("", None))
        line, declaration = source_of(member, node)
        return UnresolvedTypeReference(
            type_name=type_name,
            reason=reason,
            source=qualified_name(factory.lookup(usage_id)),
            member=member,
            line=line,
            declaration=declaration,
        )

    unresolved = [
        make_unresolved(usage_id, type_name, "unresolved")
        for usage_id, type_name in result.unresolved_types.items()
    ]
    unresolved.extend(
        make_unresolved(usage_id, type_name, f"wrong-kind: {kind}")
        for usage_id, (type_name, kind) in result.mistyped.items()
    )

    # Gate only on diagnostics this import introduced: whole-factory validation
    # minus what was already there. This still catches import-caused problems
    # (including a name that collides with pre-existing content, which is a new
    # diagnostic), while ignoring pre-existing-only errors.
    all_diagnostics = validate(factory, result.unresolved_types, result.mistyped)
    validation_diagnostics = tuple(
        d for d in all_diagnostics if d not in preexisting_set
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
        element_provenance=element_provenance,
        validation_diagnostics=validation_diagnostics,
        preexisting_diagnostics=tuple(preexisting),
        has_validation_errors=has_errors(validation_diagnostics),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
