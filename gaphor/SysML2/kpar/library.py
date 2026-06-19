"""Minimal normative-library KPAR import (completion-roadmap Phase 3b).

Implements the value-type slice of `docs/sysml-v2/KPAR_IMPORT_CONTRACT.md`:
import the KerML `ScalarValues` package from the pinned `Data-Type-Library.kpar`
as **real read-only KerML kernel elements** (`Package` + `DataType` +
intra-package `Specialization`), materialized in a dedicated ElementFactory that
is **regenerated from the pinned KPAR on load** and never persisted into a user
`.gaphor`. Every element carries provenance back to the pinned archive, member
file, source declaration text, and line. Cross-library references the minimal
closure does not import (for example `ScalarValue specializes DataValue`, which
lives in `Base`) are recorded as explicit unresolved references -- never
silently dropped.

Scope (per the contract): this imports the `ScalarValues` value-type package
only. The importer is closed-world over `docs/sysml-v2/omg/20250201` and never
fetches. General user KPAR import and full dependency-closure import are Phase 3c.
The entry surface is a Python API only.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from gaphor.SysML2.kpar.reader import KparArchive, read_kpar, read_member_text

if TYPE_CHECKING:
    from gaphor.core.modeling import ElementFactory
    from gaphor.SysML2 import kerml

# Closed-world source root: the Phase 1 pinned artifacts. The importer never
# reads model content from anywhere else and never fetches over the network.
_DEFAULT_OMG_DIR = Path(__file__).resolve().parents[3] / "docs/sysml-v2/omg/20250201"
_DATA_TYPE_LIBRARY = "Data-Type-Library.kpar"
_SCALAR_VALUES_MEMBER = "ScalarValues.kerml"

_PACKAGE_RE = re.compile(
    r"^(?:[A-Za-z_]\w*\s+)*?package\s+(?P<name>[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)\s*\{$"
)
_IMPORT_RE = re.compile(
    r"^(?:(?P<vis>private|public)\s+)?import\s+"
    r"(?P<name>[A-Za-z_]\w*(?:::[A-Za-z_]\w*|::\*)*)\s*;$"
)
_DATATYPE_RE = re.compile(
    r"^(?P<abstract>abstract\s+)?datatype\s+(?P<name>[A-Za-z_]\w*)\s*"
    r"(?:(?:specializes|:>)\s+(?P<supers>[^;{]+))?\s*;$"
)


class LibraryImportError(Exception):
    """A structural precondition for importing a normative library failed."""


@dataclass(frozen=True)
class ElementProvenance:
    """Where an imported element came from, traced to the pinned KPAR."""

    kpar_path: Path
    kpar_sha256: str
    member: str  # archive entry, e.g. "Kernel Data Type Library/ScalarValues.kerml"
    declaration: str  # source declaration text, e.g. "datatype Real specializes Complex"
    line: int  # 1-based line in the member file


@dataclass(frozen=True)
class UnresolvedReference:
    """A reference the minimal import closure does not resolve, recorded loudly.

    Carries the same provenance an imported element does, so an unresolved
    cross-library reference traces back to the exact pinned source declaration.
    """

    source: str  # qualified name of the referring element
    target: str  # the unresolved name as written, e.g. "DataValue"
    kind: str  # "specialization"
    kpar_path: Path
    kpar_sha256: str
    member: str
    line: int
    declaration: str  # the source declaration text the reference came from
    message: str


@dataclass(frozen=True)
class KparDependency:
    """A `.project.json` `usage` dependency resolved to a pinned artifact."""

    resource: str  # the declared resource URL
    filename: str  # its basename, e.g. "Semantic-Library.kpar"
    path: Path  # the matched pinned artifact
    version_constraint: str | None


@dataclass(frozen=True)
class _DatatypeDecl:
    name: str
    abstract: bool
    specializes: tuple[str, ...]
    line: int
    text: str


@dataclass(frozen=True)
class _LibraryModule:
    package: str
    package_line: int
    package_text: str
    imports: tuple[tuple[str, int], ...]
    datatypes: tuple[_DatatypeDecl, ...]
    unsupported: tuple[tuple[str, int], ...]


class NormativeLibrary:
    """A read-only, regenerated-on-load view of an imported normative library.

    Holds the materialized KerML kernel elements and answers value-type
    resolution queries. There is no editing surface: the contract treats
    normative libraries as read-only, and the library is rebuilt from the pinned
    KPAR each time it is imported.
    """

    def __init__(
        self,
        package: kerml.Package,
        index: dict[str, kerml.Element],
        simple_names: dict[str, kerml.Element],
        provenance: dict[str, ElementProvenance],
        relationships: tuple[kerml.Element, ...],
        dependencies: tuple[KparDependency, ...],
        unresolved: tuple[UnresolvedReference, ...],
        unsupported: tuple[tuple[str, int], ...],
    ) -> None:
        self.package = package
        self._index = index
        self._simple = simple_names
        self._provenance = provenance
        self._relationships = relationships
        self.dependencies = dependencies
        self.unresolved = unresolved
        self.unsupported = unsupported

    def resolve(self, name: str) -> kerml.Element | None:
        """Resolve a qualified (``ScalarValues::Real``) or simple (``Real``) name."""
        element = self._index.get(name)
        if element is not None:
            return element
        return self._simple.get(name)

    def provenance_of(self, element: kerml.Element) -> ElementProvenance | None:
        return self._provenance.get(element.id)

    def supertypes(self, element: kerml.Element) -> tuple[kerml.Element, ...]:
        """The resolved general types of an imported element (intra-library)."""
        from gaphor.SysML2 import kerml

        generals: list[kerml.Element] = []
        for relationship in element.ownedRelationship:
            if isinstance(relationship, kerml.Specialization):
                generals.extend(relationship.general)
        return tuple(generals)

    @property
    def elements(self) -> tuple[kerml.Element, ...]:
        """The named imported elements, ordered by qualified name for determinism."""
        return tuple(self._index[name] for name in sorted(self._index))

    @property
    def relationships(self) -> tuple[kerml.Element, ...]:
        """Imported relationship elements (Specializations) carrying provenance."""
        return self._relationships

    @property
    def qualified_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._index))


def import_scalar_values_library(omg_dir: str | Path | None = None) -> NormativeLibrary:
    """Import the KerML ``ScalarValues`` value-type package from the pinned KPAR.

    Returns a read-only :class:`NormativeLibrary`. Raises a
    :class:`~gaphor.SysML2.kpar.reader.KparError` subclass if the pinned archive
    is missing/malformed, and :class:`LibraryImportError` if the archive does not
    contain the expected ``ScalarValues`` member or package.
    """
    from gaphor.core.modeling import ElementFactory
    from gaphor.SysML2 import kerml
    from gaphor.SysML2 import kerml_kernel as kk

    base = Path(omg_dir) if omg_dir is not None else _DEFAULT_OMG_DIR
    kpar_path = base / _DATA_TYPE_LIBRARY

    archive = read_kpar(kpar_path)
    member = f"{archive.root}/{_SCALAR_VALUES_MEMBER}"
    if member not in {model_file.member for model_file in archive.model_files}:
        raise LibraryImportError(
            f"{kpar_path}: expected member {member!r} not found in archive"
        )
    text = read_member_text(archive, member)
    sha256 = _sha256(kpar_path)

    # Closed-world dependency resolution: every declared `usage` entry must match
    # a pinned artifact, or the import fails loudly (per the contract).
    dependencies = _resolve_dependencies(archive, base, kpar_path)

    module = _parse_scalar_library(text)
    if module is None:
        raise LibraryImportError(
            f"{kpar_path}: {member} does not declare a recognisable library package"
        )

    factory = ElementFactory()
    provenance: dict[str, ElementProvenance] = {}

    package = factory.create(kerml.Package)
    package.declaredName = module.package
    provenance[package.id] = ElementProvenance(
        kpar_path, sha256, member, module.package_text, module.package_line
    )

    by_name: dict[str, kerml.Element] = {}
    for decl in module.datatypes:
        datatype = factory.create(kerml.DataType)
        datatype.declaredName = decl.name
        datatype.isAbstract = decl.abstract
        kk.add_owned_member(package, datatype, factory.create(kerml.OwningMembership))
        by_name[decl.name] = datatype
        provenance[datatype.id] = ElementProvenance(
            kpar_path, sha256, member, decl.text, decl.line
        )

    unresolved: list[UnresolvedReference] = []
    relationships: list[kerml.Element] = []
    for decl in module.datatypes:
        specific = by_name[decl.name]
        for super_name in decl.specializes:
            general = by_name.get(super_name)
            if general is not None:
                specialization = factory.create(kerml.Specialization)
                specialization.specific = specific
                specialization.general = general
                specific.ownedRelationship = specialization
                specialization.owningRelatedElement = specific
                relationships.append(specialization)
                provenance[specialization.id] = ElementProvenance(
                    kpar_path, sha256, member, decl.text, decl.line
                )
            else:
                unresolved.append(
                    UnresolvedReference(
                        source=kk.qualified_name(specific),
                        target=super_name,
                        kind="specialization",
                        kpar_path=kpar_path,
                        kpar_sha256=sha256,
                        member=member,
                        line=decl.line,
                        declaration=decl.text,
                        message=(
                            f"{decl.name} specializes {super_name!r}, which is not in "
                            f"the imported {module.package} closure; recorded as a "
                            "cross-library reference, not dropped"
                        ),
                    )
                )

    index: dict[str, kerml.Element] = {kk.qualified_name(package): package}
    simple_names: dict[str, kerml.Element] = {module.package: package}
    for name, datatype in by_name.items():
        index[kk.qualified_name(datatype)] = datatype
        simple_names[name] = datatype

    return NormativeLibrary(
        package=package,
        index=index,
        simple_names=simple_names,
        provenance=provenance,
        relationships=tuple(relationships),
        dependencies=dependencies,
        unresolved=tuple(unresolved),
        unsupported=module.unsupported,
    )


def _resolve_dependencies(
    archive: KparArchive, base: Path, kpar_path: Path
) -> tuple[KparDependency, ...]:
    """Match each `.project.json` `usage` entry to a pinned artifact.

    Closed-world: the importer never fetches, so a declared dependency that does
    not resolve to a pinned artifact under ``base`` fails the import loudly.
    """
    resolved: list[KparDependency] = []
    for usage in archive.project.usage:
        filename = usage.resource.rsplit("/", 1)[-1]
        dep_path = base / filename
        if not dep_path.is_file():
            raise LibraryImportError(
                f"{kpar_path}: declared usage dependency {usage.resource!r} does not "
                f"resolve to a pinned artifact (expected {dep_path}); closed-world "
                f"import over {base} cannot satisfy it"
            )
        resolved.append(
            KparDependency(
                resource=usage.resource,
                filename=filename,
                path=dep_path,
                version_constraint=usage.version_constraint,
            )
        )
    return tuple(resolved)


def _parse_scalar_library(text: str) -> _LibraryModule | None:
    """Parse the value-type subset of a KerML library file.

    Handles exactly what the normative ``ScalarValues`` package uses: a
    ``[standard] [library] package`` wrapper, ``doc`` blocks, ``[private|public]
    import`` statements, and ``[abstract] datatype X [specializes A, B];``
    declarations. Anything else inside the package is recorded as an unsupported
    construct (never silently dropped); returns ``None`` if no package is found.
    """
    package: str | None = None
    package_line = 0
    package_text = ""
    imports: list[tuple[str, int]] = []
    datatypes: list[_DatatypeDecl] = []
    unsupported: list[tuple[str, int]] = []
    inside = False
    in_block = False

    for lineno, raw in enumerate(text.splitlines(), start=1):
        clean, in_block = _strip_comments(raw, in_block)
        stmt = clean.strip()
        if not stmt or stmt == "doc":
            continue

        if not inside:
            header = _PACKAGE_RE.match(stmt)
            if header:
                package = header.group("name")
                package_line = lineno
                package_text = stmt.rstrip("{").strip()
                inside = True
            else:
                unsupported.append((stmt, lineno))
            continue

        if stmt == "}":
            inside = False
            continue

        import_match = _IMPORT_RE.match(stmt)
        if import_match:
            imports.append((import_match.group("name"), lineno))
            continue

        datatype_match = _DATATYPE_RE.match(stmt)
        if datatype_match:
            supers_group = datatype_match.group("supers")
            supers = (
                tuple(s.strip() for s in supers_group.split(",") if s.strip())
                if supers_group
                else ()
            )
            datatypes.append(
                _DatatypeDecl(
                    name=datatype_match.group("name"),
                    abstract=bool(datatype_match.group("abstract")),
                    specializes=supers,
                    line=lineno,
                    text=stmt.rstrip(";").strip(),
                )
            )
            continue

        unsupported.append((stmt, lineno))

    if package is None:
        return None
    return _LibraryModule(
        package=package,
        package_line=package_line,
        package_text=package_text,
        imports=tuple(imports),
        datatypes=tuple(datatypes),
        unsupported=tuple(unsupported),
    )


def _strip_comments(line: str, in_block: bool) -> tuple[str, bool]:
    """Strip ``/* */`` (possibly multi-line) and ``//`` comments from one line."""
    out: list[str] = []
    i = 0
    n = len(line)
    while i < n:
        if in_block:
            end = line.find("*/", i)
            if end == -1:
                return "".join(out), True
            in_block = False
            i = end + 2
            continue
        block_start = line.find("/*", i)
        line_comment = line.find("//", i)
        if line_comment != -1 and (block_start == -1 or line_comment < block_start):
            out.append(line[i:line_comment])
            return "".join(out), False
        if block_start == -1:
            out.append(line[i:])
            return "".join(out), False
        out.append(line[i:block_start])
        in_block = True
        i = block_start + 2
    return "".join(out), in_block


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
