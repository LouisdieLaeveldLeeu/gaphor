# SysML v2 Mapping Decisions

## M0 Metamodel-Generation Finding

Sources checked:

- OMG SysML 2.0 specification page: https://www.omg.org/spec/SysML/2.0/About-SysML
- OMG KerML 1.0 specification page: https://www.omg.org/spec/KerML/1.0/About-KerML
- OMG final-adoption announcement: https://www.omg.org/news/releases/pr2025/07-21-25.htm
- Systems Modeling Community release repository: https://github.com/Systems-Modeling/SysML-v2-Release
- Systems Modeling Community releases: https://github.com/Systems-Modeling/SysML-v2-Release/releases

### What Gaphor Currently Generates From

Gaphor's current model-code pipeline generates Python model modules from checked-in Gaphor model files, not from arbitrary external Ecore, MOF XMI, or Eclipse XMI.

- `pyproject.toml` defines `poe` tasks that call `gaphor.codegen.coder:main`.
- `gaphor.codegen.coder` loads `.gaphor` model files through `gaphor.storage.load`.
- Current generated modules include `gaphor/core/modeling/coremodel.py`, `gaphor/UML/uml.py`, `gaphor/SysML/sysml.py`, `gaphor/RAAML/raaml.py`, and `gaphor/C4Model/c4model.py`.
- `tests/test_models_up_to_date.py` verifies generated output equals the checked-in generated modules.

This means M1a must prove an adapter path from normative SysML/KerML artifacts into the Gaphor generator's accepted model shape before the KerML kernel is built on it.

### Which SysML2 Artifacts Are Usable

Usable M0 inputs:

- OMG formal SysML 2.0 and KerML 1.0 specification documents for conformance authority.
- OMG normative MOF XMI for the SysML and KerML abstract syntax as metamodel source input.
- OMG normative KPAR artifacts for library/interchange import when that phase arrives.
- JSON schemas for abstract syntax and project interchange, mainly for future validation and API alignment.
- Systems Modeling Community release BNF files as parser seed material, cross-checked against the formal PDFs.
- Textual standard-library files in the release repository as readable fixtures and cross-checks, not as the sole conformance authority.

### Normative vs Reference Artifacts

Normative for this effort:

- OMG formal SysML 2.0 Language specification.
- OMG formal KerML 1.0 specification.
- OMG MOF XMI abstract syntax files for SysML and KerML.
- OMG KPAR model interchange projects listed as normative machine-readable documents.

Reference or convenience artifacts:

- Systems Modeling Community release repository packaging.
- Extracted `.kebnf`, `.kgbnf`, and HTML BNF files. They are derived from the specifications and useful for parser work, but must be checked against the formal docs when ambiguity or correction notes appear.
- Release repository XMI library representations using Eclipse XMI. Release notes state these are not fully normative OMG XMI.
- Pilot implementation behavior and Xtext grammar. These are useful comparators, not automatic conformance authority.

### Realistic Generator Path

Use a two-step generator strategy:

1. M1a imports a small normative MOF XMI slice into an intermediate mapping model and emits one generated, semantics-free Gaphor `Base` subclass with generated attributes and references.
2. Only after that generated class persists and reloads through `.gaphor`, extend the path to the minimal KerML kernel in M1b.

Do not hand-author the KerML or SysML metamodel as production code unless M1a proves the generation path unviable and a new human-approved plan replaces this decision.

### M1a Outcome (verified 2026-06-16): generator path is viable

The two-step path was proven end to end on one semantics-free class:

- `gaphor/SysML2/codegen/xmi_adapter.py` parses the normative `KerML.xmi` and emits a coder-ready `.gaphor` slice (`models/KerMLSlice.gaphor`) for KerML `Element` with two primitive attributes (`declaredName`, `isLibraryElement`) and one self-reference (`ownedElement`), generalized to Gaphor `Base` via the Core supermodel.
- Gaphor's own `gaphor.codegen.coder` generated `gaphor/SysML2/kerml_slice.py`: `class Element(_Base)` with `_attribute` properties and an `association`. No class body was hand-authored. Regenerable via `poe sysml2-slice-model` then `poe sysml2-slice`.
- `gaphor/SysML2/tests/test_m1a_generated_persist.py` confirms real persistence (not just import): the generated class is a `Base` subclass; the generated string attribute, bool attribute, and reference each persist and reload through `.gaphor` via `ElementFactory` + `storage`.

Note recorded for M1b: Gaphor's `attribute.load()` does not coerce a persisted value back to the declared Python type, so a generated `bool` reloads as the string `"True"`. This is shared framework behaviour (UML/SysML attributes behave the same), not a generator defect. M1b should decide whether KerML boolean attributes need typed accessors or validation-time coercion.

### M1b Outcome (verified 2026-06-16): minimal KerML kernel via the proven path

The kernel was built through the M1a generator path, scaled to a connected multi-class closure. Key design decisions (some correcting an initial over-broad first cut, after review):

