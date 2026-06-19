# SysML v2 Completion Roadmap

Goal: complete the SysML v2 effort honestly. Every support-matrix row reaches
its maximum defensible status (`supported`, `alpha` with a named scheduled
dependency, or `internal-only` with a documented rationale), every `yes` cell is
backed by focused tests, and no scope note or source comment contradicts the
implementation.

This is a planning artifact. Per the project's phase-stop discipline, implement
and commit one phase at a time. Each phase stops for human review before the next
phase starts. Claim discipline still holds: a cell advances only with passing
tests.

## Current State

- KerML kernel (27 generated non-enum classes plus 2 enums): `internal-only` --
  Create-API + Persist are tested, and the five kernel behaviours are tested.
  The kernel grew deliberately from the original 12-class minimal slice:
  Classifier/Class/Structure and FeatureTyping for M2; Package and DataType for
  package/attribute work; BooleanExpression/Predicate plus
  Expression/Step/Function/Behavior for constraints/requirements; and
  AssociationStructure/Connector plus Association for connections.
- KerML Package: `supported` (all nine cells).
- SysML PartDefinition, PartUsage: `supported` (all nine cells).
- SysML AttributeDefinition: `supported` (all nine cells).
- SysML AttributeUsage: `alpha` (all nine cells for untyped usages and usages
  typed by AttributeDefinition; capped until the standard-library/value-type
  path supports `attribute x : Real` and related primitive/value types).
- SysML ActionDefinition, ActionUsage: `alpha` (all nine cells for the
  declaration-and-typing surface; capped on action bodies, nested steps,
  succession/flow connections, and parameters).
- SysML ConstraintDefinition/Usage and RequirementDefinition/Usage: `alpha` (all
  nine cells for the declaration-and-typing surface; capped on constraint
  expression bodies and requirement `subject`/`assume`/`require` parameters).
- SysML PortDefinition, PortUsage: `alpha` (all nine cells for unconjugated ports
  typed by PortDefinition; capped on PortConjugation/KerML Conjugation,
  interface, and flow-direction semantics).
- SysML ConnectionDefinition, ConnectionUsage: `alpha` (all nine cells for the
  declaration-and-typing surface; capped on connector-end semantics).
- Resolution scope so far: same-namespace plus simple/nested qualified names,
  including cross-package lookup. Inheritance, visibility, aliases, imports beyond
  the simple cases, and feature chains remain planned work.
- KPAR is now in completion scope. General KPAR import is the next architectural
  track after the read-only reader: first a design contract, then minimal
  normative-library import, then general user KPAR import. Standard-library
  value typing and AttributeUsage promotion build on that import path rather
  than on a separate pre-import library index.

## Definition Of Supported

For a user-facing construct, `supported` means all nine cells are implemented and
tested:

1. Parse
2. Import
3. Create-API
4. Persist
5. Validate
6. Export
7. Round-trip
8. Diagram
9. UI-edit

For structural KerML bases, `internal-only` is final and honest: they have no
textual concrete syntax or user-facing diagram/edit surface.

## Completion Phases

### Phase 0 -- Scope Reset And Audit Cleanup -- DONE

Reset the roadmap from the post-M2 dependency placeholder to the full completion
plan. Bring KPAR into scope, while keeping the work phased. Clean stale audit
findings in docs and comments, update verification planning, and regenerate the
support-matrix spreadsheet if the Markdown matrix changes.

Exit: no behavior changes; documentation, controller state, and verification
instructions are internally consistent; gates pass.

### Phase 1 -- KPAR Artifact Baseline -- DONE

Fetch and pin the OMG 20250201 `.kpar` artifacts:

- KerML `Semantic-Library.kpar`, `Data-Type-Library.kpar`, and
  `Function-Library.kpar`.
- SysML `Systems-Library.kpar` and the published domain libraries.

Record source URLs, OMG file ids, SHA-256 hashes, and archive sizes in the
artifact manifest. Add tests that verify the pinned archives exist, match the
manifest, are readable zip archives, and contain expected internal entries.

