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

- KerML kernel (31 generated non-enum classes plus 2 enums): `internal-only` --
  Create-API + Persist are tested, and the five kernel behaviours are tested.
  The kernel grew deliberately from the original 12-class minimal slice:
  Classifier/Class/Structure and FeatureTyping for M2; Package and DataType for
  package/attribute work; BooleanExpression/Predicate plus
  Expression/Step/Function/Behavior for constraints/requirements;
  AssociationStructure/Connector plus Association for connections;
  Conjugation for port conjugation (Phase 8a); TextualRepresentation (the
  carrier for a preserved constraint body) for Phase 6a; and
  FeatureMembership/ParameterMembership (the membership roots the SysML
  requirement-parameter memberships generalize) for Phase 6b. The
  `FeatureDirectionKind` enum is one of the 2 enums; Phase 8b made
  `Feature::direction` nullable (no new class).
- KerML Package: `supported` (all nine cells).
- SysML PartDefinition, PartUsage: `supported` (all nine cells).
- SysML AttributeDefinition: `supported` (all nine cells).
- SysML AttributeUsage: `supported` (all nine cells, including usages typed by a
  standard-library value type such as `attribute x : Real`, resolved against the
  pinned ScalarValues library via a read-only value-type proxy -- Phase 4).
- SysML ActionDefinition, ActionUsage: `alpha` (all nine cells for the
  declaration-and-typing surface; capped on action bodies, nested steps,
  succession/flow connections, and parameters).
- SysML ConstraintDefinition/Usage and RequirementDefinition/Usage: `alpha` (the
  declaration-and-typing surface; constraints also preserve an opaque expression
  body -- `constraint c { <expr> }` stored as a TextualRepresentation, Phase 6a;
  requirements also carry `subject`/`assume`/`require` via their normative
  memberships, Phase 6b, plus `reqId` (as `declaredShortName`) and
  `actor`/`stakeholder` parameter memberships, Phase 6c). Capped on constraint
  expression SEMANTICS (a faithful KerML expression tree), structured
  requirement-parameter UI-edit (only a `reqId` editor exists), and the remaining
  named requirement surface: `framedConcern` plus the Concern construct (Phase 6d).
- SysML PortDefinition, PortUsage: `supported` (all nine cells for the
  declaration-and-typing surface INCLUDING conjugation -- `port p : ~Fuel` typed
  by the faithful conjugate via PortConjugation/ConjugatedPortDefinition/
  ConjugatedPortTyping over KerML Conjugation; Phase 8a). Interface semantics
  (Phase 8c) remain a follow-up.
- Feature direction (`in`/`out`/`inout`) is supported on ALL usages (Phase 8b),
  mapping to the nullable KerML `Feature::direction` so undirected stays distinct
  from `in`. Parse, map, export, round-trip, diagram label, and a direction
  property page are covered; undirected is the absent (None) state.
- SysML ConnectionDefinition, ConnectionUsage: `supported` (binary, non-chain
  connector ends -- `connection c connect a to b;` -- resolved to features,
  validated, exported, round-tripped, and projected as a line bound to its ends;
  Phase 9). Feature-chain endpoints (Phase 5e) and n-ary forms remain follow-ups.
- SysML InterfaceDefinition, InterfaceUsage: `alpha` (the connection-level
  surface -- typing by an InterfaceDefinition, binary connect ends, direction,
  own diagram items + type page; Phase 8c). They subclass the connection classes
  and reuse their machinery. Held at alpha on a named dependency: interface-end
  PORT bodies (`interface def I { end : ~P; }`) and flow need definition-body
  grammar (no construct has it yet).
- Resolution scope so far: nearest-first lookup across enclosing namespaces
  (Phase 5) -- same-namespace, enclosing-package, relative-qualified, and
  root-qualified names, with inner scopes shadowing outer ones. Imports, aliases,
  inherited members, visibility, implicit specialization, and feature chains
  remain planned follow-up work (they need new grammar and semantics).