- Derived vs stored. The XMI marks most class properties `isDerived=true` and carries no aggregation metadata. The adapter classifies every property: primitive non-derived -> `typeValue` attribute; enum non-derived -> enumeration; `uml:Class` non-derived -> stored reference; ANY derived property -> `DerivedAttribute`/`DerivedReference` metadata that is recorded for audit but NOT emitted as persisted structure; an unknown non-derived target type raises (fail-fast, invariant 8). Persisting derived features would create stale state that can disagree with the behaviour layer, so they are computed instead.
- Closure follows stored references only. Because derived references no longer extend the closure, the M1b minimal kernel was 12 classes (Element, Relationship, Namespace, Membership, OwningMembership, Type, Feature, Specialization, Import, Documentation, plus AnnotatingElement/Comment reached via Documentation). Classes previously pulled in only through derived references (FeatureMembership, Conjugation, Subsetting, ...) are correctly absent. (M2 later added Classifier/Class/Structure and FeatureTyping to the seed for the SysML supermodel and the typing relation, bringing the kernel to 16 classes — see the M2 Outcome section.)
- Containment is an explicit whitelist. With no aggregation in the XMI, composite (cascade-on-delete) is restricted to `COMPOSITE_REFS = {(Element, ownedRelationship), (Relationship, ownedRelatedElement)}` — the KerML containment spine. Every other stored reference (source, target, general/specific, memberElement) is plain non-owning and never cascades. Extend the whitelist only with a new tested mapping decision.
- Enumerations are value-domain types: `Feature.direction` (FeatureDirectionKind) and `Membership`/`Import.visibility` (VisibilityKind) generate as `enum.StrEnum` + `_enumeration(...)`, never folded into the class closure.
- Behaviour layer `gaphor/SysML2/kerml_kernel.py` computes the derived surface from the stored Relationship spine, ported from the normative XMI: `members`, `owned_elements`, `owning_namespace`, `qualified_name` (walks owners, joined by `::`), `resolve_qualified_name`, `imported_elements`. A derivation that is not yet implemented (`featuring_types`) raises rather than returning a misleading default. Because the XMI declares no opposite-end pairings, the member's `owningRelationship` back-pointer is set explicitly in `add_owned_member` (navigation, not inferred).

Tests (`test_m1b_kernel.py`, `test_kernel_adapter.py`): the five required behaviours each through `.gaphor` save/reload; a parametrized create->save->reload over every generated kernel class (12 at M1b, 16 after the M2 expansion); delete-direction tests pinning BOTH that the containment spine cascades AND that non-owning references (import target, specialization general/specific, membership member) do NOT; derived-exclusion audit (derived names classified as metadata and absent from `kerml.py`/`models/KerML.gaphor`); composite restricted to exactly the two whitelisted refs; fail-fast on a missing seed class; enum tests; determinism and freshness of `models/KerML.gaphor` and `gaphor/SysML2/kerml.py`.

Scope honesty: this is `Create-API`+`Persist` plus the five behaviours. There is no grammar/parse, text import, scoped validation, export, or round-trip yet; those are M2. The support matrix marks the kernel classes `internal-only`, never `supported`.

### M2 Outcome (verified 2026-06-16): PartDefinition/PartUsage vertical tracer

`part def Engine;` and `part vehicleEngine : Engine;` were driven through the entire chain, committed at each green sub-step:

- Text -> AST: a Lark grammar slice (`grammar/sysml2.lark`, `grammar/parser.py`) parses the two constructs to a small AST.
- AST -> semantic: `mapping.py` builds `sysml2.PartDefinition`/`PartUsage` (generated from SysML.xmi on the KerML kernel supermodel) owned by a root Namespace, with the usage typed by the definition via a KerML `FeatureTyping`. PartUsage is a `kerml.Feature`; PartDefinition's MRO runs through Structure/Class/Classifier/Type to Base.
- Persistence: the model save/reloads through `.gaphor` with the typing relation intact. The usage owns its FeatureTyping (containment spine), so deleting the usage cascades to the typing while the non-owning `type` target (the definition) survives; deleting the definition leaves usage and typing intact.
- Validation + resolution (scoped): four ERROR-class rules (missing-owner, duplicate-name, unresolved-import, usage-without-valid-type) with conformance severities; resolution is same-namespace + simple qualified-name only.
- Textual export: re-emits valid SysML (definition stays a definition, usage stays a usage, typing preserved), re-parseable by the grammar.
- Round-trip: `roundtrip.py` runs import -> validate -> save -> reload -> validate -> export -> re-parse and compares CANONICAL forms (kind + qualified name + resolved type name), never ids or raw text. Validation runs on both the source and the reloaded model, and the harness asserts the verdict survives persistence. PartDefinition/PartUsage are the first rows of the coverage metric. Preservation (canonical form) and validity (no errors) are reported separately: a duplicate-name model can round-trip structurally yet be invalid.
- Validation is model-derived: `usage-without-valid-type` is reported both from mapping context (an unresolvable declared type name) AND from the persisted model (a FeatureTyping with an empty `type`, e.g. after its definition is deleted), so a broken typing in a stored/mutated model is caught with no mapping state.
- CLI: `cli.py` wires the real pipeline -- `sysml2-validate` (parse+map+validate), `sysml2-import` (text -> .gaphor), `sysml2-export` (.gaphor -> text), `sysml2-round-trip` (canonical round-trip) -- so the CLI is a genuine path, not a stub.

Support matrix: PartDefinition and PartUsage advance to `alpha` with Parse/Import/Create-API/Persist/Validate/Export/Round-trip all `yes`; Diagram and UI-edit stay `no`. They are `alpha`, not `supported`, because resolution is minimal and the diagram/UI surface is unimplemented. The required deliverable is the CLI/Python round-trip (both work); diagram projection was deferred (optional stretch) and not built.

### Post-M2 Construct: Package / nested namespace (verified 2026-06-16)

The second vertical-tracer construct, chosen to strengthen scoping, qualified names, and round-trip without adding UI surface. `Package` is a KerML class (a `Namespace` subclass), added to the kernel seed (kernel now 17 classes); `package X { ... }` maps onto it and nests members and sub-packages through the existing `OwningMembership` containment spine -- no new ownership machinery. The grammar gained a recursive `package_definition`; the mapper builds the ownership tree in a first phase (so all names exist) then resolves typing in a second; export recurses with indentation; the canonical form recurses through packages, with each entry's qualified name (e.g. `Root::Outer::Inner::Engine`) encoding the full nesting path. Resolution gained a member-relative `resolve_in_namespace` for qualified names from the implicit root, distinct from the root-rooted `resolve_qualified_name`. Package advances to `alpha` (Parse..Round-trip yes; Diagram/UI no) and is the third coverage-metric row. Verified: nested packages persist/reload, qualified names span nesting through `.gaphor`, and the nested model round-trips canonically.

### Post-M2 Construct: AttributeDefinition / AttributeUsage (verified 2026-06-17)

