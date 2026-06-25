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
- Diagram support currently means manual subject-bound projection and UI editing
  for implemented constructs, not automatic diagram generation from imported
  text/KPAR content. Initial diagram synthesis and model-browser/UI grooming are
  now planned as Phase 13, after semantic/resolution work is stable and before
  final CI/release hardening.

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

### Phase 5a -- Imports, Imported Memberships, Visibility & Ambiguity -- DONE

Added `import` statements and `public`/`private` visibility, resolving names
through imported memberships and honouring visibility, with ambiguity diagnostics.
The existing Import/VisibilityKind/Membership.visibility metamodel sufficed (no new
classes; kernel stays 35):

- **grammar/AST/parser**: `[<vis>] import <QName> [::*] ;` (named element or the
  `::*` import-all of a namespace; `::*` is a single WILDCARD terminal so it does
  not collide with the `::` separator) plus a uniform `public`/`private` prefix on
  every member (and import), applied centrally in the `member` transformer;
- **mapping**: each import becomes a `kerml.Import` (isImportAll + visibility),
  its target resolved in phase 2 owned-members-only (so imports do not resolve
  through other imports); each member's `OwningMembership.visibility` is set from
  the prefix, defaulting to PUBLIC (the SysML member default; the generated default
  is private, so it is set explicitly);
- **resolution**: nearest-first now consults a scope's imports after its owned
  members -- a wildcard brings only the target namespace's PUBLIC members, a named
  import brings the element; an OWN member shadows an import, a nearer scope shadows
  a farther one; a name visible from MORE THAN ONE import (distinct targets) is
  reported `ambiguous-name` and does not bind;
- **export/round-trip/persist**: import statements and the `private` member prefix
  re-emit; canonical records Import and private-member-visibility entries. A
  persistence-robust `is_import_all` helper normalizes the boolean `isImportAll`
  (it reloads from `.gaphor` as a string).

OUT of scope (deferred): transitive re-export through `public` imports (a public
import is recorded but its names are not re-resolved across import chains),
recursive imports (`::**`), and import aliases.

Exit: imported names resolve with visibility and ambiguity reporting -- done and
tested (`test_imports_visibility.py`). No support-matrix cell moves (resolution is
deepened for already-supported constructs).

### Phase 5b -- Aliases -- DONE

Added `alias` declarations and resolution of a name through its alias to the
aliased element. The existing Membership metamodel sufficed (no new classes;
kernel stays 35):

- **grammar/AST/parser**: `[<vis>] alias <Name> for <QName> ;`, sharing the
  uniform `public`/`private` member prefix (default public);
- **mapping**: an alias becomes a NON-owning `kerml.Membership`
  (`memberName` = the alias, `memberElement` = the referenced target, NOT owned),
  its target resolved in phase 2 with the same import-aware, nearest-first rule as
  a typed usage. Aliases resolve AFTER imports and BEFORE typed usages, and are
  iterated to a fixpoint so alias-to-alias chains settle regardless of declaration
  order; an alias target visible from more than one import is `ambiguous-name`;
- **resolution**: `owned_member_named` matches an alias by its alias name and
  returns the foreign element it references, so a name bound by an alias resolves
  wherever the alias is in scope (a usage typed by the alias name, a wildcard
  `import <ns>::*` that re-exports a public alias, an alias targeting an imported
  name);
- **validation**: `unresolved-alias` (an alias whose target never resolved;
  suppressed when the target was ambiguous, so no double report), and
  duplicate-name now counts alias names (an alias colliding with an owned member or
  another alias is a duplicate);
- **export/round-trip/persist**: an alias re-emits as `alias <name> for <path>;`
  (rendered from the membership, NOT by re-rendering the foreign target; `private`
  prefixed when private); canonical records an Alias entry; the non-owning
  membership + memberName + visibility survive save/reload.

`members()` is scoped to OWNING memberships so an alias's foreign target is not
mistaken for one of the namespace's own members (a no-op for all prior cases,
where every membership already owns its member).

OUT of scope (deferred): aliases inside action bodies are not fingerprinted by
round-trip (consistent with the existing visit, which recurses only into
packages); a NAMED import of an alias (`import <ns>::E`) imports the underlying
element under its real name, not the alias name.

Exit: an alias resolves to its target wherever the target would resolve -- done
and tested (`test_aliases.py`). No support-matrix cell moves (resolution is
deepened for already-supported constructs).