- KPAR is now in completion scope. KPAR artifact pinning, reader inspection,
  import contract, normative-library import, user-project import, GUI import, and
  the AttributeUsage value-type promotion built on that path are complete for the
  implemented SysML2 surface. KPAR export/round-trip remains Phase 10.

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

### Phase 3d -- GUI KPAR Import -- DONE

Expose the proven KPAR importer through Gaphor's GUI import flow.

Prerequisite: Phase 3c importer behavior is stable and tested for diagnostics,
preservation/rejection of unsupported content, unresolved references, dependency
gaps, and output semantics. (Duplicate-import and version-conflict diagnostics
for re-import into an already-populated model are explicitly deferred in Phase 3c
and are not a prerequisite here; the GUI inherits that same deferral.)

Work:

- add a GUI import entry point for `.kpar` projects;
- surface importer diagnostics in the UI without losing detail;
- preserve the same semantics as the Python API and CLI;
- add headless/service-level tests where possible, plus focused GUI smoke tests.

Delivered as the `gaphor/plugins/sysml2kparimport/` plugin (`SysML2KparImport`, a
`Service`/`ActionProvider` registered as the `sysml2_kpar_import` service). It
lives in `plugins/` rather than `gaphor/SysML2/` because it bridges the UI and
the modeling language, and the architecture rules forbid a modeling-language
package from depending on `gaphor.ui` (beyond `filedialog`/`errordialog`). A new
`import_menu` fragment adds **File -> Import -> Import KPAR Project…** to the
menu bar. Importing adds the user KPAR's content to the *current* model as
editable, undoable elements (reusing the Phase 3c `import_user_kpar`); validation
errors trigger a confirm-or-cancel dialog (cancel removes the just-imported
subtree, mirroring the CLI's refuse-by-default + `--allow-invalid`); rejected
members, unresolved references, and validation errors are surfaced via a summary
toast plus a details dialog. The GTK-free import core (`import_into_model`) is
unit-tested headless; the file chooser and dialogs are the thin GUI layer.

Exit (reached): users can import supported KPAR projects from the Gaphor UI with
the same diagnostic and preservation behavior as the CLI/API.

### Phase 4 -- AttributeUsage Promotion -- DONE

Use the imported normative standard library to finish primitive/value-typed
attributes.

Work:

- parse, map, validate, export, and round-trip `attribute x : Real` and related
  primitive/value types;
- update UI type selection if the existing AttributeUsage editor should expose
  read-only imported library types;
- promote `SysML AttributeUsage` to `supported` only after focused tests pass.

Delivered in `gaphor/SysML2/mapping.py`: when an AttributeUsage's declared type
does not resolve in the user model, the mapper resolves it against the pinned
`ScalarValues` library and types the attribute through a read-only value-type
proxy -- a bare `kerml.DataType` materialized at the model root that is a real
Type for FeatureTyping/validation/persistence but is invisible to textual export
and the round-trip canonical form (so `attribute x : Real;` round-trips and the
library declaration is never dumped). The AttributeUsage typing-kind rule was
relaxed to accept any `DataType` (AttributeDefinition or library value type). The
property page now also offers the concrete library value types. AttributeUsage is
promoted to `supported`; `test_attribute_value_typing.py` covers the full chain.

Exit (reached): AttributeUsage is no longer capped on the standard-library
dependency.

### Phase 5 -- Deeper Name Resolution (Enclosing-Namespace Lookup) -- DONE

Originally this phase listed the full planned resolver (imports, inherited
members, visibility, aliases, implicit specialization, feature chains, ambiguity
diagnostics). Those each need new grammar **and** a semantic contract that does
not exist yet, so they cannot be authored or tested today; they have been
**formally replanned** into the named follow-up phases 5a-5e below. Phase 5 itself
is re-scoped to the part that is reachable with the current grammar:

- a (qualified) type name's first segment is resolved by walking outward from the
  usage's own namespace through each enclosing namespace to the model root, the
  nearest declaration winning (inner scopes shadow outer ones); the remaining
  `::` segments are then navigated as members;
- enclosing-package lookup and relative-qualified names (e.g. a sibling
  `A::Engine`) now resolve, beyond the old same-namespace / root-qualified scope;
- unresolved names remain explicit diagnostics; standard-library value-type
  proxies are excluded from name resolution, so resolution is independent of
  declaration order;
- the unused `kerml_kernel.featuring_types()` raising surface is retired.

Within the current grammar nearest-first resolution is deterministic, so there is
no reachable ambiguity to report; ambiguity diagnostics land with imports
(Phase 5a).

Exit (reached): the resolver is no longer limited to same-namespace and simple
root-qualified names for the grammar we support today.

### Phase 5a -- Imports, Imported Memberships, Visibility & Ambiguity -- PLANNED

Add `import` (and `public`/`private` visibility) syntax and resolve names through
imported memberships, honouring visibility, with ambiguity diagnostics when a
name is visible from more than one import. Prerequisite: grammar for import
statements and member visibility, plus the imported-membership/visibility
semantic contract. Exit: imported names resolve with visibility and ambiguity
reporting.

### Phase 5b -- Aliases -- PLANNED

Add alias declarations and resolve a name through its alias to the aliased
element. Prerequisite: alias grammar + the alias-membership semantic contract.
Exit: an alias resolves to its target wherever the target would resolve.

### Phase 5c -- Inherited Members -- PLANNED

Resolve members inherited through specialization (a feature/member reachable via
a supertype). Prerequisite: definition bodies (members nested in definitions) in
the grammar so inheritance is authorable, plus the inheritance-resolution
contract. Exit: inherited members resolve from a specializing type.

### Phase 5d -- Implicit Specialization -- PLANNED

Apply KerML implicit specialization where the normative model requires it.
Prerequisite: the implicit-specialization semantic contract (and any grammar it
implies). Exit: implicit specializations participate in resolution per the spec.

### Phase 5e -- Feature Chains -- PLANNED

Add feature-chain syntax (`a.b.c`) and resolve a chain step-by-step through
feature types. Prerequisite: feature-chain grammar + the chain-resolution
contract. Exit: feature chains resolve along their feature types. Also enables
feature-chain connector endpoints (`connect a.b to c.d`), the explicit extension
deferred by Phase 9's non-chain endpoint scope.

### Phase 6 -- Constraint And Requirement Semantics

Sliced into independently reviewable requirement/constraint surfaces:

- 6a: constraint expression bodies;
- 6b: requirement `subject` / `assume` / `require`;
- 6c: requirement `reqId`;
- 6d: requirement context parameters (`actor`, `stakeholder`,
  `framedConcern`).

Each slice stops for review before the next starts (the 8a/8b/8c precedent).
The requirement rows remain `alpha` until the named requirement surfaces through
6d are complete and verified; no phase should claim full requirement support
while one of these named surfaces remains scheduled.

#### Phase 6a -- Constraint Expression Bodies -- DONE

Delivered the constraint body surface as PRESERVED OPAQUE TEXT (an explicit
decision -- a faithful KerML expression tree is a later, multi-phase dependency,
so the body is preserved without claiming expression semantics):

- grammar/parser/AST: `constraint def C { <body> }` and
  `[<dir>] constraint c [: C] { <body> }`; the body is captured by a balanced-brace
  terminal (tolerant to nesting) as opaque text; unbalanced braces are a parse
  error (delimiter validation);
- the body is stored as a `TextualRepresentation` (language `sysml`) owned by the
  constraint -- the normative KerML carrier for "this element's content as text in
  a language" (seeded into the kernel; 29 generated non-enum classes now). The
  faithful `Annotation` attachment + expression tree are deferred;
- export re-emits `{<body>}` with no added inner padding; the round-trip
  canonical form records the body as a separate entry (so a constraint with a
  body differs from one without);
  validation reports an empty body (`empty-constraint-body`, WARNING); a property
  page edits the body (deferring for requirements);
- Constraint rows stay `alpha` (the body is preserved, not semantically modeled).

Exit (reached): constraint body text parses, persists, exports, round-trips, and
preserves arbitrary expression text safely; the matrix stays honest (`alpha`).

#### Phase 6b -- Requirement Parameters -- DONE

Delivered requirement `subject`, `assume`, and `require` through their NORMATIVE
membership structure (no local marker fields):

- membership classes generated from the pinned XMI -- KerML
  FeatureMembership/ParameterMembership (kernel) and SysML SubjectMembership/
  RequirementConstraintMembership (with RequirementConstraintKind:
  assumption/requirement);
- grammar/parser/AST: `requirement [def] r [: R] { subject n [: T]; assume
  constraint { <body> } require constraint { <body> } }`; the subject is a
  parameter feature and assume/require constraints REUSE the 6a opaque body;
- mapping builds the subject feature via a SubjectMembership (its type resolved
  nearest-first -- a scoped reference, recorded unresolved if it does not resolve)
  and each assumed/required constraint as a ConstraintUsage owned via a
  RequirementConstraintMembership carrying the kind;
- validation: the subject type via the usual unresolved-type rule, plus a
  model-derived `broken-requirement-parameter` guarding membership-member kinds;
  export re-emits the parts and the round-trip canonical form records
  subject/assume/require as separate entries;
- structured UI-edit for these parts is deliberately deferred (the requirement
  keeps its name/type editors); the rows stay `alpha`.

Requirement rows stay `alpha` after 6b because `reqId` (6c) and the context
parameters (6d) are still scheduled, and constraint expression SEMANTICS remain a
later, multi-phase dependency.

#### Phase 6c -- Lightweight Requirement Parameters (`reqId`, `actor`, `stakeholder`) -- DONE

Delivered the lightweight remaining requirement parameters, grouped because they
share an implementation shape (a small short-name attribute plus two
`subject`-style parameter memberships) and none introduces a new construct:

- `reqId` -- stored CANONICALLY as the requirement's KerML `declaredShortName`
  (not the separately generated `reqId` String slot). The normative `reqId`
  redefines `Element::declaredShortName`, but the coder emits redefinitions as
  distinct slots, so writing both would double-store; `declaredShortName` is the
  one true home (see MAPPING_DECISIONS 6c). Written `<id>` for a bare identifier
  or `<'1.1.3'>` quoted for a dotted/special id, with `\'`/`\\` escapes so any
  short name (even one with a quote) round-trips losslessly via the single
  `shortnames` encode/decode authority; parse/map/persist/validate/export/
  round-trip plus a text-entry editor (`RequirementReqIdPropertyPage`);
- `actor` and `stakeholder` -- `PartUsage` parameters (the pinned XMI types the
  ActorMembership/StakeholderMembership owned parameter as a PartUsage) carried by
  those normative memberships (generated from the pinned XMI): built via their
  memberships in declaration order, their declared types resolved nearest-first
  through the SHARED kind-checked PartUsage->PartDefinition path (scoped
  references, recorded unresolved/wrong-kind otherwise), exported and
  round-tripped (order-sensitive canonical entries). The model-derived exact-one
  `broken-requirement-parameter` rule was extended to both memberships (each must
  own exactly one PartUsage);
- structured UI-edit for `actor`/`stakeholder` is deliberately deferred (only the
  `reqId` text editor is added); the rows stay `alpha`.

A latent grammar bug surfaced and was fixed: a requirement/constraint USAGE with
a type AND a body (`requirement r : R { ... }`) mis-lexed the `{` as a greedy
constraint-body terminal. Constraint bodies are now built from literal `{`/`}`
plus a non-brace `BODY_TEXT` terminal, so every `{` lexes identically and the
PARSER disambiguates body-vs-body by context; opaque bodies stay verbatim
(whitespace and nesting preserved).

Exit: `reqId`, `actor`, and `stakeholder` are implemented and tested end to end;
Requirement rows stay `alpha` (framedConcern, structured requirement-parameter
UI-edit, and constraint expression semantics remain).

#### Phase 6d -- Framed Concern And the Concern Construct

The heavyweight remaining requirement surface, introducing a new construct
(Concern). Sliced by metamodel footprint: 6d-1 is SysML-layer only; 6d-2 adds
kernel classes (subsetting) for the framed-concern reference form.

##### Phase 6d-1 -- Concern Construct + Framed-Concern DECLARE form -- DONE

- the Concern construct -- ConcernDefinition/ConcernUsage generated from the
  pinned XMI (ConcernDefinition -> RequirementDefinition, ConcernUsage ->
  RequirementUsage; SysML-layer, so the kernel stays 31). Because a Concern IS a
  Requirement, both REUSE the requirement body (subject/assume/require/actor/
  stakeholder/frame); `concern def`/`concern` parse, map, validate (ConcernUsage
  is kind-checked to a ConcernDefinition through the shared typed-usage path),
  export, round-trip, persist, project to a diagram item, and get the reqId +
  type editors. New support-matrix rows at `alpha`;
- `framedConcern` (DECLARE form) -- `frame concern <name> [: <C>]` owns a new
  ConcernUsage via a FramedConcernMembership. FramedConcernMembership IS a
  RequirementConstraintMembership with `kind` fixed to `requirement` (the coder
  emits the inherited `assumption` default, so the mapper sets `requirement`
  explicitly); the `require`-constraint reader/validator EXCLUDE it so a framed
  concern is never read as a `require` constraint. Validation: exactly one
  ConcernUsage member and kind=requirement.

Exit: the Concern construct and the framed-concern declare form are implemented
and tested end to end; Requirement/Concern rows stay `alpha`.

##### Phase 6d-2 -- Framed-Concern REFERENCE form -- PLANNED

- `frame <existing>` -- reference an already-declared concern (rather than declare
  a new ConcernUsage). Faithfully this owns an anonymous ConcernUsage that
  subsets the referenced concern, so it needs `ReferenceSubsetting`
  (-> Subsetting -> Specialization) added to the kernel from the pinned XMI -- the
  one new KERNEL footprint, isolated here for review. Grammar/mapping/validation/
  export/round-trip for the reference form.

Exit: all named requirement surfaces (`subject`, `assume`, `require`, `reqId`,
`actor`, `stakeholder`, and `framedConcern` in both declare and reference forms)
plus the Concern construct are implemented and tested. At this point
RequirementDefinition and RequirementUsage can be considered for promotion out of
`alpha`, subject to the normal nine-cell support rule and the remaining
expression-semantics limits.

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

Phase 8 (ports beyond the unconjugated declaration-and-typing slice) is sliced
into 8a/8b/8c so each is a complete, reviewable, individually-promotable surface
(the same precedent as 3a-3d and 5a-5e). Port rows are promoted only for the
surface a slice actually proves.

#### Phase 8a -- Port Conjugation -- DONE

Delivered the faithful port-conjugation surface for `port p : ~Fuel`:

- the normative metamodel is generated from the pinned XMI -- KerML `Conjugation`
  (kernel) and SysML `PortConjugation`, `ConjugatedPortDefinition`,
  `ConjugatedPortTyping`;
- grammar/parser gained the port-scoped `: ~<type>` form (`~` cannot leak onto
  non-port usages);
- the mapper materializes (and reuses) the original definition's implicit
  conjugate and types the port through a `ConjugatedPortTyping`; the conjugate +
  its `PortConjugation` are owned by the original (cascade on delete) and are
  invisible to name resolution, duplicate-name checks, and textual export;
- export re-emits `~Fuel` (never the conjugate as a `port def`); the round-trip
  canonical form distinguishes `: Fuel` from `: ~Fuel`;
- validation reports a non-port conjugation target (mistyped) and a broken
  conjugation model-derived (`broken-conjugation`);
- the diagram projects a conjugated port as a subject-bound `PortUsageItem`
  (the conjugate is never projectable), and the PortUsage type page gained a
  conjugation toggle (UI-edit).

Exit (reached): PortDefinition and PortUsage are promoted from `alpha` to
`supported` for the declaration-and-typing surface INCLUDING conjugation;
flow-direction (8b) and interface (8c) remain explicit follow-ups.

#### Phase 8b -- Flow Direction -- DONE

Delivered feature direction (`in` / `out` / `inout`) on ALL usages, mapping to
KerML `Feature::direction`.

- The generated `Feature::direction` defaulted to `in`, collapsing undirected
  into `in`. KerML makes it `[0..1]`, so direction is now NULLABLE: an explicit
  opt-in (`nullable_optional_enums`) on Gaphor's coder emits an optional enum
  (XMI lower 0, no default) as `_enumeration(..., None)`, and core `enumeration`
  gained `None`-default support. The opt-in is enabled ONLY for the SysML2/KerML
  generation path, so UML/Core/SysML/RAAML stay byte-identical
  (`tests/test_models_up_to_date.py` passes); the adapter emits the lowerValue so
  the rule fires for `direction`/`portionKind` but not `visibility` (which has a
  default).
- Grammar/parser/AST: a port-scoped-free `DIRECTION?` prefix on every usage
  (definitions are Classifiers, not Features, so they take none). Mapping sets
  `feature.direction`; export re-emits the prefix; the round-trip canonical form
  records direction as a separate entry so directed and undirected usages are
  distinct. The diagram label shows the prefix, and a direction property page
  edits it (undirected = the absent None state).

No support-matrix row changes status (direction is added to the existing
declaration-and-typing surface of every usage); the already-`supported` rows now
also cover direction.

#### Phase 8c -- Interface Definition / Usage Semantics -- DONE

Delivered the CONNECTION-LEVEL surface for InterfaceDefinition/InterfaceUsage.
They subclass ConnectionDefinition/ConnectionUsage (adding only derived
properties), so an interface reuses the connection machinery one definition kind
deeper:

- generated from the pinned XMI (added to the SysML seed; no new stored closure);
- grammar/parser/AST: `interface def I;` and `[<dir>] interface i [: I]
  [connect a to b];` -- typing, binary connector ends (Phase 9), and the
  direction prefix (Phase 8b) all via inheritance;
- mapping types an InterfaceUsage by an InterfaceDefinition (exact kind, so a
  plain ConnectionDefinition is mistyped) and resolves its ends with the shared
  connection-end machinery; export emits the interface keywords; the round-trip
  canonical form distinguishes interfaces from connections;
- validation: the connection-end rules (broken/non-feature/incomplete) already
  cover InterfaceUsage (it IS a ConnectionUsage);
- diagram: `InterfaceDefinitionItem` (box) and `InterfaceUsageItem` (line, reusing
  the connection line + connector via MRO), each registered so it wins over the
  inherited connection item; UI-edit: an InterfaceUsage type page listing
  InterfaceDefinitions (the inherited connection/part type pages defer) plus
  toolbox tools.

InterfaceDefinition/InterfaceUsage are held at `alpha`, NOT `supported`, on the
named dependency: interface-end PORT bodies (`interface def I { end : ~P; }`) and
flow semantics need definition-body grammar that no construct has yet. Only the
connection-level surface is proven.

### Phase 9 -- Connection End Semantics -- DONE

Delivered for the binary, non-chain endpoint surface: the grammar gained
`connection <name> [: <type>] connect <end> to <end>;`; the mapper resolves each
endpoint nearest-first to a feature and stores it as the connector's
`source`/`target` (broken/non-feature ends recorded and validated as
`broken-connection-end`); export emits the connect clause and the round-trip
canonical form carries the endpoint qualified names; and `ConnectionUsageItem` is
now a `LinePresentation` bound to `source`/`target` (head/tail), with a connector
that authors ends on connect while preserving the connection's own subject (no
duplicate). ConnectionDefinition and ConnectionUsage are promoted to `supported`.
Feature-chain endpoints (Phase 5e) and n-ary/unnamed forms remain follow-ups.

