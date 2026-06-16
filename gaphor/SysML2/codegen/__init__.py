"""SysML v2 code-generation adapters.

M1a proves the generator path from the OMG normative MOF XMI abstract syntax
(docs/sysml-v2/omg/20250201/) into Gaphor's own model-code pipeline. Gaphor's
`gaphor.codegen.coder` generates Python `Base` subclasses from `.gaphor` model
files, not from external XMI, so the adapter here translates a MOF XMI slice
into the `.gaphor` model shape the coder accepts. No SysML v2 semantics are
introduced by this module.
"""
