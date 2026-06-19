"""Read-only KPAR archive support for SysML v2 (completion-roadmap Phase 2+).

Phase 2 ships the read-only reader: validate an archive, extract its
project/index metadata, and discover its model files. Later phases first settle
the semantic import contract, then use that import path for normative standard
libraries, general user KPAR projects, and KPAR export/round-trip.
"""

from gaphor.SysML2.kpar.reader import (
    KparArchive,
    KparError,
    KparLayoutError,
    KparMeta,
    KparMetadataError,
    KparModelFile,
    KparNotAnArchiveError,
    KparNotFoundError,
    KparProject,
    KparUsage,
    read_kpar,
    read_member_text,
)
from gaphor.SysML2.kpar.library import (
    ElementProvenance,
    KparDependency,
    LibraryImportError,
    NormativeLibrary,
    UnresolvedReference,
    import_scalar_values_library,
)
from gaphor.SysML2.kpar.project_import import (
    ExternalDependency,
    ImportedMember,
    ProjectProvenance,
    RejectedMember,
    UnresolvedTypeReference,
    UserKparImport,
    import_user_kpar,
)

__all__ = [
    "KparArchive",
    "KparError",
    "KparLayoutError",
    "KparMeta",
    "KparMetadataError",
    "KparModelFile",
    "KparNotAnArchiveError",
    "KparNotFoundError",
    "KparProject",
    "KparUsage",
    "read_kpar",
    "read_member_text",
    "ElementProvenance",
    "KparDependency",
    "LibraryImportError",
    "NormativeLibrary",
    "UnresolvedReference",
    "import_scalar_values_library",
    "ExternalDependency",
    "ImportedMember",
    "ProjectProvenance",
    "RejectedMember",
    "UnresolvedTypeReference",
    "UserKparImport",
    "import_user_kpar",
]