Complete actual connector endpoints:

- derive/model connector ends faithfully from KerML/SysML semantics;
- parse and export connection syntax with endpoints;
- ensure diagram connection views bind to semantic connector/end state rather
  than only declaration typing;
- validate broken or mismatched endpoints.

Scope limitation (endpoint references): connector ends are limited to
simple-name and qualified-name references resolvable by the Phase 5 resolver
(e.g. `connect a to b`, `connect A::a to B::b`). Feature-chain endpoints
(e.g. `connect a.b to c.d`) depend on Phase 5e (Feature Chains) and are an
explicit extension scheduled with 5e, not part of this phase -- so Phase 9 does
not need 5e to land first.

Exit (reached): ConnectionDefinition and ConnectionUsage promoted from `alpha`
for the non-chain endpoint surface (feature-chain endpoints follow with Phase 5e).

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
- add generic generated-metamodel multiplicity validation for conceptually
  single-valued stored references that are emitted as `relation_many` at runtime
  (for example `FeatureTyping.type`/`typedFeature`,
  `Specialization.general`/`specific`, and other `0..1` or `1..1` ends), so
  API-mutated or hand-edited models with appended extra targets are reported
  instead of accepted by first-value helpers;
- run full suite plus focused SysML2 tests before final support claims.

Exit: final claims are backed by local and CI verification with no known
environment-only ambiguity.

