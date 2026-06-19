"""Read-only KPAR archive support for SysML v2 (completion-roadmap Phase 2+).

Phase 2 ships the read-only reader: validate an archive, extract its
project/index metadata, and discover its model files. Later phases build the
standard-library loader and general KPAR import/export on top of this.
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
]