### Phase 5c-1 -- Subclassification, Definition Bodies, Subsetting, And Inherited Members -- DONE

Resolve members inherited through specialization (a member reachable via a
supertype). Added the prerequisite authoring surface (definition bodies +
subclassification) and the inheritance-resolution contract. One new kernel class:
`Subclassification` (kernel 35 -> 36).

- **metamodel**: seeded `Subclassification` (the KerML Specialization between
  Classifiers) from the pinned XMI and regenerated; it redefines general/specific
  as the stored `superclassifier`/`subclassifier` ends (like Subsetting's ends);
- **grammar/AST/parser**: `part def Name [:> Super, ...] ( ; | { <members> } )` --
  a definition may specialize supertypes (`:>`, the KerML specializes/subsets
  token) and carry a body of nested members; and `part x [: T] [:> y] ;` -- a usage
  may SUBSET an existing feature. The body reuses the shared `member` list;
- **mapping**: a `:> Super` becomes a Subclassification (`owner_is_type=True` owns
  body features via FeatureMembership, nested definitions via OwningMembership, like
  an action body); a `:> y` becomes a plain Subsetting. Both targets resolve in
  phase 2 with the import-aware resolver; subclassifications resolve BEFORE the
  member passes so inheritance is visible;
- **resolution**: `_resolve_type` now consults INHERITED members at a Type scope --
  KerML local order is owned, then inherited (through supertypes, transitively,
  cycle-guarded), then imported, and that whole local scope shadows an enclosing
  namespace. Private members are NOT inherited. So a usage typed by an inherited
  nested definition AND a usage subsetting an inherited feature both resolve;
- **validation**: `unresolved-specialization` (a `:> Super` that is not a Classifier)
  and `unresolved-subsetting` (a `:> y` that is not a Feature); an ambiguous
  supertype/subsetted name is reported `ambiguous-name` instead (no double report);
- **export/round-trip/persist**: a `part def` re-emits its `:> Super, ...` and body;
  a usage re-emits `:> y` (an own/inherited target by bare name, else path); the
  canonical form gained `Subclassification` and `Subsetting` entries and recurses
  into part-def bodies; the heritage links and body survive save/reload.

OUT of scope (deferred): subclassification/bodies on non-part definitions
(attribute/port/connection/interface), feature-chain references (5e), and
Redefinition (`:>>`), which is now explicit Phase 5c-2. Round-trip still does
not recurse into ACTION bodies (unchanged from Phase 7); only part-def bodies
are fingerprinted.

Exit: inherited members resolve from a specializing type -- done and tested
(`test_inherited_members.py`). No support-matrix construct cell moves (resolution
is deepened for already-supported constructs; PartDefinition/PartUsage stay
`supported`).

### Phase 5c-2 -- Redefinition -- DONE

Added the canonical KerML Redefinition surface on top of inherited-member
resolution. One new kernel class: `Redefinition` (kernel 36 -> 37).

- **metamodel**: seeded `Redefinition` (the KerML Subsetting that redefines an
  inherited feature) from the pinned XMI and regenerated; it redefines
  subsetted/subsetting as the stored `redefinedFeature`/`redefiningFeature` ends;
- **grammar/AST/parser**: `part x [: T] [:> y] [:>> z] ;` -- `:>>` (a 3-char token
  that lexes before the 2-char `:>`) redefines an existing feature; `PartUsage`
  gains `redefines`;
- **mapping**: `:>>` becomes a `kerml.Redefinition`; the Phase 5c-1 subclassification
  / subsetting behaviour is unchanged;
- **resolution**: the redefined feature resolves through owned/inherited/imported
  scopes EXCLUDING the redefining feature itself (`_resolve_type(..., exclude=)` /
  `owned_member_named(..., exclude=)`), so a bare `:>> x` on a feature named `x`
  redefines the INHERITED `x`. A redefining feature gives the type its own member,
  which shadows an inherited-name conflict -- so a conflict that is `ambiguous-name`
  when merely inherited (5c-1) is RESOLVED by redefining one supertype's feature
  (`:>> A::x`); a bare `:>> x` over a genuine conflict stays ambiguous;
- **validation**: `unresolved-redefinition` (mapping context: `:>> z` not a Feature)
  and model-derived `broken-redefinition` (a persisted/API-mutated Redefinition with
  no `redefinedFeature`), so no first-value helper silently accepts a broken one;
- **export/round-trip/persist**: emits `:>>` (a redefined own/inherited target by
  bare name via the resolver-mirrored `exclude`, else path); the canonical form
  gained a `Redefinition` entry; `:>>` survives `.gaphor` save/reload, and the
  multi-supertype-conflict-resolved case round-trips.

OUT of scope (deferred): redefinition on non-part usages and in non-part-def
definition bodies; multiplicity/type-conformance checks between a redefining and
redefined feature (a redefinition currently requires only that the target is a
Feature).

Exit: a usage can faithfully redefine an inherited feature, inherited conflicts are
diagnosed unless explicitly resolved, and Redefinition participates in
validation/export/round-trip without silent model drift -- done and tested
(`test_redefinition.py`).

### Phase 5d -- Implicit Specialization -- DONE

Applied the KerML UNIVERSAL-ROOT implicit specialization (the chosen scope; per-kind
Systems-Library bases such as `Parts::Part` are deferred to the library-import
phase, since we currently load only ScalarValues). No new kernel class -- reuses
Subclassification/Subsetting (5c) and the read-only-proxy pattern (the value-type
proxies, Phase 4):

- **mechanism**: a mapping pass (last, after all explicit resolution) gives every
  definition (Classifier) with no explicit subclassification an implicit
  `:> Anything`, and every usage (Feature) with no explicit feature-specialization
  (Subsetting / ReferenceSubsetting / Redefinition) an implicit `:> things`. The two
  bases are read-only proxies materialized at the model root (`Anything`, a bare
  Classifier; `things`, a bare Feature), one each per root, recognized by
  `kk.is_implicit_base`;
- **suppression**: a DECLARED `:>`/`:>>` -- even one that did not resolve -- suppresses
  the implicit base (tracked by element id from the phase-2 lists), so a broken
  `:> Missing` keeps its `unresolved-specialization` error instead of being masked by
  a root;
- **invisible + non-referenceable**: the bases are filtered from export and the
  round-trip canonical form (`kk.explicit_supertypes` / `explicit_subsettings`, and
  `visit` skips all library proxies) and skipped in name resolution and
  duplicate-name counting (`kk.is_library_proxy`), so `Anything`/`things` are never
  written, never user-resolvable, and never collide;
- **participation + persistence**: the implicit specialization is a real stored
  Subclassification/Subsetting, so it shows up in `supertypes()`/`subsettings()`, is
  traversed by inherited-member resolution, and survives `.gaphor` save/reload.

OUT of scope (deferred): per-kind Systems/Kernel-Library bases (PartDefinition ->
Parts::Part, etc.) and their inherited members -- the universal root has no members,
so the payoff here is structural, not member-inheritance, pending broad library
import.

Exit: implicit specializations participate in resolution per the (universal-root)
spec, and are invisible to text -- done and tested
(`test_implicit_specialization.py`). No support-matrix construct cell moves.

### Phase 5e -- Feature Chains -- DONE

Added feature-chain CONNECTOR ENDPOINTS (`connect a.b to c.d`, + succession
`first/then`, flow `from/to`) -- the chosen scope, the explicit extension deferred
by Phase 9's non-chain endpoints. One new kernel class: `FeatureChaining` (kernel
37 -> 38).