## Execution Status And Order

This roadmap is the planning source of truth. `DONE` means committed and
reviewed against the phase gate; work present only in the dirty worktree is not
counted here.

1. Phase 0 -- Scope Reset And Audit Cleanup -- DONE
2. Phase 1 -- KPAR Artifact Baseline -- DONE
3. Phase 2 -- KPAR Reader Core -- DONE
4. Phase 3a -- KPAR Import Design Contract -- DONE
5. Phase 3b -- Minimal Normative Library Import -- DONE
6. Phase 3c -- General User KPAR Import -- DONE
7. Phase 3d -- GUI KPAR Import -- DONE
8. Phase 4 -- AttributeUsage Promotion -- DONE
9. Phase 5 -- Deeper Name Resolution (Enclosing-Namespace Lookup) -- DONE
10. Phase 9 -- Connection End Semantics -- DONE
11. Phase 8a -- Port Conjugation -- DONE
12. Phase 8b -- Flow Direction -- DONE
13. Phase 8c -- Interface Definition / Usage Semantics -- DONE
14. Phase 6a -- Constraint Expression Bodies -- DONE
15. Phase 6b -- Requirement Parameters -- DONE
16. Phase 6c -- Lightweight Requirement Parameters (`reqId`, `actor`, `stakeholder`) -- DONE
17. Phase 6d -- Framed Concern And the Concern Construct (6d-1 DONE; 6d-2 PLANNED)
18. Phase 7 -- Action Semantics -- PLANNED
19. Phase 5a -- Imports, Imported Memberships, Visibility & Ambiguity -- PLANNED
20. Phase 5b -- Aliases -- PLANNED
21. Phase 5c -- Inherited Members -- PLANNED
22. Phase 5d -- Implicit Specialization -- PLANNED
23. Phase 5e -- Feature Chains -- PLANNED
24. Phase 10 -- General KPAR Export And Round-Trip -- PLANNED
25. Phase 11 -- Versioned Spec-Ingestion Pipeline -- PLANNED
26. Phase 12 -- SysML v2 API Alignment -- PLANNED
27. Phase 13 -- CI And Release Hardening -- PLANNED

Rationale: the project now intentionally resolves KPAR import architecture
before standard-library/value-type promotion. Phase 3a prevents import identity,
storage, read-only, and partial-import policy from being decided accidentally.
Phase 3b proves that policy on the real normative library content needed for
`attribute x : Real`, and Phase 3c expands it to general user KPAR import. Deeper
resolution then becomes shared infrastructure for the remaining semantic work.
Connector ends and ports are closely related, so they should be addressed before
the larger expression/action behavior phases. Requirement surfaces now continue
through 6b/6c/6d before action semantics, so Requirement rows do not promote
while named requirement work remains. KPAR export/round-trip follows after import
semantics exist. Spec-ingestion and CI hardening close the loop.

## Definition Of Done

The matrix is complete when every row's status is its honest maximum and every
`yes` cell has a conformance test, with any row that cannot reach `supported`
showing `alpha`/`internal-only` plus a documented, scheduled or explicitly closed
reason. Completion means no silent gaps, not every cell forced green.