Exit (reached): KPAR bytes are reproducible source artifacts. No semantic import
yet.

### Phase 2 -- KPAR Reader Core -- DONE

Build a read-only KPAR archive reader:

- archive validation;
- project/manifest metadata extraction;
- internal model-file discovery;
- stable diagnostics for malformed archives or unsupported layouts.

This phase inspects KPARs but does not import user models into Gaphor.

Delivered as `gaphor/SysML2/kpar/` (a `read_kpar()` reader returning frozen
`KparArchive`/`KparProject`/`KparMeta`/`KparModelFile` dataclasses, with a typed
`KparError` hierarchy) plus a read-only `sysml2-kpar-info` CLI command. Benign
zip noise (`__MACOSX/`, `.DS_Store`) is skipped explicitly; any other
out-of-project entry, multi-project layout, missing/duplicate descriptor, or
malformed JSON raises loudly. No model content is interpreted.

Exit (reached): pinned KPARs can be inspected deterministically; unknown
structure fails loudly.

### Phase 3a -- KPAR Import Design Contract -- DONE

Decide the import semantics before materializing KPAR content as Gaphor model
state. This is a design/contract phase, not a broad parser implementation.

Delivered as `docs/sysml-v2/KPAR_IMPORT_CONTRACT.md`, anchored by
`gaphor/SysML2/tests/test_kpar_import_contract.py` and a static existence gate.
Ratified decisions: ElementFactory-backed read-only library elements regenerated
from the pinned KPAR on load (not persisted into `.gaphor`); subset-import with
explicit unresolved/diagnostic records and never silent loss; a Python-API-only
entry surface for 3b; and a closed-world dependency policy over the pinned
artifacts (minimal closure; missing required dependency fails the import).

Resolved decision areas (the binding policy for each is in the contract):

- identity: Gaphor `Base.id`, source KPAR identity, API-facing ids if present,
  and canonical identity for imported libraries;
- storage: whether imported elements are saved into `.gaphor`, referenced by
  pinned source/provenance, or regenerated from KPAR on load;
- mutability: normative OMG libraries are read-only by default; user KPAR
  imports may become editable only under an explicit policy;
- dependency closure: how `.project.json` `usage` dependencies resolve to pinned
  KPARs, missing KPARs, version constraints, and import order;
- duplicate/re-import/update behavior: same KPAR twice, newer versions, and
  conflicts with existing user elements;
- unsupported syntax policy: fail the import, import a tested subset with
  diagnostics, or create explicit unresolved/proxy records -- no silent loss;
- provenance: every imported element/reference must trace to KPAR path, member
  file, declaration span when available, and source declaration text;
- API/CLI/UI boundary: which import entry points are in scope for the first
  implementation and which remain later.

Exit (reached): a committed design contract and tests/fixtures for the selected
invariants where possible; no imported semantic content yet unless the design
phase is explicitly split and reviewed.

### Phase 3b -- Minimal Normative Library Import -- DONE

Use the Phase 3a contract to import the smallest real OMG KPAR library content
needed for primitive/value typing. This phase targets the normative libraries,
not arbitrary user projects.

Import enough of the pinned KerML libraries to materialize at minimum:

- `ScalarValues::Real`
- `ScalarValues::String`
- `ScalarValues::Boolean`
- `ScalarValues::Integer`
- `ScalarValues::Natural`
- required owning packages, aliases, and dependency links needed by the formal
  library structure.

Every imported library element must trace back to a pinned KPAR, member file,
and source declaration. No hand-authored curated value-type stubs. The chosen
representation (ElementFactory-backed, proxy-backed, or another reviewed form)
must preserve read-only normative-library treatment unless the design contract
explicitly says otherwise.