- **metamodel**: seeded `FeatureChaining` (a Relationship whose target,
  `chainingFeature`, is one of the chain feature's ordered steps; `featureChained`
  the derived source) and regenerated;
- **grammar/AST/parser**: `connection_end: qualified_name ("." NAME)*` -- a `.`-chained
  endpoint becomes `ast.FeatureChain(head, rest)`, distinct from the `::` namespace
  separator; a plain endpoint stays a tuple;
- **resolution**: a chain resolves step-by-step -- the HEAD nearest-first (imports
  included), then each `.step` as a member of the previous feature's TYPE (own member,
  else its SOLE inherited member). A resolved chain becomes a synthesized anonymous
  Feature owning an ordered FeatureChaining per step, owned by the connector and set
  as its source/target. The chain feature is created only after BOTH ends resolve, so
  a half-broken connection leaves no orphan and the ends stay atomic; a step that does
  not resolve is reported `broken-connection-end`;
- **invisible as a user member**: the synthesized chain feature gets no implicit base
  (`is_feature_chain` skip in the 5d pass), is not exported as a member, and is
  recognized by `kk.is_feature_chain`;
- **validation**: model-derived `broken-feature-chain` (a FeatureChaining whose
  chainingFeature was cleared);
- **export/round-trip/persist**: a chain endpoint renders as the dotted path `a.b.c`
  (head by the usual endpoint rule, then each step's simple name); the canonical form
  fingerprints a chain endpoint by its chaining features' qualified names (not the
  anonymous chain feature); chains survive `.gaphor` save/reload.

