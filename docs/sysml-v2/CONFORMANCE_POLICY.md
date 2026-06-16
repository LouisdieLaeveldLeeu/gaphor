# SysML v2 Conformance Policy

## Pinned Baseline

The implementation baseline is:

- OMG SysML 2.0 formal, publication date September 2025.
- OMG KerML 1.0 formal, publication date September 2025.
- OMG machine-readable abstract syntax and KPAR library artifacts under `SysML/20250201` and `KerML/20250201`.
- The Systems Modeling Community release repository is a convenience source for extracted BNF and readable library variants, not the authority for conformance when it differs from the OMG formal specification documents.

Primary references:

- https://www.omg.org/spec/SysML/2.0/About-SysML
- https://www.omg.org/spec/KerML/1.0/About-KerML
- https://github.com/Systems-Modeling/SysML-v2-Release/releases

Updates to later SysML, KerML, API, or RTF beta artifacts require a mapping decision update, support-matrix review, and focused regression fixtures before the pin changes.

## Claim Rules

Conformance claims are cell-based. A construct may be parsed without being importable, persistable, exportable, diagrammable, or supported. `docs/sysml-v2/SUPPORT_MATRIX.md` is the claim ledger.

No construct is called supported unless:

- the relevant support-matrix cells are complete,
- tests cover those cells,
- import/export round-trip compares canonical forms rather than strings or ids,
- unsupported syntax is preserved-and-warned only when the preservation conditions are satisfied, or rejected with an error.

## Unsupported Syntax

Unsupported syntax is never silently dropped.

Use `ERROR` when a construct cannot be understood enough to preserve safely, when references cannot be tracked, or when the model would export incorrectly.

Use `WARNING` only when the construct or optional feature is preserved losslessly, its owner namespace is preserved, no operation in the session requires understanding its internals, outbound references are either self-contained or tracked and revalidated, and export can re-emit it safely.

Use `INFO` for non-semantic normalization such as formatting changes or generated ids.

## Verification Standard

Every phase must run the controller gates plus focused project-native checks. A skipped check is an environment limitation, not a pass. The commit message records exact commands and outcomes.
