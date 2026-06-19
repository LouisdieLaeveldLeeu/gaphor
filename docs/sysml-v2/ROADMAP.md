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
- KPAR is now in completion scope. General KPAR support is not a detour around
  the standard library; it is a first-class interchange/library capability,
  phased below so the stdlib path does not require full user import/export to
  land first.

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

### Phase 2 -- KPAR Reader Core

Build a read-only KPAR archive reader:

- archive validation;
- project/manifest metadata extraction;
- internal model-file discovery;
- stable diagnostics for malformed archives or unsupported layouts.

This phase inspects KPARs but does not import user models into Gaphor.

Exit: pinned KPARs can be inspected deterministically; unknown structure fails
loudly.

### Phase 3 -- Standard Library Loader

Load the normative model libraries from pinned KPARs into a read-only library
layer. Resolve at minimum:

- `ScalarValues::Real`
- `ScalarValues::String`
- `ScalarValues::Boolean`
- `ScalarValues::Integer`
- any required qualified aliases or owning packages needed by the formal library
  structure.

Every loaded library element must trace back to a pinned KPAR source entry. No
hand-authored curated value-type stubs.

Exit: the real standard library can answer value-type resolution queries.

### Phase 4 -- AttributeUsage Promotion

Use the standard-library loader to finish primitive/value-typed attributes.

Work:

- parse, map, validate, export, and round-trip `attribute x : Real` and related
  primitive/value types;
- update UI type selection if the existing AttributeUsage editor should expose
  read-only library types;
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

### Phase 10 -- General KPAR Import

Move from library-only KPAR handling to user-facing KPAR import:

- import supported KPAR project archives into the SysML2 model pipeline;
- preserve or reject unsupported content according to the conformance policy;
- add CLI and UI entry points if appropriate for Gaphor's import flow;
- add diagnostics for unsupported constructs and references.

Exit: KPAR import is a supported capability for the implemented SysML2 surface.

### Phase 11 -- General KPAR Export And Round-Trip

Export Gaphor SysML2 models to KPAR and prove interchange round-trips:

- `.gaphor` SysML2 model -> KPAR;
- KPAR -> Gaphor -> KPAR;
- text -> Gaphor -> KPAR -> Gaphor -> text;
- identity/provenance rules documented and tested.

Exit: KPAR support is complete for the implemented SysML2 surface, not just
stdlib ingestion.

### Phase 12 -- Versioned Spec-Ingestion Pipeline

Build the future-spec machinery:

- generated metamodel indexes from XMI/KPAR inputs;
- provenance/hash refresh tooling;
- diffs for added/removed classes, properties, enum literals, derived/stored
  changes, and library changes;
- fail-fast review reports for unknown mapping changes, especially new stored
  references without an ownership policy.

Exit: future OMG SysML/KerML releases can be assessed mechanically before human
mapping decisions.

### Phase 13 -- SysML v2 API Alignment

Decide and implement the SysML v2 API/client surface needed by Gaphor, if any:

- keep Gaphor's internal ids distinct from SysML/API-facing ids;
- add API-facing identity/export compatibility only where required;
- align diagnostics and interchange metadata with the formal API where it affects
  model compatibility.

Exit: API-related scope is either implemented and tested or explicitly closed
with a documented rationale.

### Phase 14 -- CI And Release Hardening

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
4. Phase 3
5. Phase 4
6. Phase 5
7. Phase 9
8. Phase 8
9. Phase 6
10. Phase 7
11. Phase 10
12. Phase 11
13. Phase 12
14. Phase 13
15. Phase 14

Rationale: KPAR and the standard library unblock value typing first. Deeper
resolution then becomes shared infrastructure for the remaining semantic work.
Connector ends and ports are closely related, so they should be addressed before
the larger expression/action behavior phases. General KPAR import/export should
come after the semantic surface is strong enough to represent the imported
content. Spec-ingestion and CI hardening close the loop.

## Definition Of Done

The matrix is complete when every row's status is its honest maximum and every
`yes` cell has a conformance test, with any row that cannot reach `supported`
showing `alpha`/`internal-only` plus a documented, scheduled or explicitly closed
reason. Completion means no silent gaps, not every cell forced green.