OUT of scope (deferred): feature chains in non-endpoint positions (typing /
subsetting / redefinition targets), and FeatureChainExpression (expression-level
chains).

Exit: feature chains resolve along their feature types and feature-chain connector
endpoints work -- done and tested (`test_feature_chains.py`). The
SuccessionAsUsage/FlowUsage/ConnectionUsage/InterfaceUsage rows gain feature-chain
endpoints (no status change).

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

##### Phase 6d-2 -- Framed-Concern REFERENCE form -- DONE

- `frame <existing>` references an already-declared concern (rather than declaring
  a new ConcernUsage). Faithfully it owns an anonymous ConcernUsage that SUBSETS
  the referenced concern via a `ReferenceSubsetting`; `ReferenceSubsetting ->
  Subsetting -> Specialization` were added to the kernel from the pinned XMI (the
  one new KERNEL footprint; kernel 31 -> 33). The grammar disambiguates by the
  `concern` keyword (declare: `frame concern ...`; reference: `frame <name>`); the
  mapper resolves the reference nearest-first to a ConcernUsage and links it with a
  ReferenceSubsetting (`kerml_kernel.add_reference_subsetting`), recording a name
  that does not resolve to a ConcernUsage (missing or wrong-kind) for the
  `broken-frame-reference` rule; export re-emits `frame <name>;`, the round-trip
  canonical form distinguishes the two forms by the referenced qualified name, and
  an unresolved reference is reported (not re-emitted as invalid text, mirroring an
  unresolved usage type / connect clause).

Exit: all named requirement surfaces (`subject`, `assume`, `require`, `reqId`,
`actor`, `stakeholder`, and `framedConcern` in both declare and reference forms)
plus the Concern construct are implemented and tested. At this point
RequirementDefinition and RequirementUsage can be considered for promotion out of
`alpha`, subject to the normal nine-cell support rule and the remaining
expression-semantics limits.

### Phase 7 -- Action Semantics -- DONE (bounded; rows stay `alpha`)

Delivered the action behavior surface (the four ROADMAP bullets), grounded in the
pinned XMI and the Sensmetry pilot's normative action body:

- **action bodies and nested steps** -- `action def A { ... }` / `action a [: T]
  { ... }` reuse the shared `member` grammar, so a body holds nested action steps
  and any other usage. An action IS a Type, so body members are owned PER KIND:
  usages (Features) via FeatureMembership; nested definitions/packages (non-features)
  via ordinary OwningMembership -- a FeatureMembership never points at a non-feature
  (model-derived `broken-feature-membership` guards it);
- **action parameters** -- directed (`in`/`out`/`inout`) nested usages in the body
  (reusing the Phase 8b direction support; e.g. `in attribute t : Real;`);
- **succession and flow** -- `succession [name] first <end> then <end>;` ->
  SuccessionAsUsage and `flow [name] from <end> to <end>;` -> FlowUsage, binary
  connector usages whose ends reuse the connection-end resolution. New metamodel:
  KerML Succession + Flow (kernel 33 -> 35) and SysML SuccessionAsUsage + FlowUsage;
- **coverage** -- validation (the connection-end integrity rules now cover ALL
  ConnectorAsUsage, so succession/flow ends are guarded; unresolved ends reported),
  export, round-trip (the canonical form now recurses into action bodies and
  fingerprints succession/flow with their ends), persistence, and diagram
  PROJECTION (line items for succession/flow, mirroring the connection line; action
  boxes for bodies). NOTE: succession/flow are `UI-edit=no` -- projection/drop only,
  not the toolbox create-tool + property-page edit `UI-edit=yes` requires (the
  interactive connect adapter for their ends is deferred).

OUT of scope (documented; rows stay `alpha`): the advanced action nodes
(`if`/`while`/`for`/`fork`/`join`/`merge`/`decision`, `accept`/`send`/`assign`/
`terminate`, `perform`), the chained `first/then`-only flow form, `flow def`
(needs KerML Interaction), item usages, and `of`-item flow payloads.