The third construct, chosen as a new definition/usage axis on a different KerML base. `AttributeDefinition` generalizes KerML `DataType` (added to the kernel seed; kernel now 18 classes) and `Definition`; `AttributeUsage` generalizes `Usage` (so it is a `Feature`, like `PartUsage`). Both were added to the SysML seed and generated through the same supermodel path; `DataType` is the only new KerML root needed (Class/Classifier/Structure/Feature already present). The grammar gained `attribute def <name>;` and `attribute <name> [: <type>];`; the AST, mapper, export, and canonical form were extended in parallel with the part forms (export's usage rendering was factored into a shared `_usage_decl` that serves Part and Attribute usages). Typing reuses the FeatureTyping containment spine unchanged. Scope note: AttributeUsage is typed here by an AttributeDefinition; the distinct primitive/value-type axis (`attribute x : Real`) is deliberately deferred -- this proves the attribute definition/usage pattern on a DataType base, not full value-type semantics. AttributeDefinition and AttributeUsage advance to `alpha` and are the 4th/5th coverage-metric rows. Verified: attribute def/usage round-trips, including attribute-in-package cross-package typing (`attribute m : Units::Mass`).

### Diagram projection core: PartDefinitionItem (verified 2026-06-17)

The first diagram surface, kept to the projection core per invariant 4 (a diagram item is a view onto a semantic element, never storage). `PartDefinitionItem` is an `ElementPresentation[PartDefinition]` (a named box) declared via `@represents(sysml2.PartDefinition)`; a `drop` handler (`@drop.register(sysml2.PartDefinition, Diagram)`) projects an EXISTING PartDefinition by `diagram.create(item)` then `item.subject = element` -- there is no symbol-only creation path. A new `gaphor.modules` entry point (`gaphor.SysML2.uicomponents`) imports the item/drop modules so their decorators register at startup. The SysML2 modeling language's `lookup_element` now also resolves the `diagramitems` module so persisted presentations (saved under the single `SysML2` ns, like all gaphor.SysML2 classes) reload.

Scope and claim: `Diagram=yes` for PartDefinition is the projection core only -- project existing element, subject bind, persist/reload of the view->element link, and cascade-delete of the view when the element is unlinked -- all tested headless (`test_diagram_projection.py`). It is NOT toolbox creation or in-diagram editing, so `UI-edit` stays `no`. The GTK rendering/toolbox/property-page surface remains deferred; the design constraint (project-existing-element-only) is what was in scope and is proven.

### Diagram projection extended: PartUsage + FeatureTyping line (verified 2026-06-17)

PartUsage now projects as a box item exactly like PartDefinition (`PartUsageItem`); `Diagram=yes` for PartUsage on the same projection-core terms.

The FeatureTyping relation projects as a line (`FeatureTypingItem`, a `LinePresentation` with `@represents(kerml.FeatureTyping, head=typedFeature, tail=type)`). The drop handler creates the line only when BOTH ends are already projected, binds `subject` to the EXISTING typing, then connects the line's handles to the endpoint items. The default gaphas relationship connector (`MetadataRelationConnect`, registered for ElementPresentation/LinePresentation) establishes the subject via `relationship_or_new` -- find-or-CREATE -- which duplicated the FeatureTyping on connect (observed 1->2). The fix is `FeatureTypingConnect` (`gaphor/SysML2/connectors.py`), registered more specifically for `(ElementPresentation, FeatureTypingItem)` so it wins by MRO; it overrides `connect_subject` to KEEP the line's existing subject instead of find-or-create. Result: the typing line is now a fully visually-wired view -- handles anchored to both endpoint items, subject is the existing typing, no duplicate, persists/reloads, cascade-deletes. `connectors` is imported by `drop` and `uicomponents` so the connector registers on both the dispatch and startup paths.

Registration-bug fix found here: `gaphor.SysML2.drop` now imports `gaphor.SysML2.diagramitems` directly. Previously the `@represents` registrations only happened if something imported `diagramitems` (the `uicomponents` entry point, or a test), so the dispatch path could reach `drop` with an empty item registry and silently return `None`. The earlier PartDefinition drop test passed only because that test imported the item class explicitly. The dependency is now explicit so the drop handlers always find their items.

### Deferred: versioned spec-ingestion pipeline (post-M2)

The adapter already produces a normalized in-memory IR (`Kernel`: classes, properties, target kind, derived/stored, composite, enum literals) and applies a reviewed mapping policy (`COMPOSITE_REFS`; derived-refs-computed-in-behaviour-layer; fail-fast on unknown non-derived targets). A natural extension is a full versioned spec-ingestion pipeline for future OMG XMI releases:

- emit a machine-readable metamodel index (e.g. `docs/sysml-v2/generated/KerML_INDEX.json`): class/property name, target kind, derived/stored, composite, enum literals, multiplicity, source XMI id;
- on a new artifact: re-verify provenance/hash, parse to IR, diff against the previous IR, regenerate, and produce a review report; fail the build on an unknown mapping change (e.g. a new non-derived class reference with no ownership policy).

Decision (2026-06-16): defer this to a named post-M2 phase rather than build it now. The corrective part it was meant to enforce (derived/composite/fail-fast) already shipped in M1b. M2's validation/resolution is deliberately scoped to concrete same-namespace + simple qualified-name resolution and four named structural rules — it does not consume a metamodel index — so the index is not load-bearing for M2 and building the diff/fetch/upgrade machinery now would be speculative ahead of an actual spec release. Boundary to preserve when built: automatic = structural extraction, generated classes, index, deterministic diffs; human-reviewed = semantic behaviour, ownership policy, compatibility/migration, support-matrix claims.

## Grammar Tool

Decision: use Lark for the first SysML v2 textual grammar.

Tradeoff:

- Lark is pure Python, fits Gaphor packaging better, supports EBNF-style grammar composition, and is simple to exercise in pytest.
- ANTLR tracks the broader tooling ecosystem more closely and has a mature grammar workflow, but adds a Java-oriented toolchain and generated parser lifecycle that is heavier for Gaphor.

The grammar is one layered grammar: SysML textual notation extends KerML textual notation. Port from the BNF, not from intuition. Pilot/Xtext behavior may be used to understand ambiguities, not as the source of truth.

Lark is declared as a core dependency in `pyproject.toml` (`lark>=1.1,<2`, locked to 1.3.1 on 2026-06-16). It is a core dependency rather than an optional extra because SysML2 is registered as a first-class modeling language and is auto-loaded like UML/SysML/C4Model; a base install without it would fail once the parser layer imports `lark`. Being pure Python, Lark adds no build/ABI burden. The M2 grammar layer now imports it through `gaphor/SysML2/grammar/parser.py`.

## Spec Version Pin

Pin to:

- SysML 2.0 formal, September 2025.
- KerML 1.0 formal, September 2025.
- Systems Modeling API and Services 1.0 formal only for identity/API alignment notes, not implementation in this kickoff.
- OMG `20250201` machine-readable artifacts for SysML and KerML abstract syntax and library KPARs.
- Systems Modeling Community release tag `2026-03` as the current convenience bundle for formal documents, BNF extraction files, and reference libraries.

The checked-in MOF XMI abstract-syntax inputs for M1a are under `docs/sysml-v2/omg/20250201/`:

- `KerML.xmi` from `https://www.omg.org/spec/KerML/20250201/KerML.xmi` (`ptc/25-04-04`).
- `SysML.xmi` from `https://www.omg.org/spec/SysML/20250201/SysML.xmi` (`ptc/25-02-15`).

Update policy: changing the pin requires a mapping decision update, support-matrix review, and focused regression fixtures for affected grammar, metamodel, library, and round-trip behavior.

## Test Environment

Decision: the canonical, reproducible test environment is a committed Docker image (`docker/Dockerfile`) based on Ubuntu 25.10, running `poetry run pytest` against `poetry.lock`. Both CI and local development run this image, so "verified" means the same thing everywhere. `poetry.lock` is the source of truth for Python dependencies; the image is the source of truth for the system runtime.

Rationale and rejected alternatives:

- Gaphor's UI import chain (`gaphor/conftest.py` -> `gaphor.ui`) requires libadwaita >= 1.8 and GtkSource 5. The development host is Ubuntu 24.04 LTS, capped at libadwaita 1.5.0, so the host Poetry venv cannot collect tests.
- Of the bases checked on 2026-06-16, only Ubuntu 25.10 cleared the floor (libadwaita 1.8.0, GTK 4.20, PyGObject 3.50, GtkSource 5.16). Fedora 41 (1.6.10) and Fedora 42 (1.7.12) were too old.
- Rejected: pip-installing pytest into the installed Flatpak Gaphor runtime. It worked as a one-off smoke check but is not a valid foundation: the test deps would live in unpinned, mutable `~/.var/app` user-site state outside `poetry.lock`, resolved against a different Python (3.13) than the lockfile, and a Flatpak update can discard it. It splits the dependency source of truth and is not reproducible across machines or CI.
- Rejected (as a requirement): upgrading the host OS to Ubuntu 26.04. It would fix the Poetry path natively but is not reproducible across a team and is not needed once the image exists.

The image also supports interactive GUI launch (`docker/run-gui.sh`, X11 socket passthrough) as a convenience, but GUI interaction is not the foundation: correctness is proven headless via `docker/run-tests.sh` (xvfb), exactly as Gaphor's own CI runs GUI-dependent tests. This is consistent with the invariant that diagrams/GUI come last.

Verified 2026-06-16: the image builds, the full suite collects (2430 tests), the four M0 SysML2 CLI tests pass, and a core ElementFactory slice passes.

## Element Identity

Repository identity uses Gaphor's native `Base.id` and `ElementFactory` ownership of elements.

Do not introduce a parallel repository id. Add a SysML/API-facing `elementId` only when API or export compatibility requires it. Round-trip equivalence never depends on either Gaphor ids or imported textual ids.

Keep these identities distinct:

- Gaphor internal `Base.id`.
- SysML/API-facing `elementId`, if introduced later.
- Text import ids minted during import.
- Canonical round-trip identity, based on structure and resolved references.

## Round-Trip Equivalence

Round-trip equivalence is canonical structural comparison over:

- element types,
- ownership tree,
- memberships,
- typing and specialization relations,
- references resolved to their target by canonical path,
- documentation,
- qualified names.

It explicitly excludes text formatting and Gaphor element id equality.

## Name Resolution Target Design

Full target:

- unqualified lookup through owner namespaces,
- simple and nested qualified-name lookup,
- imports,
- inherited members,
- visibility,
- aliases,
- nested namespaces,
- implicit specialization,
- feature chains,
- diagnostics for ambiguous and unresolved names.

M2 scope only:

- same-namespace lookup,
- simple qualified-name lookup,
- unresolved-symbol diagnostic.

Do not implement inheritance, visibility, aliases, or feature chains during the first tracer.

## Former Z2a Blocker: standard model libraries are KPAR-only (recorded 2026-06-18)

The formerly named Phase Z2 (read-only standard-library loader) would promote
AttributeUsage to `supported` by resolving `attribute x : Real` against the
normative value-type library. Per the earlier plan, Z2a was to come first: pin
the real OMG model libraries, hash them, document provenance, and add existence
tests for Real/String/Boolean/Integer/ScalarValues -- with the explicit rule "if
the library files cannot be located or are not published in a stable release
bundle, pause and document the blocker rather than fall back to a curated
subset."

Finding (verified 2026-06-18 against the OMG About pages for the pinned 20250201
release): the standard model libraries are published **exclusively as `.kpar`
archives**, with no XMI or plain-text `.kerml`/`.sysml` form:

- KerML: `Semantic-Library.kpar` (ptc/25-04-17), `Data-Type-Library.kpar`
  (ptc/25-04-18, defines Real/String/Boolean/Integer), `Function-Library.kpar`
  (ptc/25-04-19).
- SysML: `Systems-Library.kpar` (ptc/25-04-24) and six domain libraries
  (Analysis, Cause-and-Effect, Geometry, Metadata, Quantities-and-Units,
  Requirement-Derivation), all `.kpar`.
- The only plain-text artifact in the release is an example model
  (`ptc/25-04-31.sysml`, the Simple Vehicle Model), not a library.
- Our pinned artifacts (`KerML.xmi`, `SysML.xmi`) are abstract-syntax only;
  `Real` appears 0 times in them.

At the time, this was treated as a blocker rather than a path:

1. **Scope conflict.** `.kpar` (KPAR) is explicitly named in the kickoff's
   NON_GOALS ("KPAR & the SysML v2 API client") as out of scope for the first
   vertical slice. Pinning and depending on KPAR archives needed an explicit
   scope reset before implementation.
2. **Format.** `.kpar` is a zip-based project archive, not the MOF XMI our
   generator path consumes; a faithful loader would need a KPAR
   reader/unzip + the textual library syntax inside, which is itself a
   larger build than "load a pinned XMI".
3. **Fetch.** The download tool available here converts pages to markdown and
   cannot retrieve a binary zip archive intact, so even pinning the bytes is not
   possible from this environment without a separate approved binary-download
   step.

Decision at that point: PAUSE Z2 and do NOT fall back to a hand-authored curated
value-type subset (per the standing instruction). AttributeUsage remains
`alpha` with the stdlib dependency named. At that point, resuming the stdlib path
required an explicit decision on one of: (a) relax the first-slice KPAR boundary
and add a pinned-KPAR reader (binary fetch + unzip + the library textual syntax);
(b) approve a binary download of the `.kpar` artifacts plus a converter to a
pinned XMI/text form; or (c) accept a curated value-type subset as an explicit,
documented exception to the "pin the real source" rule. No code was written for
that stdlib path.

### Phase 0 Scope Reset: KPAR is now in completion scope (recorded 2026-06-19)

The project has moved beyond the first vertical slice. KPAR is no longer a
blanket non-goal. At that moment, the completion roadmap brought KPAR in
deliberately as a phased capability:

1. pin the OMG `.kpar` artifacts with provenance and hashes;
2. build a read-only KPAR archive reader;
3. decide and implement KPAR import semantics before using imported libraries for
   value typing (replanned after Phase 2; see below);
4. use the imported normative libraries to finish primitive/value-typed
   AttributeUsage;
5. later add KPAR export and KPAR round-trip.

This does not license a hand-authored value-type stub. It means KPAR is a
first-class source/interchange format in the remaining plan, and each KPAR phase
must carry its own focused tests and support-matrix claim updates.

The SysML v2 API/client surface is also no longer dismissed by the old kickoff
boundary. It is a later decision phase and remains separate from Gaphor's
internal identity model unless that phase proves a concrete API-facing need.

### Completion Phase 1: KPAR Artifact Baseline (verified 2026-06-19)

The direct binary-delivery question was tested first, using the formal OMG About
pages as the source of truth for exact URLs. The OMG KPAR links are publicly
downloadable with `curl -L --fail`; all ten direct responses returned HTTP 200,
non-empty payloads, and ZIP magic bytes (`PK\x03\x04`). OMG serves them with
`content-type: text/plain; charset=UTF-8`, so the project verifies them by
source URL, file id, byte size, SHA-256, and ZIP structure rather than MIME type.

Pinned KPAR artifacts under `docs/sysml-v2/omg/20250201/`:

- KerML: `Semantic-Library.kpar`, `Data-Type-Library.kpar`,
  `Function-Library.kpar`.
- SysML: `Systems-Library.kpar`, `Analysis-Domain-Library.kpar`,
  `Cause-and-Effect-Domain-Library.kpar`, `Geometry-Domain-Library.kpar`,
  `Metadata-Domain-Library.kpar`, `Quantities-and-Units-Domain-Library.kpar`,
  `Requirement-Derivation-Domain-Library.kpar`.

The artifact manifest in `docs/sysml-v2/omg/20250201/README.md` records exact
URLs, OMG file ids, byte sizes, and SHA-256 hashes. The Phase 1 tests verify
that each archive exists, matches the manifest, is a valid ZIP/KPAR archive, and
contains representative `.project.json`, `.meta.json`, and library text entries.
They also smoke-check that `Data-Type-Library.kpar` contains the expected scalar
value types (`Boolean`, `String`, `Real`, `Integer`, `Natural`) in
`ScalarValues.kerml`.

Boundary: this phase pins and verifies bytes only. It does not implement the
KPAR reader, semantic KPAR import, or value-type resolution against imported
libraries; those remain the next completion phases.

### Completion Phase 2: KPAR Reader Core (verified 2026-06-19)

The read-only reader lives in `gaphor/SysML2/kpar/` (a forward-looking
subpackage, since Phases 3a/3b/3c and Phase 10 are also KPAR work).
`read_kpar(path)` returns frozen dataclasses -- `KparArchive` with `KparProject`
(from `.project.json`), `KparMeta` (from `.meta.json`, including the
qualified-name->file `index`), and a deterministic, name-sorted tuple of
`KparModelFile`s discovered by `.kerml`/`.sysml` extension under the single
project directory.

Decisions:

- Error model is a typed exception hierarchy (`KparError` ->
  `KparNotFoundError`, `KparNotAnArchiveError`, `KparLayoutError`,
  `KparMetadataError`) rather than a diagnostics list. The reader either yields a
  trustworthy inspection or fails loudly; that matches the "unknown structure
  fails loudly" exit criterion and is distinct from the model-validation
  diagnostics surface, which is a different concern.
- Layout is validated strictly: exactly one `.project.json`, all real content
  under its directory, descriptors parseable, `name` present. Anything else
  raises.
- Known-benign zip noise is the one explicit exception to "fail on anything
  unexpected": `__MACOSX/` (macOS zip tooling, present in `Systems-Library.kpar`)
  and `.DS_Store` are skipped and documented, never treated as model content or
  as a stray-entry error. This is a deliberate, narrow allowlist, not silent
  tolerance of arbitrary extra files.
- A read-only `sysml2-kpar-info` CLI command was added (registered as a
  `gaphor.argparsers` entry point) so the reader is observable from the command
  line. It prints metadata and the model-file listing; it does not import.

Boundary: this phase inspects archives only. It does not read or interpret model
file *content*, load the standard library, or import user models -- those are
Phases 3a/3b/3c and later.

### Phase 3 Replan: KPAR import precedes standard-library promotion (recorded 2026-06-19)

After the Phase 2 reader landed, the plan was changed deliberately: do the KPAR
import architecture before the read-only standard-library/value-type layer. The
previously discussed in-memory dataclass standard-library index remains a
possible internal implementation detail only if the import design contract
chooses it; it is no longer the next standalone phase.

The reason is architectural, not because Phase 2 failed. General import answers
questions that would otherwise be decided implicitly by a narrow value-type
loader:

- how imported KPAR content gets identity in Gaphor (`Base.id`, source KPAR
  identity, API-facing ids, and canonical identity);
- whether imported elements are saved in `.gaphor`, referenced by pinned
  provenance, or regenerated from KPAR on load;
- which content is read-only (normative OMG libraries) versus editable (user
  imports);
- how `.project.json` `usage` dependency closure, missing dependencies, and
  version constraints are handled;
- what duplicate import, re-import, and update semantics are;
- whether unsupported textual content fails the import, creates explicit
  unresolved/proxy records, or is imported as a tested subset with diagnostics;
- how every imported element/reference records KPAR path, member file, source
  declaration, and declaration span when available.

The new track is:

1. **Phase 3a -- KPAR Import Design Contract.** Commit the import identity,
   storage, mutability, dependency, partial-import, duplicate/re-import, and
   provenance rules before semantic import code materializes content.
2. **Phase 3b -- Minimal Normative Library Import.** Apply that contract to the
   pinned OMG libraries and import enough real content to materialize
   `ScalarValues::Real/String/Boolean/Integer/Natural` plus required owning
   packages/aliases/dependencies. No hand-authored value-type stubs.
3. **Phase 3c -- General User KPAR Import.** Expand the same import path to user
   KPAR projects over the implemented SysML2 surface, with CLI/UI entry points
   and diagnostics according to the Phase 3a policy.

AttributeUsage promotion now depends on this imported normative-library path, not
on a separate pre-import library index.

### Completion Phase 3a: KPAR Import Design Contract (committed 2026-06-19)

The contract is committed as `docs/sysml-v2/KPAR_IMPORT_CONTRACT.md` (the
authoritative document) and anchored mechanically by
`gaphor/SysML2/tests/test_kpar_import_contract.py` plus a static existence gate.
No importer code or imported semantic content lands in this phase; no
support-matrix cell moves.

Ratified decisions (see the contract for the full text):

- **Representation/storage:** imported normative-library content is materialized
  as real read-only KerML kernel elements in a dedicated library ElementFactory
  that is regenerated from the pinned KPAR on load, and is *not* persisted into
  the user's `.gaphor`.
- **Identity:** Gaphor `Base.id` stays internal; canonical library identity is
  the fully-qualified KerML name plus KPAR provenance; no API id minted yet.
- **Dependency closure:** closed-world over `docs/sysml-v2/omg/20250201`; never
  fetches; resolves `usage` only to pinned artifacts; imports the minimal closure
  the targeted declarations need; a missing required dependency fails the import.
- **Unsupported syntax:** subset-import with explicit unresolved/diagnostic
  records, never silent loss.
- **Entry points:** Phase 3b is Python-API-only; CLI/UI deferred to Phase 3c.
- **Provenance:** every imported element/reference traces to a pinned KPAR
  (path, SHA-256, member, declaration text, span when available).

### Completion Phase 3b: Minimal Normative Library Import (verified 2026-06-19)

`gaphor/SysML2/kpar/library.py` applies the Phase 3a contract to the KerML
`ScalarValues` value-type package. `import_scalar_values_library()` returns a
read-only `NormativeLibrary`.

- **What is imported:** the `ScalarValues` package and its full datatype closure
  (`ScalarValue`, `Boolean`, `String`, `NumericalValue`, `Number`, `Complex`,
  `Real`, `Rational`, `Integer`, `Natural`, `Positive`) as real
  `kerml.Package`/`kerml.DataType` elements, with intra-package `specializes`
  edges as `kerml.Specialization`. This is the contract's ElementFactory-backed
  representation, built through the existing kernel Create-API.
- **Regenerate on load, not persisted:** each call builds the elements in a
  fresh `ElementFactory`; nothing is written to `.gaphor`. Re-import yields the
  same qualified names with fresh element instances (tested).
- **Parser scope:** a focused, strict parser handles exactly the value-type
  subset `ScalarValues.kerml` uses (`[standard] [library] package`, `doc`,
  `[private|public] import`, `[abstract] datatype X [specializes A, B];`). Any
  other construct inside the package would be recorded as unsupported, never
  silently dropped; for `ScalarValues` the unsupported list is empty (tested).
- **Cross-library closure:** the minimal closure is `ScalarValues` alone.
  `ScalarValue specializes DataValue` (DataValue is in `Base`, outside the
  closure) is recorded as an explicit `UnresolvedReference`; no dangling
  `Specialization` to a missing element is created. Full dependency-closure
  import remains Phase 3c.
- **Provenance / no stubs:** every imported element *and relationship*
  (`Specialization`) records the KPAR path, SHA-256, member file, source
  declaration text, and line; the unresolved cross-library references carry the
  same provenance. A test confirms each recorded declaration actually appears in
  the pinned member bytes.
- **Closed-world dependency resolution:** the importer reads model content only
  from the pinned `docs/sysml-v2/omg/20250201` dir (overridable for tests) and
  never fetches. Each `.project.json` `usage` entry is matched to a pinned
  artifact; a declared dependency that is not pinned fails the import loudly
  (e.g. `Data-Type-Library` without its `Semantic-Library` dependency). Matching
  requires the dependency to be a readable, well-formed KPAR (not merely a file
  with the right name) and, when the usage `versionConstraint` is an exact
  version, the pinned project version must equal it. Importing the dependency's
  *content* (full closure) and full semver-range constraint handling remain
  Phase 3c.
- **Boundary:** Python API only; no CLI/UI; no support-matrix cell moves.

### Completion Phase 3c: General User KPAR Import (verified 2026-06-19)

`gaphor/SysML2/kpar/project_import.py` (`import_user_kpar()` -> `UserKparImport`)
imports a *user* KPAR project through the existing SysML2 text pipeline, with a
`sysml2-kpar-import` CLI command. Decisions ratified at the Phase 3c review gate:

- **Editable, persisted (not read-only).** Imported content becomes ordinary
  Gaphor model elements in the target ElementFactory and is saved into `.gaphor`,
  exactly like importing a `.sysml` text file -- the opposite of the read-only,
  regenerated normative libraries. Provenance/diagnostics are recorded on the
  import result, but they do not make the imported elements read-only.
- **Per-member partial import.** Each model member is parsed independently;
  members that parse are imported, members that do not are recorded as rejected
  members with their parse error. One bad member never blocks the others, and
  nothing is silently dropped.
- **Self-contained, project-wide resolution.** A new `mapping.map_project`
  builds every parseable member under one shared project namespace and resolves
  typing project-wide, so cross-file references inside the KPAR resolve. A name
  that belongs to no imported member (a library/external/unimported type) stays
  unresolved and is recorded. Cross-library resolution into the Phase 3b
  normative library is Phase 4.
- **Dependency-gap diagnostics.** A user KPAR's declared `.project.json` `usage`
  entries are surfaced as external-dependency diagnostics (not resolved/imported
  in this self-contained phase).
- **Validation before persist.** The mapped model is validated; the CLI refuses
  to save a model with validation errors (unresolved/mistyped types, duplicate
  names) unless `--allow-invalid` is passed -- matching the single-file
  `sysml2-import` policy.
- **Per-element/reference provenance.** The grammar now records each
  declaration's source line, so every imported element (including nested ones),
  every relationship created from a declaration (for example `FeatureTyping`),
  and every unresolved reference traces to its source member, declaration text,
  and line. Provenance is metadata only; imported content stays editable.
- **Entry points.** Python API + `sysml2-kpar-import` CLI; GUI import is Phase 3d.
- **Deferred (recorded, not claimed):** duplicate-import and version-conflict
  diagnostics, which only arise when re-importing into an already-populated user
  model -- a re-import/merge concern beyond this single-project import slice.

### Completion Phase 3d: GUI KPAR Import (verified 2026-06-19)

The Phase 3c importer is exposed in the UI via the `gaphor/plugins/sysml2kparimport/`
plugin (`SysML2KparImport`), registered as the `sysml2_kpar_import` service and
adding **File -> Import -> Import KPAR Project…** through a new `import_menu`
menu fragment.

- **Plugin, not modeling-language code.** The service bridges `gaphor.ui` (file
  dialog, menus, Adw dialogs) and the SysML2 importer. The architecture rules
  forbid `gaphor.SysML*` from importing `gaphor.ui` (beyond `filedialog`/
  `errordialog`), so the GUI service lives in `plugins/` like `diagramexport`,
  while the pure importer stays in `gaphor/SysML2/kpar/`.
- **Import into the current model.** Importing adds the KPAR's content to the
  open model's ElementFactory as ordinary editable, undoable elements (reusing
  `import_user_kpar`), wrapped in one `Transaction`.
