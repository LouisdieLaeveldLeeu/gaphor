"""Write a Gaphor SysML2 model to a KPAR archive (completion-roadmap Phase 10).

The reverse of `project_import`: a model rooted at a KerML `Namespace` is serialized
to SysML v2 text and packaged as a `.kpar` project archive (a ZIP with a single
project directory containing `.project.json`, `.meta.json`, and the model members),
the same layout `read_kpar` inspects and `import_user_kpar` consumes.

Single-member layout (the chosen Phase 10 scope): the WHOLE model is exported to one
`<model>.sysml` member via the textual exporter, and `.meta.json` indexes each
top-level member name to it. A text->Gaphor model has no original per-file
boundaries to preserve, and import re-merges members into one root anyway, so a
single member is the honest representation.

Identity / round-trip rules:

- Read-only library proxies (standard-library value types, the implicit-base
  `Anything`/`things`) and synthesized feature-chain connector features are NOT
  written -- they are regenerable references / structural artifacts, and the text
  exporter already omits them. The `.meta.json` index lists only real top-level
  user members.
- Interchange round-trips by CANONICAL-FORM equivalence, not byte-identity: member
  naming and entry ordering are the writer's choice, so `KPAR -> Gaphor -> KPAR` and
  `text -> Gaphor -> KPAR -> Gaphor -> text` are proven by comparing the imported
  models' canonical forms (`roundtrip.canonical_form`), the same semantic test the
  text round-trip uses.
- Provenance on re-import traces to the single exported member; the original
  per-source-file provenance of an imported KPAR is not preserved across export
  (an honest consequence of the single-member layout).
"""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from gaphor.SysML2 import kerml
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.element_id import element_id
from gaphor.SysML2.export import export_namespace

#: The single model member every export writes (the whole model's text).
MODEL_MEMBER = "model.sysml"

#: Identifies the metamodel in `.meta.json`.
METAMODEL = "SysML2"

#: Characters that are invalid in a Windows path component (plus the path
#: separators `/` and `\`); each is replaced in the project DIRECTORY name so the
#: archive extracts portably on Windows as well as macOS/Linux.
_INVALID_DIR_CHARS = set('<>:"|?*/\\')

#: Reserved Windows device names (case-insensitive, ignoring any extension) that
#: cannot be a directory component; a project directory matching one is prefixed.
_RESERVED_DIR_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{digit}" for digit in range(1, 10)}
    | {f"LPT{digit}" for digit in range(1, 10)}
)


def write_kpar(
    path: str | Path,
    root: kerml.Namespace,
    *,
    project_name: str,
    version: str | None = None,
    description: str | None = None,
) -> Path:
    """Write the SysML2 model rooted at `root` to a KPAR archive at `path`.

    `project_name` names the project (the archive's single project directory and the
    `.project.json` `name`); `version`/`description` are optional `.project.json`
    fields. Returns the written `path`.
    """
    text = export_namespace(root)
    project_dir = _project_dir_name(project_name)

    project: dict[str, object] = {"name": project_name}
    if version is not None:
        project["version"] = version
    if description is not None:
        project["description"] = description

    # The index maps each REAL top-level member name to the single model file;
    # library proxies and anonymous members (e.g. a nameless connector) are omitted.
    # `elementIds` carries each member's API-facing elementId (Phase 12) so the
    # archive records the OMG element identity; the reader tolerates the extra key.
    index = {}
    element_ids = {}
    for member in kk.members(root):
        if kk.is_library_proxy(member):
            continue
        name = kk.effective_name(member)
        if name is None:
            continue
        index[name] = MODEL_MEMBER
        element_ids[name] = element_id(member)
    meta = {"index": index, "metamodel": METAMODEL, "elementIds": element_ids}

    path = Path(path)
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            f"{project_dir}/.project.json", json.dumps(project, indent=2)
        )
        archive.writestr(f"{project_dir}/.meta.json", json.dumps(meta, indent=2))
        archive.writestr(f"{project_dir}/{MODEL_MEMBER}", text)
    return path


def _project_dir_name(project_name: str) -> str:
    """A PORTABLE single-segment project directory name from `project_name`.

    The exported archive must extract on Windows, macOS, and Linux, so the project
    DIRECTORY component is reduced to a portable slug (the original name is still kept
    verbatim as the `.project.json` display `name`):

    - path separators and Windows-invalid characters (`< > : " | ? *`) and control
      characters are replaced with `_`;
    - leading/trailing whitespace and TRAILING dots/spaces are trimmed (Windows
      silently drops trailing dots/spaces, which would change or empty the name);
    - an empty result, or a relative-path special (`.`/`..` -- which would place
      entries OUTSIDE the project directory, e.g. `../.project.json`), falls back to a
      constant, so `--name ..` cannot escape the project dir;
    - a reserved Windows device name (`CON`, `PRN`, `AUX`, `NUL`, `COM1`-`COM9`,
      `LPT1`-`LPT9`, case-insensitive, ignoring any extension) is prefixed with `_`.
    """
    name = "".join(
        "_" if char in _INVALID_DIR_CHARS or not char.isprintable() else char
        for char in project_name
    )
    name = name.strip().rstrip(". ")
    if name in ("", ".", ".."):
        return "Project"
    if name.split(".", 1)[0].upper() in _RESERVED_DIR_NAMES:
        return f"_{name}"
    return name