Delivered as `gaphor/SysML2/kpar/library.py` (`import_scalar_values_library()`
-> read-only `NormativeLibrary`). The KerML `ScalarValues` package is imported
from the pinned `Data-Type-Library.kpar` as real `kerml.Package`/`DataType`
elements with intra-package `Specialization` edges, regenerated into a fresh
ElementFactory on each load and never persisted. Every element carries
provenance (KPAR path, SHA-256, member, declaration text, line); the
cross-library super `ScalarValue :> Base::DataValue` is recorded as an explicit
unresolved reference, not dropped. Python API only; no support-matrix cell moves
(AttributeUsage promotion is Phase 4).

Exit (reached): the real imported standard library can answer value-type
resolution queries with provenance.

### Phase 3c -- General User KPAR Import -- DONE

Expand from minimal normative-library import to user-facing KPAR import for the
implemented SysML2 surface:

- import supported KPAR project archives into the SysML2 model pipeline;
- preserve or reject unsupported content according to the conformance policy and
  the Phase 3a partial-import decision;
- expose a Python API and `sysml2-kpar-import` CLI entry point;
- add diagnostics for unsupported constructs, unresolved references, dependency
  gaps, duplicate imports, and version conflicts.

Delivered as `gaphor/SysML2/kpar/project_import.py` (`import_user_kpar()` ->
`UserKparImport`) plus the `sysml2-kpar-import` CLI command. Each model member is
parsed independently: parseable members are imported as ordinary editable Gaphor
model elements (savable into `.gaphor`, unlike read-only libraries), unparseable
members are recorded as rejected members, and references are resolved
project-wide across imported members (via the new `mapping.map_project`).
References outside the project (libraries, declared `usage` dependencies,
unimported members) are recorded as unresolved references / external-dependency
diagnostics, never silently dropped. Cross-library resolution is Phase 4; GUI
import is Phase 3d.

Deferred (recorded, not claimed): duplicate-import and version-conflict
diagnostics, which apply to re-importing into an already-populated user model --
a re-import/merge concern beyond this self-contained single-project import slice.

Exit (reached): KPAR import is a supported capability for the implemented SysML2
surface (self-contained projects; CLI + Python API).

### Phase 3d -- GUI KPAR Import

Expose the proven KPAR importer through Gaphor's GUI import flow.

Prerequisite: Phase 3c importer behavior is stable and tested for diagnostics,
preservation/rejection of unsupported content, unresolved references, dependency
gaps, duplicate/version conflicts, and output semantics.

Work:

- add a GUI import entry point for `.kpar` projects;
- surface importer diagnostics in the UI without losing detail;
- preserve the same semantics as the Python API and CLI;
- add headless/service-level tests where possible, plus focused GUI smoke tests.

Exit: users can import supported KPAR projects from the Gaphor UI with the same
diagnostic and preservation behavior as the CLI/API.

### Phase 4 -- AttributeUsage Promotion

Use the imported normative standard library to finish primitive/value-typed
attributes.

Work:

- parse, map, validate, export, and round-trip `attribute x : Real` and related
  primitive/value types;
- update UI type selection if the existing AttributeUsage editor should expose
  read-only imported library types;
- promote `SysML AttributeUsage` to `supported` only after focused tests pass.

Exit: AttributeUsage is no longer capped on the standard-library dependency.

### Phase 5 -- Deeper Name Resolution

Replace the current scoped resolver with the planned resolver:

- unqualified lookup through owner namespaces;
- imports and imported memberships;
- inherited members;
- visibility;
- aliases;
- implicit specialization;
- feature chains;
- diagnostics for ambiguous and unresolved names.

Implement or retire the public raising surface for `kerml_kernel.featuring_types()`
as part of this phase.

Exit: the resolver is no longer limited to same-namespace and simple qualified
names.

### Phase 6 -- Constraint And Requirement Semantics

Complete the expression/requirement gate:

- constraint predicate/body syntax and semantic mapping;
- persisted expression/body structure;
- requirement `subject`, `assume`, and `require` parameters;
- validation, export, round-trip, diagram, and UI-edit coverage for the new
  surface.

Exit: ConstraintDefinition/Usage and RequirementDefinition/Usage can be promoted
from `alpha` when all claimed cells pass.

### Phase 7 -- Action Semantics

Complete the action behavior surface:

