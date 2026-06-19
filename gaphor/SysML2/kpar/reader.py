"""Read-only reader for OMG KPAR archives (completion-roadmap Phase 2).

A KPAR is a ZIP archive holding one library/project: a single top-level project
directory containing a ``.project.json`` descriptor, a ``.meta.json`` index, and
the project's ``.kerml``/``.sysml`` model files. This module validates such an
archive, extracts its project/index metadata, and discovers its model files.

It deliberately does NOT interpret model content or import anything into Gaphor.
That is later completion-roadmap work: the import design contract, minimal
normative-library import, general user KPAR import, and KPAR export/round-trip.
This phase only inspects.

Diagnostics are loud and typed: anything that is not a readable ZIP with exactly
one recognised project layout raises a :class:`KparError` subclass rather than
guessing. Known-benign archive noise (``__MACOSX/`` from macOS zip tooling,
``.DS_Store``) is skipped explicitly and documented -- it is never treated as
part of the model, and anything *else* outside the project directory is an error,
honouring the project's "never silently drop unknown structure" rule.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from zipfile import BadZipFile, ZipFile, is_zipfile

PROJECT_DESCRIPTOR = ".project.json"
META_DESCRIPTOR = ".meta.json"
MODEL_SUFFIXES = (".kerml", ".sysml")

# Archive noise some zip tools inject; not part of the KPAR model. These are
# skipped when interpreting layout; anything else outside the project dir errors.
_NOISE_PREFIXES = ("__MACOSX/",)
_NOISE_BASENAMES = (".DS_Store",)


class KparError(Exception):
    """Base class for all KPAR reader failures."""


class KparNotFoundError(KparError):
    """The archive path does not exist."""


class KparNotAnArchiveError(KparError):
    """The path is not a readable ZIP archive (bad magic or corrupt entry)."""


class KparLayoutError(KparError):
    """The archive does not match the expected single-project KPAR layout."""


class KparMetadataError(KparError):
    """A required descriptor (.project.json/.meta.json) is missing or malformed."""


@dataclass(frozen=True)
class KparUsage:
    """A declared dependency on another KPAR resource (from ``usage``)."""

    resource: str
    version_constraint: str | None = None


@dataclass(frozen=True)
class KparProject:
    """Parsed ``.project.json`` descriptor."""

    name: str
    version: str | None
    description: str | None
    usage: tuple[KparUsage, ...]


@dataclass(frozen=True)
class KparMeta:
    """Parsed ``.meta.json`` index."""

    index: Mapping[str, str]  # element/package name -> member filename
    created: str | None
    metamodel: str | None


@dataclass(frozen=True)
class KparModelFile:
    """A discovered model file inside the archive."""

    member: str  # full archive entry, e.g. "Kernel Data Type Library/ScalarValues.kerml"
    name: str  # path relative to the project dir, e.g. "ScalarValues.kerml"
    size: int  # uncompressed size in bytes


@dataclass(frozen=True)
class KparArchive:
    """The inspected, read-only view of a KPAR archive."""

    path: Path
    root: str  # project directory name
    project: KparProject
    meta: KparMeta
    model_files: tuple[KparModelFile, ...]


def read_kpar(path: str | Path) -> KparArchive:
    """Validate and inspect a KPAR archive without importing its content.

    Raises a :class:`KparError` subclass for a missing path, a non-ZIP/corrupt
    archive, an unrecognised layout, or malformed/missing descriptors.
    """
    path = Path(path)
    if not path.exists():
        raise KparNotFoundError(f"{path}: no such file")
    if not is_zipfile(path):
        raise KparNotAnArchiveError(f"{path}: not a ZIP/KPAR archive")

    try:
        with ZipFile(path) as zf:
            corrupt = zf.testzip()
            if corrupt is not None:
                raise KparNotAnArchiveError(f"{path}: corrupt archive entry {corrupt!r}")
            infos = zf.infolist()
            content = [i.filename for i in infos if not _is_noise(i.filename)]

            root = _project_root(path, content)
            project = _read_project(zf, path, root)
            meta = _read_meta(zf, path, root)
            model_files = _discover_model_files(infos, root)
    except BadZipFile as exc:
        raise KparNotAnArchiveError(f"{path}: {exc}") from exc

    return KparArchive(
        path=path, root=root, project=project, meta=meta, model_files=model_files
    )


def _is_noise(name: str) -> bool:
    if any(name.startswith(prefix) for prefix in _NOISE_PREFIXES):
        return True
    return name.rsplit("/", 1)[-1] in _NOISE_BASENAMES


def _project_root(path: Path, content: list[str]) -> str:
    descriptors = [n for n in content if n.rsplit("/", 1)[-1] == PROJECT_DESCRIPTOR]
    if not descriptors:
        raise KparLayoutError(
            f"{path}: no {PROJECT_DESCRIPTOR} found; not a KPAR project archive"
        )
    if len(descriptors) > 1:
        raise KparLayoutError(
            f"{path}: multiple {PROJECT_DESCRIPTOR} entries {sorted(descriptors)!r}; "
            "multi-project archives are unsupported"
        )
    descriptor = descriptors[0]
    if "/" not in descriptor:
        raise KparLayoutError(
            f"{path}: {PROJECT_DESCRIPTOR} at archive root; "
            "expected a single project directory"
        )
    root = descriptor.rsplit("/", 1)[0]

    prefix = root + "/"
    stray = sorted(n for n in content if n != root and not n.startswith(prefix))
    if stray:
        raise KparLayoutError(
            f"{path}: entries outside project dir {root!r}: {stray!r}"
        )
    return root


def _read_project(zf: ZipFile, path: Path, root: str) -> KparProject:
    data = _load_json(zf, f"{root}/{PROJECT_DESCRIPTOR}", path)
    if not isinstance(data, dict):
        raise KparMetadataError(f"{path}: {PROJECT_DESCRIPTOR} is not a JSON object")
    name = data.get("name")
    if not isinstance(name, str) or not name:
        raise KparMetadataError(f"{path}: {PROJECT_DESCRIPTOR} has no 'name'")
    usage = tuple(
        KparUsage(
            resource=str(entry.get("resource", "")),
            version_constraint=_opt_str(entry.get("versionConstraint")),
        )
        for entry in data.get("usage", [])
        if isinstance(entry, dict)
    )
    return KparProject(
        name=name,
        version=_opt_str(data.get("version")),
        description=_opt_str(data.get("description")),
        usage=usage,
    )


def _read_meta(zf: ZipFile, path: Path, root: str) -> KparMeta:
    data = _load_json(zf, f"{root}/{META_DESCRIPTOR}", path)
    if not isinstance(data, dict):
        raise KparMetadataError(f"{path}: {META_DESCRIPTOR} is not a JSON object")
    index_raw = data.get("index", {})
    if not isinstance(index_raw, dict):
        raise KparMetadataError(f"{path}: {META_DESCRIPTOR} 'index' is not an object")
    # Fail loud on a malformed index rather than coercing: the index maps
    # qualified names to member files and later phases resolve against it.
    if any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in index_raw.items()
    ):
        raise KparMetadataError(
            f"{path}: {META_DESCRIPTOR} 'index' must map strings to strings"
        )
    # MappingProxyType keeps the result genuinely read-only (the frozen
    # dataclass alone does not stop callers mutating a plain dict field).
    index = MappingProxyType(dict(sorted(index_raw.items())))
    return KparMeta(
        index=index,
        created=_opt_str(data.get("created")),
        metamodel=_opt_str(data.get("metamodel")),
    )


def _discover_model_files(infos, root: str) -> tuple[KparModelFile, ...]:
    prefix = root + "/"
    files = [
        KparModelFile(
            member=info.filename,
            name=info.filename[len(prefix):],
            size=info.file_size,
        )
        for info in infos
        if not _is_noise(info.filename)
        and not info.filename.endswith("/")
        and info.filename.startswith(prefix)
        and info.filename.lower().endswith(MODEL_SUFFIXES)
    ]
    return tuple(sorted(files, key=lambda model_file: model_file.name))


def _load_json(zf: ZipFile, member: str, path: Path):
    try:
        raw = zf.read(member)
    except KeyError as exc:
        raise KparMetadataError(
            f"{path}: missing required descriptor {member!r}"
        ) from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise KparMetadataError(
            f"{path}: {member!r} is not valid JSON: {exc}"
        ) from exc


def _opt_str(value) -> str | None:
    return value if isinstance(value, str) else None