Exit: bodies/steps, directed parameters, succession, and flow are implemented and
tested end to end. ActionDefinition/ActionUsage STAY `alpha` (under-claim): the
advanced action-node surface above is unimplemented, so the construct is not yet
complete; promotion waits until that surface lands.

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

### Phase 10 -- General KPAR Export And Round-Trip -- DONE

Added the KPAR WRITER (the inverse of import) and proved interchange round-trips.
SINGLE-MEMBER layout (the chosen scope): the whole model is exported to one
`.sysml` member via the textual exporter, with `.project.json`/`.meta.json` and the
member packaged as a KPAR -- the same layout `read_kpar`/`import_user_kpar` consume.

- **writer**: `kpar.write_kpar(path, root, *, project_name, version, description)`
  serializes the model with `export_namespace` and zips a single project directory;
  `.meta.json` indexes each REAL top-level member name to the member (library proxies
  -- value types, the implicit `Anything`/`things` -- and anonymous members are
  omitted, since the text exporter already omits them and a synthesized chain feature
  is owned by its connector, not top-level);
- **CLI**: `sysml2-kpar-export <model.gaphor> <out.kpar> [--name]`, symmetric with
  `sysml2-kpar-import` / `sysml2-kpar-info`;
- **round-trips (by canonical form, not byte-identity)**:
  - `.gaphor` SysML2 model -> KPAR (a saved/reloaded model writes a valid archive);
  - `KPAR -> Gaphor -> KPAR -> Gaphor` is canonical-form stable;
  - `text -> Gaphor -> KPAR -> Gaphor` preserves the canonical form AND re-exports
    identical text;
  - the two CLIs compose (export then import back to a `.gaphor`);
- **identity/provenance rules** documented in the writer module and
  `KPAR_IMPORT_CONTRACT.md`: read-only proxies / chain features are never written;
  interchange round-trips semantically (canonical form), since member naming and
  ordering are the writer's choice; provenance on re-import traces to the single
  exported member (the original per-source-file provenance of an imported KPAR is
  not preserved across the single-member export).

OUT of scope (deferred): per-source-file (multi-member) export preserving original
file boundaries / per-file provenance; KPAR `usage`-dependency export.

Exit: KPAR support is complete for the implemented SysML2 surface (export +
round-trip, not just stdlib ingestion) -- done and tested (`test_kpar_export.py`).

### Phase 11 -- Versioned Spec-Ingestion Pipeline -- DONE

Added the future-spec machinery so a NEW OMG SysML/KerML release can be assessed
MECHANICALLY before any human mapping decision. It is maintainer tooling
(`gaphor/SysML2/codegen/spec_index.py`), surfaced as `poe` tasks (no user-facing
CLI); it reads the pinned XMI abstract syntax and never changes the model or the
generator.

- **metamodel index** (`index_xmi`): parses an OMG MOF XMI into a `MetamodelIndex`
  -- every class (name, abstractness, generalizations, owned properties with type /
  stored-vs-derived / attribute-vs-enum-vs-reference) and every enumeration's
  literals. A committed JSON BASELINE of each pinned XMI
  (`codegen/spec_baseline/*.index.json`) is the "current pinned" snapshot a new
  release is diffed against; a test (`test_committed_baseline_matches_live_xmi`)
  guards that the baseline still matches the live XMI -- the same regen discipline
  the generated code uses;
- **diff** (`diff_indexes`): added/removed classes, added/removed/changed
  properties, derived<->stored flips, type/kind changes, and added/removed
  enumerations and literals;
- **fail-fast review report** (`review_findings`): turns a diff into REVIEW (needs a
  human mapping decision) vs INFO findings. The central rule -- a NEW STORED
  REFERENCE needs an ownership policy: it cascades on delete only if listed in
  `xmi_adapter.COMPOSITE_REFS` (the containment whitelist), which a new reference is
  NOT, so it is always flagged. Also flags new/removed classes, removed properties,
  derived<->stored flips, type changes, and removed enumerations/literals;
- **provenance/hash refresh** (`compute_manifest_rows`): SHA-256 + byte size for each
  pinned artifact (XMI/KPAR), to refresh the manifest table when bumping the pin;
- **workflow (no arguments)**: pin a new XMI (replace the file), run
  `poe sysml2-spec-diff` to diff the committed baseline against the live XMI and get
  the review report (NON-ZERO exit on a blocking finding), make the mapping
  decisions, then run `poe sysml2-spec-index` to accept the new version (regenerate
  the baseline). `poe sysml2-manifest-refresh` prints fresh hashes.