- action bodies and nested steps;
- succession and flow connection semantics;
- action parameters;
- validation, export, round-trip, diagram, and UI-edit coverage for the new
  surface.

Exit: ActionDefinition and ActionUsage can be promoted from `alpha` when all
claimed cells pass.

### Phase 8 -- Port Semantics

Complete ports beyond the unconjugated declaration-and-typing slice:

- KerML `Conjugation` and SysML `PortConjugation` as required by the normative
  model;
- textual conjugation syntax such as `~P`;
- interface and flow-direction semantics;
- validation, export, round-trip, diagram, and UI-edit coverage.

Exit: PortDefinition and PortUsage can be promoted from `alpha` when all claimed
cells pass.

### Phase 9 -- Connection End Semantics

Complete actual connector endpoints:

- derive/model connector ends faithfully from KerML/SysML semantics;
- parse and export connection syntax with endpoints;
- ensure diagram connection views bind to semantic connector/end state rather
  than only declaration typing;
- validate broken or mismatched endpoints.

Exit: ConnectionDefinition and ConnectionUsage can be promoted from `alpha` when
all claimed cells pass.

### Phase 10 -- General KPAR Export And Round-Trip

Export Gaphor SysML2 models to KPAR and prove interchange round-trips:

- `.gaphor` SysML2 model -> KPAR;
- KPAR -> Gaphor -> KPAR;
- text -> Gaphor -> KPAR -> Gaphor -> text;
- identity/provenance rules documented and tested.

Exit: KPAR support is complete for the implemented SysML2 surface, not just
stdlib ingestion.

### Phase 11 -- Versioned Spec-Ingestion Pipeline

Build the future-spec machinery:

- generated metamodel indexes from XMI/KPAR inputs;
- provenance/hash refresh tooling;
- diffs for added/removed classes, properties, enum literals, derived/stored
  changes, and library changes;
- fail-fast review reports for unknown mapping changes, especially new stored
  references without an ownership policy.

Exit: future OMG SysML/KerML releases can be assessed mechanically before human
mapping decisions.

### Phase 12 -- SysML v2 API Alignment

Decide and implement the SysML v2 API/client surface needed by Gaphor, if any:

- keep Gaphor's internal ids distinct from SysML/API-facing ids;
- add API-facing identity/export compatibility only where required;
- align diagnostics and interchange metadata with the formal API where it affects
  model compatibility.

Exit: API-related scope is either implemented and tested or explicitly closed
with a documented rationale.

### Phase 13 -- CI And Release Hardening

Make verification authoritative:

- decide whether the full-suite Docker workflow becomes per-push/required rather
  than manual/nightly;
- add KPAR artifact/hash checks to the static gates;
- add matrix consistency checks for Markdown and `.xls`;
- run full suite plus focused SysML2 tests before final support claims.

Exit: final claims are backed by local and CI verification with no known
environment-only ambiguity.

## Recommended Execution Order

1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 3a
5. Phase 3b
6. Phase 3c
7. Phase 4
8. Phase 5
9. Phase 9
10. Phase 8
11. Phase 6
12. Phase 7
13. Phase 10
14. Phase 11
15. Phase 12
16. Phase 13

Rationale: the project now intentionally resolves KPAR import architecture
before standard-library/value-type promotion. Phase 3a prevents import identity,
storage, read-only, and partial-import policy from being decided accidentally.
Phase 3b proves that policy on the real normative library content needed for
`attribute x : Real`, and Phase 3c expands it to general user KPAR import. Deeper
resolution then becomes shared infrastructure for the remaining semantic work.
Connector ends and ports are closely related, so they should be addressed before
the larger expression/action behavior phases. KPAR export/round-trip follows
after import semantics exist. Spec-ingestion and CI hardening close the loop.

## Definition Of Done

The matrix is complete when every row's status is its honest maximum and every
`yes` cell has a conformance test, with any row that cannot reach `supported`
showing `alpha`/`internal-only` plus a documented, scheduled or explicitly closed
reason. Completion means no silent gaps, not every cell forced green.