- **No empty-root on nothing-imported.** If no member parses (`imported_any` is
  False), the just-created root namespace is removed and the UI reports "No
  supported content found" -- matching the CLI's refusal rather than leaving an
  empty namespace in the model.
- **Gate only on import-caused diagnostics.** `import_user_kpar` snapshots the
  target factory's diagnostics before building the import and reports only the
  new ones (`validation_diagnostics`), keeping pre-existing model problems
  separate (`preexisting_diagnostics`). So a valid import into a model that
  already has errors is not refused for those errors, while an import that
  introduces a problem of its own (e.g. a duplicate name within the imported
  project, or an unresolved/mistyped reference) still is. Because each import
  lands in a fresh root namespace, detecting a collision against *pre-existing*
  model content is part of the deferred duplicate/re-import work, not this gate.
- **Confirm-or-cancel on validation errors.** A first pass imports and, if there
  are import-caused validation errors, removes the just-imported subtree
  (`result.root.unlink()`, whose composite containment cascades) and asks the
  user; on confirm it re-imports with `allow_invalid=True`. Subtree removal is
  used instead of transaction rollback so it does not depend on an undo manager
  being active and only ever touches this import's content. Mirrors the CLI's
  refuse-by-default + `--allow-invalid`.
- **Diagnostics without losing detail.** A summary toast plus an Adw details
  dialog listing rejected members, unresolved references, validation errors, and
  external dependencies.