The diff/review logic is exercised with small synthetic XMI version pairs
(`test_spec_index.py`); the baseline drift guard and the hash-refresh tool are
checked against the real pinned artifacts.

OUT of scope (deferred): diffing library KPAR CONTENT (the elements inside the
normative `.kpar` libraries) -- only the artifact set + hashes are tracked here;
auto-rewriting the manifest Markdown table (the tool prints rows to paste).

Exit: future OMG SysML/KerML releases can be assessed mechanically before human
mapping decisions -- done and tested.

### Phase 12 -- SysML v2 API Alignment

Decide and implement the SysML v2 API/client surface needed by Gaphor, if any:

- keep Gaphor's internal ids distinct from SysML/API-facing ids;
- add API-facing identity/export compatibility only where required;
- align diagnostics and interchange metadata with the formal API where it affects
  model compatibility.

Exit: API-related scope is either implemented and tested or explicitly closed
with a documented rationale.

### Phase 13 -- Diagram Synthesis And User-Facing UI Grooming

Turn the proven semantic import/projection machinery into an evaluator-friendly
workflow: imported text/KPAR content should produce useful initial diagrams and
the UI should present SysML2 concepts rather than generated metamodel plumbing.

This phase does NOT change the `Diagram=yes` meaning used earlier in the support
matrix: those cells prove that a construct can be projected as a subject-bound
diagram item. This phase is the product workflow on top of that foundation.

Work:

- model-browser grooming: hide, group, or de-emphasize internal implementation
  elements such as `FeatureTyping`, generated membership relationships,
  conjugation helper elements, library value-type proxies, and other relationship
  plumbing unless the user explicitly asks for an internal/debug view;
- diagram synthesis from imported or existing semantic content: create initial
  package/structure, requirement/concern, action/flow, port/connection, and
  interface-oriented diagrams for the implemented surface where the semantic
  model contains enough information;
- deterministic layout and routing heuristics good enough for human evaluation:
  stable placement, readable labels, relation lines anchored to their semantic
  endpoints, and no avoidable overlaps on normal-sized models;
- idempotency rules: importing or regenerating diagrams must not duplicate
  already-synthesized diagrams/items unless the user requests a new view;
- scope controls: let users choose whether to generate diagrams during text/KPAR
  import, generate them later from an existing model, or keep semantic import
  model-only;
- tests: headless synthesis tests proving subject binding, idempotency,
  persistence/reload, delete cascade, and representative layout invariants, plus
  focused GUI smoke tests for the generation entry point.

Exit: a human evaluator can import supported SysML2 text/KPAR content and get
useful initial diagrams without manually dragging every element, while every
generated diagram item remains a view of existing semantic model state.

### Phase 14 -- CI And Release Hardening

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
17. Phase 6d -- Framed Concern And the Concern Construct -- DONE (6d-1 + 6d-2)
18. Phase 7 -- Action Semantics -- DONE (bounded: bodies/steps, parameters, succession, flow; advanced nodes deferred; rows stay `alpha`)
19. Phase 5a -- Imports, Imported Memberships, Visibility & Ambiguity -- DONE
20. Phase 5b -- Aliases -- DONE
21. Phase 5c-1 -- Subclassification, Definition Bodies, Subsetting, And Inherited Members -- DONE
22. Phase 5c-2 -- Redefinition -- DONE
23. Phase 5d -- Implicit Specialization -- PLANNED
24. Phase 5e -- Feature Chains -- PLANNED
25. Phase 10 -- General KPAR Export And Round-Trip -- PLANNED
26. Phase 11 -- Versioned Spec-Ingestion Pipeline -- DONE
27. Phase 12 -- SysML v2 API Alignment -- PLANNED
28. Phase 13 -- Diagram Synthesis And User-Facing UI Grooming -- PLANNED
29. Phase 14 -- CI And Release Hardening -- PLANNED

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
semantics exist. Spec-ingestion and API alignment come before diagram synthesis
so the synthesized views are built on stable semantics. Diagram synthesis then
turns the semantic/projectable model into an evaluator-friendly workflow before
CI hardening closes the loop.

## Definition Of Done

The matrix is complete when every row's status is its honest maximum and every
`yes` cell has a conformance test, with any row that cannot reach `supported`
showing `alpha`/`internal-only` plus a documented, scheduled or explicitly closed
reason. Completion means no silent gaps, not every cell forced green.
