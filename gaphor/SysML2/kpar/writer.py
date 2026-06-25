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
from gaphor.SysML2.export import export_namespace

#: The single model member every export writes (the whole model's text).
MODEL_MEMBER = "model.sysml"

#: Identifies the metamodel in `.meta.json`.
METAMODEL = "SysML2"


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
    index = {
        name: MODEL_MEMBER
        for member in kk.members(root)
        if not kk.is_library_proxy(member)
        and (name := kk.effective_name(member)) is not None
    }
    meta = {"index": index, "metamodel": METAMODEL}

    path = Path(path)
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            f"{project_dir}/.project.json", json.dumps(project, indent=2)
        )
        archive.writestr(f"{project_dir}/.meta.json", json.dumps(meta, indent=2))
        archive.writestr(f"{project_dir}/{MODEL_MEMBER}", text)
    return path


def _project_dir_name(project_name: str) -> str:
    """A safe, non-empty single-segment project directory name from `project_name`.

    `read_kpar` requires the descriptors to live under one project directory (no
    archive-root descriptor, no nested separators), so path separators are replaced
    and an empty result falls back to a constant."""
    name = project_name.replace("/", "_").replace("\\", "_").strip()
    return name or "Project"