- **Testability.** The import core (`import_into_model`) is GTK-free and tested
  headless (commit, refuse-removes-subtree, refusal-preserves-existing-content,
  allow-invalid, malformed-archive, action/menu registration). The file chooser
  and dialogs are the thin GUI layer. The menu wiring spans `menubar.ui`,
  `mainwindow.ui` (hamburger), and the app menu hooks in `gaphor/ui/__init__.py`.

### Completion Phase 4: AttributeUsage Promotion (verified 2026-06-19)

`attribute x : Real` now resolves against the pinned standard library, so SysML
AttributeUsage is promoted from `alpha` to `supported`.

- **Library-aware resolution.** In `gaphor/SysML2/mapping.py`, when an
  AttributeUsage's declared type does not resolve in the user model, the mapper
  resolves the name against the pinned `ScalarValues` library
  (`import_scalar_values_library`, cached per process) and types the attribute.
  This is global to the mapper, so it applies to text import, the round-trip
  harness, and user KPAR project import alike (a user KPAR's `attribute x : Real`
  now resolves instead of being recorded unresolved).
- **Referenced value-type proxy.** The typing target is a read-only proxy: a bare
  `kerml.DataType` (declared name = the library type's simple name) materialized
  once per type at the model root, reused for repeated references. It is a real
  Type for `FeatureTyping`/validation/persistence, but -- being neither a SysML2
  construct nor a Package -- it is invisible to `export.py` and the round-trip
  canonical form, so `attribute x : Real;` round-trips and the library
  declaration is never dumped. See the KPAR_IMPORT_CONTRACT Storage amendment.
- **Kind rule relaxed.** `type_matches_usage_kind` now accepts any
  `kerml.DataType` for an AttributeUsage (an AttributeDefinition, which is a
  DataType, or a library value type); other usage kinds keep exact matching. This
  single change covers the mapper and the model-derived validation, which routes
  kind-checking through the same function.
- **UI.** The AttributeUsage type property page lists the concrete library value
  types alongside in-model AttributeDefinitions
  (`mapping.library_value_type_names` / `mapping.set_attribute_library_type`),
  and pre-selects the current library type. Bare proxies have no property page, so
  they are not user-editable.
- **Scope/limits:** only AttributeUsages get library value typing; abstract
  library bases (ScalarValue, NumericalValue, Number) are not offered; per-element
  KPAR-span provenance for proxies is by qualified name (verifiable against the
  pinned library), not a stored span.

### Completion Phase 5: Deeper Name Resolution (verified 2026-06-19)

`mapping._resolve_type` was replaced with a **nearest-first, enclosing-namespace**
resolver. It looks up a (qualified) type name's first segment by walking outward
from the usage's own namespace through each enclosing namespace to the model root
(`kk.owning_namespace`), the nearest declaration winning, then navigates the
remaining `::` segments as members from that match.

- **Scope decision (matches the grammar we support).** This adds enclosing-package
  lookup and relative-qualified names (e.g. a sibling `A::Engine` referenced from
  within the enclosing package) on top of the old same-namespace / root-qualified
  scope, and gives inner scopes shadowing over outer ones. It is the reachable,
  testable part of the planned resolver for the current grammar.
- **Proxy exclusion (order-independence).** Standard-library value-type proxies
  (bare `kerml.DataType`s materialized by Phase 4) are excluded from name
  resolution, so a proxy created for an earlier usage cannot change how a later
  name resolves. Without this, `package A { attribute a : Real; package B { part
  p : Real; } }` would make `p` *mistyped* (it would bind to the Real proxy)
  while the same model without the attribute leaves `p` *unresolved* -- diagnostics
  must not depend on declaration order.
- **Deferred (formally replanned as named phases 5a-5e).** Imports/imported
  memberships + visibility + ambiguity diagnostics (5a), aliases (5b), inherited
  members (5c), implicit specialization (5d), and feature chains (5e) are NOT
  implemented: each needs new grammar syntax AND a semantic contract, so they are
  unauthorable/untestable today and are now named PLANNED phases in the roadmap
  with prerequisites and exits, rather than a vague deferral. Within the current
  grammar, nearest-first resolution is deterministic, so there is no reachable
  ambiguity to report yet (duplicate names in one namespace are a separate
  validation rule).
- **featuring_types retired.** `kerml_kernel.featuring_types()` was a raising stub
  with no implementation (no TypeFeaturing wiring) and no caller, so it was
  removed rather than kept as dead surface. It returns as a real derivation if a
  later phase wires TypeFeaturing and a consumer needs it.
- **No support-matrix cell moves**: this deepens resolution for already-`supported`
  constructs; no new claim is made.

### Completion Phase 9: Connection End Semantics (verified 2026-06-20)

Binary, non-chain connector endpoints. `connection c connect a to b;` (optionally
`: <type>`) is now parseable, mappable, validatable, exportable, round-trippable,
and diagrammable; ConnectionDefinition/ConnectionUsage are promoted to
`supported`.

- **Endpoint model.** A ConnectionUsage IS a KerML Connector (a Relationship), so
  the two binary ends are stored as the connector's existing `source`/`target`
  references -- no new end modeling. The mapper resolves each endpoint nearest-first
  (Phase 5) to a `Feature`; a name that resolves to a non-feature (a package or a
  definition) or not at all is a broken/mismatched end, recorded in
  `MappingResult.unresolved_ends` and reported by the `broken-connection-end`
  validation rule (each end is independent -- a resolved end is still set).
- **Grammar.** `connection NAME (":" type_ref)? connect_clause? ";"`, where
  `connect_clause: "connect" connection_end "to" connection_end`. `connect`/`to`
  become reserved words (LALR keyword terminals), consistent with the other
  keywords; the parser carries the connect clause via a tagged `_Connect` so it is
  distinguishable from an optional type_ref.
- **Export / round-trip.** Export emits the connect clause with each end rendered
  as a re-resolvable name (bare for a same-namespace end, else the path from the
  export root); the canonical form's ConnectionUsage entry gained the source/target
  qualified names so endpoints participate in round-trip equivalence.
- **Diagram (line bound to ends).** `ConnectionUsageItem` is now a
  `LinePresentation` registered with `@represents(head=Relationship.source,
  tail=Relationship.target)` and a name label, so a connection projects as a line
  whose handles bind to the source/target items. `ConnectionUsageConnect` authors
  the ends on connect (head->source, tail->target via the head/tail metadata) but
  preserves the connection's own subject (never find-or-creates), so neither
  drawing nor anchoring duplicates the connection. `drop` anchors the line to the
  endpoint items when present, else projects a free line.
- **Scope.** Binary, non-chain endpoints only. Feature-chain endpoints
  (`connect a.b to c.d`) depend on Phase 5e; n-ary/unnamed connection forms are
  later work.
