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
  validation rule.
- **Atomic ends (revised 2026-06-20).** A binary connection's ends are atomic:
  source and target are materialised together only when BOTH names resolve to a
  feature. If either is broken, the broken name(s) are recorded and NEITHER end is
  set -- the connect clause is reported broken, not half-formed. The earlier
  "each end is independent" behaviour left a one-ended connection in the model,
  which has no valid textual form and was dropped silently on export; keeping ends
  atomic removes that silent-loss path (the broken end is the only thing reported,
  and the import gate already trips on it). A one-ended connection that still
  reaches the model by another route (the Python/kernel API, a hand-edited
  `.gaphor`) is caught model-derived by the `incomplete-connection` rule -- the
  Connector counterpart to `broken-typing`.
- **Feature ends enforced at every layer (revised 2026-06-20).** "A connector end
  is a `Feature`" must hold at the model, not just at UI hover. Gaphor's low-level
  `connect()` does NOT consult a connector's `allow`, so the `allow` narrowing
  alone left non-feature ends reachable via a direct connect or an API mutation
  (and they passed validation and exported a clause the mapper would reject). Now:
  `connect_subject` only authors a `Feature` subject (a non-feature connected item
  yields no end), a model-derived `non-feature-connection-end` rule reports any
  source/target that is not a feature (covering the API and reloaded-model
  routes), and export emits the connect clause only when BOTH ends are features
  (an invalid end exports as the bare declaration, never as a non-round-trippable
  `connect D to a`). `allow` stays as the first, hover-level line of defence.
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
  the ends onto the EXISTING subject: on connect it writes head->source and
  tail->target itself (clearing each multi-valued end first, so a reconnect
  replaces rather than appends), never find-or-creating, so neither drawing nor
  anchoring duplicates the connection. Returning early when a subject is already
  present (the first cut) left `source`/`target` None for a projected/toolbox line
  -- the visual line connected but the model ends did not -- so authoring is now
  unconditional for an existing subject. `allow` is also narrowed: an end must be a
  `Feature`, so a handle cannot land on a `ConnectionDefinitionItem` even though
  the generic metadata types ends as `Element` (matching the text mapper, which
  rejects definitions as ends). `drop` anchors the line to the endpoint items when
  present, else projects a free line.
- **Endpoint provenance (KPAR import).** A broken connector endpoint is recorded
  as an `UnresolvedTypeReference` (reason `unresolved-endpoint`) with the same
  per-member/line/declaration provenance as a type reference, so every unresolved
  reference -- type or endpoint -- traces back to its KPAR member and declaration
  (Phase 3c contract).
- **Scope.** Binary, non-chain endpoints only. Feature-chain endpoints
  (`connect a.b to c.d`) depend on Phase 5e; n-ary/unnamed connection forms are
  later work.

### Completion Phase 8a: Port Conjugation (verified 2026-06-20)

`port p : ~Fuel` types a port by the *conjugate* of a PortDefinition. Modeled
faithfully on the normative metamodel (the user's decision over an ad-hoc flag),
which promotes PortDefinition/PortUsage from `alpha` to `supported` for the
declaration-and-typing surface including conjugation. Flow direction (8b) and
interfaces (8c) remain follow-ups.

- **Metamodel (generated, not hand-written).** KerML `Conjugation` is added to
  the kernel seed and SysML `PortConjugation`, `ConjugatedPortDefinition`,
  `ConjugatedPortTyping` to the SysML seed; `kerml.py`/`sysml2.py` and the
  `models/*.gaphor` are regenerated from the pinned XMI through the existing
  adapter+coder pipeline. Conjugation's ends (`originalType`/`conjugatedType`)
  reference Type and `conjugator` is derived, so the kernel closure grows by
  exactly one class (27 -> 28).
- **Storage (faithful, navigable, cascade-correct).** Each PortDefinition has at
  most one implicit conjugate: a `ConjugatedPortDefinition` owning a
  `PortConjugation` whose `originalPortDefinition` is the original (and whose
  KerML Conjugation ends are original -> conjugated). The conjugate is an UNNAMED
  owned member of the original, so it cascades on the original's delete,
  round-trips, and stays invisible to name resolution and the duplicate-name
  rule (its name is the derived `~<original>`). A port usage typed `: ~Fuel` is
  typed by that conjugate through a `ConjugatedPortTyping` (a FeatureTyping
  subclass) owned by the usage; the conjugate is reused across all `~Fuel`
  typings. This SysML behavior lives in `conjugation.py`, kept separate so
  `kerml_kernel` stays KerML-pure.
- **Grammar (port-scoped).** `port NAME (":" port_type_ref)? ";"` with
  `port_type_ref: "~"? type_ref`. The `~` is a distinct port rule, NOT folded
  into the shared `type_ref`, so conjugation cannot leak onto non-port usages
  (`part p : ~X` is a syntax error). The AST `PortUsage` gains a `conjugated`
  flag; the mapper threads it through the existing typed-usage phase-2 list.
- **Typing kind.** A conjugated typing must resolve to a PortDefinition; its
  conjugate is then a `ConjugatedPortDefinition` (a PortDefinition subclass), so
  `type_matches_usage_kind` accepts a PortUsage typed by ANY PortDefinition
  subclass (the only one is the conjugate) -- the exact-kind rule used elsewhere
  would otherwise reject the conjugate. A `~` on a non-port resolves but is
  recorded mistyped (`~Name`); an unresolved `~` name is recorded unresolved.
- **Export / round-trip.** Export re-emits `~<original>` (re-resolvable, never
  the unnamed conjugate), and never emits a `ConjugatedPortDefinition` as a
  `port def`. The canonical form renders a conjugated typing as `~<original-qn>`
  so `: Fuel` and `: ~Fuel` are distinct, stable fingerprints that survive
  reload.
- **Validation.** Model-derived `broken-conjugation`: a `ConjugatedPortTyping`
  must point at a real `ConjugatedPortDefinition` that has a `PortConjugation`
  naming the original -- catching a conjugation broken by the API or a deleted
  original (where the textual mapper's checks no longer apply).
- **Diagram / UI-edit.** A conjugated port projects as a subject-bound
  `PortUsageItem` (the conjugate is never projectable -- guarded in `drop`); the
  PortUsage type page gained a "Conjugated (~)" toggle that re-types the port via
  the conjugate (preselecting the ORIGINAL definition and reflecting an existing
  conjugation).

### Completion Phase 8b: Flow Direction (verified 2026-06-21)

Feature direction (`in` / `out` / `inout`) on ALL usages, mapping to KerML
`Feature::direction`. No support-matrix row changes status; direction is added to
the existing declaration-and-typing surface of every usage.

- **Nullable direction (the central decision).** KerML `Feature::direction` is
  `[0..1]`, but the coder generated it as an enum defaulting to `in`, so an
  undirected feature and an `in` feature collapsed (and `set(in)` deletes the
  stored value, so the two were indistinguishable on reload). Direction is now
  NULLABLE: undirected = `None` (unset), `in`/`out`/`inout` explicit, all four
  round-tripping distinctly. Implemented as a GENERATION RULE, not a hand override
  of one property: core `enumeration` gained `None`-default support
  (backward-compatible -- a non-`None` default keeps the old behaviour), and the
  coder gained an explicit `nullable_optional_enums` opt-in that emits an OPTIONAL
  enum (XMI lower 0, no explicit default) as `_enumeration(..., None)`.
- **Scoped so legacy languages are untouched.** The opt-in defaults OFF and is
  enabled only for the SysML2/KerML coder calls (poe tasks + freshness tests), so
  UML/Core/C4/SysML/RAAML regenerate byte-identical (`test_models_up_to_date`
  passes). The xmi_adapter captures an enum attribute's explicit lower bound and
  emits a `lowerValue` LiteralInteger, so the rule fires for `direction` and
  `portionKind` (lower 0, no default) but NOT `visibility` (which has a default in
  the XMI and no explicit lowerValue) -- visibility stays non-nullable.
- **Grammar/parse.** A `DIRECTION?` prefix (`in`/`out`/`inout`) on every usage
  rule; definitions are Classifiers (not Features) and take none (`in part def D;`
  is a syntax error). `DIRECTION` is a distinct terminal, so it is lexed as a
  direction only where a usage expects it (contextual LALR) -- a part may still be
  named `inlet`. Each usage AST node carries a `direction` string (or None); the
  parser splits a leading DIRECTION token, keeping the usage's existing positional
  layout.
- **Map / export / round-trip.** The mapper sets `feature.direction` from the
  prefix (undirected leaves the nullable default None). Export re-emits the prefix
  before the usage keyword. The canonical form records a directed usage's
  direction as a SEPARATE `("FeatureDirection", qn, dir)` entry, so a directed and
  an undirected usage are distinct fingerprints WITHOUT changing the base usage
  tuple (the many existing canonical-tuple assertions are untouched).
- **Diagram / UI-edit.** The usage box label shows the direction prefix
  (`in p`); definitions show just the name. A `FeatureDirectionPropertyPage`
  (registered on the base usage classes -- ConnectionUsage and RequirementUsage
  are matched by MRO, so no duplicate editor) sets the direction via a dropdown,
  with `(undirected)` clearing it back to None.

### Completion Phase 8c: Interface Definition / Usage (verified 2026-06-21)

The CONNECTION-LEVEL surface for InterfaceDefinition/InterfaceUsage. They are held
at `alpha` (not `supported`): the distinctive interface semantics -- interface
ends being typed/conjugated PORTS in the definition body plus flow -- need
definition-body grammar that no construct has yet.

- **Reuse by subclassing.** InterfaceDefinition IS a ConnectionDefinition and
  InterfaceUsage IS a ConnectionUsage, adding only DERIVED properties
  (interfaceEnd, interfaceDefinition). Seeded into the SysML generation, they pull
  no new stored closure -- an interface inherits the connector ends, typing, and
  direction. So Phase 8c is mostly wiring the existing machinery one definition
  kind deeper, not new semantics.
- **Most-derived-first everywhere.** Because the interface classes subclass the
  connection classes (which subclass the part classes), every kind-dispatch checks
  the interface kind FIRST: `USAGE_DEFINITION_KIND[InterfaceUsage] =
  InterfaceDefinition` (exact, so `interface i : C` for a plain ConnectionDefinition
  C is mistyped); export emits `interface`/`interface def` before the connection
  branches; the canonical form has Interface* entries before Connection*; and the
  diagram registers `InterfaceDefinitionItem`/`InterfaceUsageItem` (subclasses of
  the connection items) so they win over the inherited ones. The InterfaceUsageItem
  reuses the connection line AND, via MRO, the `ConnectionUsageConnect` connector.
- **Ends + validation for free.** `interface i connect a to b;` uses the same
  binary connector-end machinery as connections (Phase 9); the connection-end
  validation rules select `ConnectionUsage`, which includes InterfaceUsage, so
  broken/non-feature/incomplete ends are caught for interfaces with no new rule.
- **UI-edit deferral chain.** An InterfaceUsage matches the PartUsage,
  ConnectionUsage, AND InterfaceUsage type pages by MRO; the first two defer
  (return no widget) for an interface, and the InterfaceUsage type page lists
  InterfaceDefinitions only (exact-kind), so an interface gets exactly one
  type editor of the right kind. Toolbox tools create the interface item/element
  directly.

### Completion Phase 6a: Constraint Expression Bodies (verified 2026-06-21)

A constraint body (`constraint c { <expr> }`) is preserved as OPAQUE TEXT, not
parsed into a KerML expression tree. This was the explicit decision: a faithful
expression tree (operators as invocations of library functions, plus expression-
node classes and the function libraries) is a multi-phase effort, and a tiny
structured subset now would look more semantic than it is. The Constraint rows
stay `alpha`.

- **Carrier (honest, normative).** The body is stored as a `TextualRepresentation`
  (language `sysml`) owned by the constraint -- the KerML carrier for "this
  element's content represented as text in a named language". This preserves the
  body without claiming expression semantics. TextualRepresentation was seeded
  into the kernel (an AnnotatingElement with String body/language; 29 generated
  non-enum classes now). It is owned via the ordinary OwningMembership spine
  (there is no `Annotation` relationship class in the closure yet); the faithful
  Annotation attachment is deferred with the expression tree. A `Comment` was
  rejected as the carrier -- a constraint body is not documentation.
- **Grammar.** `constraint def NAME ( ";" | constraint_body )` and
  `[<dir>] constraint NAME [: type] ( ";" | constraint_body )`, where the body is a
  single `CONSTRAINT_BODY` terminal matching balanced braces (tolerant to a couple
  of nesting levels, so `{ ... { ... } ... }` is captured). Unbalanced braces are
  a parse error -- that IS the delimiter validation. The body is captured opaque
  and VERBATIM (the inner text between the braces, whitespace included -- not
  trimmed or normalized); it is never tokenized as SysML. Only the constraint
  rules get bodies; requirement bodies are Phase 6b.
- **Map / export / round-trip.** The mapper stores the body via
  `constraints.set_body_text`; export re-injects `{<body>}` verbatim with no added
  padding (so it
  re-parses identically); the round-trip canonical form records the body as a
  SEPARATE `("ConstraintBody", qn, text)` entry, so a constraint with a body is a
  distinct fingerprint without changing the base constraint tuple.
- **Validation.** Only basic well-formedness: an empty/whitespace body is a
  WARNING (`empty-constraint-body`) -- syntactically allowed, almost certainly a
  mistake; the body is otherwise not interpreted. (This is the first non-ERROR
  rule.)
- **UI-edit.** A `ConstraintBodyPropertyPage` text entry edits the body (clearing
  the field removes it); it DEFERS for requirements (they subclass the constraint
  classes, but requirement bodies are Phase 6b and not yet exported, so a body
  must not be authorable on a requirement here).

### Completion Phase 6b: Requirement Parameters (verified 2026-06-21)

Requirement `subject`/`assume`/`require` parts, modeled FAITHFULLY on the
normative membership structure (the explicit decision over local marker fields,
so future KPAR/validation/semantics work builds on the real model). Scope is
exactly subject/assume/require; `reqId` (6c) and actor/stakeholder/framedConcern
(6d) are out. Rows stay `alpha`.

- **Metamodel (generated).** Seeded the membership classes from the pinned XMI:
  KerML FeatureMembership/ParameterMembership (kernel; 31 non-enum classes now)
  and SysML SubjectMembership (-> ParameterMembership) and
  RequirementConstraintMembership (-> FeatureMembership, with `kind`:
  RequirementConstraintKind assumption/requirement -- the only new stored state).
- **Grammar.** `requirement [def] r [: R] ( ";" | requirement_body )`, where
  `requirement_body: "{" (subject_clause | assume_clause | require_clause)* "}"`;
  `subject_clause: "subject" NAME (":" type_ref)? ";"`; `assume_clause: "assume"
  "constraint" constraint_body` (and `require` likewise), REUSING the 6a
  `constraint_body`. The requirement body's literal `{ }` and the inner
  CONSTRAINT_BODY terminal are disambiguated by the contextual LALR lexer (verified
  alongside package `{ }`).
- **Mapping (memberships, not markers).** `requirements.py`: the subject becomes a
  `kerml.Feature` owned via a `SubjectMembership` (its declared type resolved in a
  separate phase-2 pass -- ANY Type, no usage-kind check, since a subject is a
  parameter; unresolved names recorded like any usage type, a scoped reference);
  each assumed/required constraint becomes an anonymous `ConstraintUsage` carrying
  a 6a opaque body, owned via a `RequirementConstraintMembership` with the matching
  kind. All are owned through these memberships (which ARE OwningMemberships), so
  they persist, cascade, and round-trip.
- **Single subject.** A requirement has exactly one subject (KerML
  `subjectParameter` is [0..1]), so a second textual `subject` clause is REJECTED
  at parse (a clear SyntaxError, surfaced by unwrapping Lark's VisitError) rather
  than silently overwriting the first.
- **Validation.** The subject type is validated by the existing
  `usage-without-valid-type` rule (recorded during mapping). A model-derived
  `broken-requirement-parameter` guards each membership's member using an
  EXACT-ONE check (`_sole`, not first-value `_single`, since `memberElement` is
  relation-many): a SubjectMembership must own exactly one Feature and a
  RequirementConstraintMembership exactly one ConstraintUsage, so a zero/multiple
  (appended)/wrong-kind member is reported -- a real safety net for a
  hand-edited/persisted .gaphor or an API mutation.
- **Export / round-trip.** Export re-emits `{ subject n : T; assume constraint
  {<body>} require constraint {<body>} }`; the canonical form records
  subject/assume/require as SEPARATE entries (`RequirementSubject` /
  `RequirementAssume` / `RequirementRequire`, the constraint entries carrying an
  ordinal so duplicate bodies stay distinct), leaving the base requirement tuple
  unchanged.
- **UI-edit (deferred).** Structured editing of subject/assume/require is
  deliberately deferred -- the requirement keeps its name/type editors -- so the
  rows stay `alpha` honestly rather than claiming a half-built editor.

### Completion Phase 6c: Lightweight Requirement Parameters (verified 2026-06-21)

The remaining lightweight requirement parameters `reqId`, `actor`, and
`stakeholder` -- grouped because they share an implementation shape (a short-name
attribute plus two `subject`-style parameter memberships) and none introduces a
new construct. Rows stay `alpha`.

- **reqId -> declaredShortName (canonical, single home).** The normative `reqId`
  REDEFINES `Element::declaredShortName`, but Gaphor's coder emits a redefinition
  as a SEPARATE String slot (it does not collapse redefinitions). Writing both a
  `reqId` slot and `declaredShortName` would double-store the same fact and let
  them disagree. Decision: store the reqId CANONICALLY in `declaredShortName` and
  treat the generated `reqId` slot as vestigial. `requirements.reqId` /
  `set_reqId` are thin accessors over `declaredShortName` (empty string normalizes
  to None).
- **actor / stakeholder (memberships, not markers).** Parameter features carried
  by the normative `ActorMembership` / `StakeholderMembership` -- both
  `-> ParameterMembership`, so they are SysML-layer classes seeded from the pinned
  XMI and the KERNEL count stays 31 (no kernel growth). Mapping mirrors the 6b
  subject machinery: each becomes a `kerml.Feature` owned via its membership, kept
  in declaration order, with its declared type resolved in the same phase-2 pass
  (ANY Type, no kind check; unresolved names recorded like any usage type). The
  phase-2 list was renamed `subject_typings` -> `parameter_typings` since it now
  carries subject/actor/stakeholder.
- **Grammar (short name + constraint-body restructure).** Added
  `short_name: "<" (QUOTED_NAME | NAME) ">"` (a bare `<R1>` or quoted `<'1.1.3'>`
  for dotted/special ids), threaded onto `requirement_definition`/`_usage` before
  the NAME, and `actor_clause`/`stakeholder_clause` alongside the 6b clauses.
  FIXING A LATENT 6b LEXER BUG: a USAGE with a type AND a body
  (`requirement r : R { ... }`, and likewise `constraint c : C { ... }`) mis-lexed
  the `{` as the greedy `CONSTRAINT_BODY` terminal (the type_ref tail let the
  contextual lexer reach the constraint-body terminal). The greedy terminal was
  REMOVED: a constraint body is now `"{" body_element* "}"` where
  `body_element: BODY_TEXT | braced_text` and `BODY_TEXT.2: /[^{}]+/` (priority
  above WS so a whitespace-only body is preserved). Every `{` now lexes to the
  same literal token and the PARSER disambiguates constraint-body vs
  requirement-body vs package body by context; opaque bodies are reassembled
  VERBATIM (whitespace and nesting preserved -- the 6a guarantee holds, retested).
- **Validation.** Parameter types via the existing `usage-without-valid-type`
  rule. The model-derived exact-one `broken-requirement-parameter` rule was
  EXTENDED to `ActorMembership` and `StakeholderMembership` (each must own exactly
  one Feature), using the same `_sole` relation-many check as the subject.
- **Export / round-trip.** Export emits the reqId as `<id>` when it is a valid
  identifier else `<'id'>` quoted, and the body re-emits `subject`, then `actor*`,
  then `stakeholder*`, then `assume*`/`require*`. The canonical form adds a
  `RequirementReqId` entry and order-sensitive `RequirementActor` /
  `RequirementStakeholder` entries (with an ordinal), leaving the base tuple
  unchanged.
- **UI-edit (reqId only).** A `RequirementReqIdPropertyPage` text editor sets
  `declaredShortName` (blank clears to None). Structured actor/stakeholder editing
  stays deferred, so the rows stay `alpha` honestly.

### Completion Phase 6c: review findings fix (verified 2026-06-21)

Two review findings on the 6c work, both fixed.

- **(High) actor/stakeholder are PartUsage, not bare Feature.** The pinned XMI
  types `ActorMembership::ownedActorParameter` and
  `StakeholderMembership::ownedStakeholderParameter` as `PartUsage`
  (`docs/sysml-v2/omg/20250201/SysML.xmi` lines 594/656), so building them as a
  generic `kerml.Feature` was unfaithful AND let an invalid parameter validate
  cleanly. Now the mapper creates `sysml2.PartUsage` for each actor/stakeholder,
  and -- because a PartUsage is kind-checked everywhere else -- their declared
  type resolves through the SHARED `_resolve_typed_usages` path (PartUsage ->
  PartDefinition, exact kind), so a wrong-kind type is reported (`type-kind-mismatch`)
  instead of being accepted as "any Type". The phase-2 list reverted to its
  subject-only name `subject_typings` (subject stays a `kerml.Feature` typed by ANY
  Type -- not flagged; the subject=ReferenceUsage refinement remains deferred).
  Validation's exact-one `broken-requirement-parameter` rule now requires exactly
  one **PartUsage** for actor/stakeholder (subject still requires a Feature), so a
  bare-Feature member is reported. `requirements.actors`/`stakeholders` return
  PartUsages.
- **(Medium) reqId short names round-trip losslessly via escaping.** Export used to
  wrap any non-identifier reqId in single quotes WITHOUT escaping, so a reqId like
  `A'B` exported as unparseable `<'A'B'>`. Decision (chosen over boundary
  rejection): preserve first -- support the spec's quote/backslash escapes so any
  short name round-trips. A new single authority `shortnames.py` does
  `encode`/`decode` (bare `<id>` for identifiers, else `<'...'>` with `\` -> `\\`
  and `'` -> `\'`); `QUOTED_NAME` accepts ONLY `\'`/`\\` escapes
  (`/'(?:[^'\\]|\\['\\])*'/`), so an unterminated/extraneous escape is a parse
  error, never silent corruption. The parser decodes and the exporter encodes
  through this one module (the ad hoc `re` in `export.py` is gone). The reqId UI
  setter needs no boundary rejection now -- every value is representable.

### Completion Phase 6d-1: Concern Construct + Framed-Concern Declare (verified 2026-06-21)

The Concern construct and a requirement's framed concern (DECLARE form). Sliced
from 6d by metamodel footprint: this slice is SysML-layer only; the reference form
(`frame <existing>`, needing kernel subsetting) is 6d-2. The user chose the
heavyweight scope (Concern reuses the full requirement body; `frame` will support
both declare and reference). Rows stay `alpha`.

- **Metamodel (generated).** Seeded ConcernDefinition (-> RequirementDefinition),
  ConcernUsage (-> RequirementUsage), and FramedConcernMembership (->
  RequirementConstraintMembership) from the pinned XMI. All are SysML-layer with
  no new stored closure, so the KERNEL count stays 31. NOTE: the XMI fixes
  FramedConcernMembership.kind's default to `requirement`, but Gaphor's coder does
  not capture a redefined default -- it emits the inherited `assumption`. So the
  mapper/behavior set `kind = requirement` EXPLICITLY (a `_enumeration` default is
  not authority here).
- **Concern reuses the requirement body.** A ConcernDefinition IS a
  RequirementDefinition and a ConcernUsage IS a RequirementUsage, so `concern def`/
  `concern` reuse `requirement_body` in the grammar and `_build_requirement_body`
  in the mapper; the AST ConcernDefinition/ConcernUsage mirror the requirement
  nodes (reqId/subject/assume/require/actors/stakeholders/framedConcerns). The
  parser's `_req_body_kwargs` is the shared body builder for all four node kinds.
  isinstance ordering puts Concern before Requirement in export/round-trip/mapping
  (a Concern IS a Requirement).
- **Framed concern (declare).** `frame concern <name> [: <C>]` builds a
  `sysml2.ConcernUsage` owned via a `FramedConcernMembership` (kind=requirement);
  its declared type is kind-checked (ConcernUsage -> ConcernDefinition) through the
  SHARED `typed_usages` path. COLLISION GUARD: a FramedConcernMembership IS a
  RequirementConstraintMembership (kind=requirement) owning a ConcernUsage (which
  IS a ConstraintUsage), so the `require`-constraint reader (`requirement_constraints`)
  and the constraint-membership validator EXCLUDE FramedConcernMembership -- a
  framed concern is read via `framed_concerns`, never as a `require`.
- **Validation.** Model-derived `broken-requirement-parameter` extended: a
  FramedConcernMembership must own exactly one ConcernUsage AND carry
  kind=requirement. ConcernUsage typing is the usual `type-kind-mismatch`/
  `usage-without-valid-type` (ConcernUsage -> ConcernDefinition, exact kind).
- **Diagram / UI.** The diagram registry is exact-type, so ConcernDefinition/
  ConcernUsage get their own items (`ConcernDefinitionItem`/`ConcernUsageItem`,
  mirroring the requirement items) + drop registrations. The shared
  ConstraintRequirement type page picks ConcernDefinition for a ConcernUsage
  (most-derived first); the reqId editor applies to concerns by isinstance.
- **Export / round-trip.** `concern def`/`concern` and the `frame concern ...`
  clause re-emit; the canonical form adds ConcernDefinition/ConcernUsage base
  entries and order-sensitive `RequirementFrame` entries (name + type).

### Completion Phase 6d-2: Framed-Concern Reference Form (verified 2026-06-21)

The framed-concern REFERENCE form `frame <existing>` (vs the 6d-1 DECLARE form
`frame concern <name> [: <C>]`). The user chose to support referencing an existing
concern, which the pilot models as an owned anonymous ConcernUsage that SUBSETS the
referenced concern -- so this slice adds the kernel subsetting relationships.

- **Metamodel (generated; kernel 31 -> 33).** Seeded Subsetting and
  ReferenceSubsetting from the pinned XMI (`Subsetting -> Specialization`;
  `ReferenceSubsetting -> Subsetting`). They add the stored subsetted/subsetting
  (referenced/referencing) feature ends. This is the one new KERNEL footprint of
  Phase 6d, isolated into its own slice for review; the kernel class-count test is
  updated 31 -> 33.
- **Representation (faithful).** `frame <existing>` owns an ANONYMOUS ConcernUsage
  (no declaredName) via a FramedConcernMembership (kind=requirement, as 6d-1), and
  that usage REFERENCES the existing concern through a ReferenceSubsetting
  (`kerml_kernel.add_reference_subsetting`: the referencing usage owns the
  subsetting; the referencedFeature is a non-owning reference). This mirrors
  `set_feature_type` (own the relationship; the target is a non-owning reference).
- **Grammar disambiguation.** `frame_clause` has two aliased alternatives:
  `frame_declare` (`"frame" "concern" NAME (":" type_ref)? ";"`) and
  `frame_reference` (`"frame" qualified_name ";"`). The `concern` keyword (a
  higher-priority literal than NAME) makes the choice LALR(1)-decidable: `frame
  concern X` declares, `frame X` references.
- **Resolution (phase 2, scoped).** A new `frame_references` list is resolved
  nearest-first (like connection ends): a name that resolves to a `ConcernUsage`
  gets a ReferenceSubsetting; a name that does not resolve, or resolves to a
  non-ConcernUsage (a ConcernDefinition is a Type, not a Feature; a part is the
  wrong kind), is recorded in `MappingResult.unresolved_frame_refs` -- never
  silently dropped.
- **Validation.** `broken-frame-reference` (mapping context, threaded through
  `validate` / cli / round-trip like `unresolved_ends`) reports each unresolved /
  wrong-kind reference. Consistent with unresolved usage types, this needs mapping
  context, so a reloaded model has none to recompute.
- **Export / round-trip.** A framed concern with a ReferenceSubsetting exports as
  `frame <name>` (the referenced name re-resolved via `_end_name`); a declared one
  as `frame concern <name> [: <C>]`; an anonymous one with no resolved reference
  (an unresolved import) is NOT re-emitted as invalid text (mirroring a broken
  connect clause / unresolved usage type) and is reported by validation. The
  canonical `RequirementFrame` entry carries the referenced qualified name, so the
  declare and reference forms have distinct fingerprints.

### Completion Phase 6d-2: review findings fix (verified 2026-06-22)

Two review findings on 6d-2, both fixed.

- **(High) KPAR import did not thread `unresolved_frame_refs`.** `import_user_kpar`
  built its `unresolved_references` list and ran its gating `validate(...)` without
  `result.unresolved_frame_refs`, so a user KPAR containing `requirement def R {
  frame missing; }` imported clean (no unresolved record, no gate). Fixed:
  `project_import.py` now adds each unresolved frame reference to the
  provenance-rich unresolved list (reason `unresolved-frame-reference`) AND passes
  `result.unresolved_frame_refs` to `validate`, so the import is gated like every
  other unresolved reference (matching the cli/round-trip paths).
- **(Medium) frame-reference validation was mapping-context only.** A stored/API-
  mutated model could hold a framed anonymous ConcernUsage whose
  ReferenceSubsetting points at a non-ConcernUsage; `validate(factory)` passed and
  export emitted invalid text (`frame p;`). Fixed: `_check_frame_references` gained
  a MODEL-DERIVED check -- when a ReferenceSubsetting exists under a framed concern,
  its referenced feature must be EXACTLY ONE ConcernUsage (`_sole`, not first-value
  `_single`). The two checks are disjoint (mapping-context fires only when NO
  subsetting was created; model-derived only when one exists), so there is no
  double-report. `framed_concern_reference` now uses exact-one too, and export
  emits the reference form only when the target is a ConcernUsage -- a corrupted
  reference is skipped (reported by validation), never emitted as invalid text.

### Completion Phase 6d-2: follow-up finding (verified 2026-06-22)

A second-round Medium finding on the same area: the model-derived integrity check
read only the FIRST owned ReferenceSubsetting (`kk.reference_subsetting` returned
the first match), so a framed concern with a valid first reference plus a second
appended ReferenceSubsetting passed `validate(factory)` and exported only the first
-- silently dropping the extra. Fixed: `reference_subsetting` is now EXACT-ONE
(None on zero or multiple), a new `reference_subsettings` exposes the full set, and
the integrity check requires EXACTLY ONE ReferenceSubsetting (to exactly one
ConcernUsage) under a referencing framed concern. A second subsetting is reported,
and export skips the corrupted frame (exact-one reader returns None) rather than
emitting just the first.

### Completion Phase 6d-2: follow-up finding 2 (verified 2026-06-22)

A third-round Medium finding on the same area: the integrity check allowed a NAMED
declared framed concern to ALSO own a valid ReferenceSubsetting. That mixed
declare+reference state validated clean and exported as `frame g;`, silently
dropping the declared `local : C`. Per the contract the reference form owns an
ANONYMOUS ConcernUsage, so the model-derived check now requires a referencing
framed concern (one owning a ReferenceSubsetting) to be a SINGLE ANONYMOUS
reference: exactly one subsetting to a ConcernUsage AND no declaredName AND no own
FeatureTyping. Export emits the reference form only for an anonymous usage, so a
mixed/corrupted frame is skipped (and reported), never misrepresented as `frame g;`.

### Completion Phase 6d-2: follow-up finding 3 (verified 2026-06-22)

A fourth-round Medium finding: export and validation had DRIFTED on what counts as
a reference. Validation rejected an anonymous framed concern that also owned a
FeatureTyping (anonymous-but-typed), but export only checked `not declaredName`, so
it still emitted `frame g;` -- silently dropping the corrupt own type. Fixed by
making `requirements.framed_concern_reference` the SINGLE shared predicate: it
returns the referenced ConcernUsage only for a well-formed reference (exactly one
ReferenceSubsetting to exactly one ConcernUsage, anonymous AND untyped), else None.
Export, round-trip, and the model-derived validation check all call it (plus
`is_referencing_frame` to tell a declared frame from a broken reference), so they
can no longer disagree; a corrupt reference is reported and skipped on export,
never misrepresented.

### Completion Phase 7: Action Semantics (verified 2026-06-22)

The action behavior surface -- bodies/steps, directed parameters, succession, and
flow -- done as one phase (the user chose "one big Phase 7") but scoped to the four
ROADMAP bullets, grounded in the pinned XMI and the Sensmetry pilot's action body.
Advanced action nodes are deliberately out (rows stay `alpha`).

- **Metamodel (generated; kernel 33 -> 35).** Seeded KerML Succession (-> Connector)
  and Flow (-> Connector + Step), and SysML SuccessionAsUsage (-> ConnectorAsUsage +
  Succession) and FlowUsage (-> ConnectorAsUsage + Flow + ActionUsage). All
  connector ends are derived (like Connector), so no new stored closure. The pinned
  2025-02 XMI names are FlowUsage/SuccessionAsUsage (NOT the 2024-12 pilot's
  "FlowConnection*"); we follow the pinned names.
- **Action bodies = nested members owned via FeatureMembership.** `action def A
  { ... }` / `action a [: T] { ... }` reuse the shared `member` grammar. The mapper's
  `_build_members` gained a `membership_type` parameter: package members are owned
  via OwningMembership (unchanged), but an action body's members (the action's
  FEATURES -- steps, directed parameters, successions, flows) are owned via
  FeatureMembership. The recursion that already descended into packages now also
  descends into ActionDefinition/ActionUsage with FeatureMembership.
- **Parameters.** A directed (`in`/`out`/`inout`) nested usage IS an action
  parameter -- reuses the Phase 8b `Feature::direction` already on usages; no new
  construct. Item-typed parameters (`out item x`) are out (no item usage in grammar).
- **Succession / flow = binary connector usages.** `succession [name] first <end>
  then <end>` and `flow [name] from <end> to <end>` map to SuccessionAsUsage /
  FlowUsage and REUSE the connection-end machinery: their two ends are recorded in
  `connection_ends` and resolved nearest-first (from the action's scope, so steps
  resolve), set on the connector's `Relationship.source`/`target`. Only the explicit
  forms are supported; the bare chained `first/then` flow form is out.
- **Validation.** `_check_connection_end_integrity` was generalized from
  ConnectionUsage to ALL `ConnectorAsUsage` (connection, interface, succession,
  flow), so a succession/flow with a non-feature or one-ended end is reported
  (non-feature-connection-end / incomplete-connection); an unresolved end is the
  mapping-context broken-connection-end. Messages reworded "connection" -> "connector"
  (rule names unchanged, so existing tests hold).
- **Export / round-trip.** Action def/usage emit ` { <members> }` (recursive,
  indented) or `;`; succession/flow emit their explicit forms via `_end_name`
  (skipped when an end is missing/non-feature, like a broken connection). The
  canonical `visit` now recurses into action bodies (their members' qualified names
  encode the action path) and records SuccessionAsUsage/FlowUsage with their
  resolved end qualified names, so bodies and connectors round-trip.
- **Diagram.** SuccessionAsUsageItem/FlowUsageItem are LinePresentations (subclass
  ConnectionUsageItem with head=source/tail=target), registered exact-type; drop
  registrations project them. Action bodies project as the existing action box; the
  interactive connect adapter for succession/flow ends is deferred.
- **Claim.** ActionDefinition/ActionUsage STAY `alpha` (under-claim): the advanced
  action-node surface is unimplemented. New SuccessionAsUsage/FlowUsage rows alpha.

### Completion Phase 7: review findings fix (verified 2026-06-22)

Two findings on the Phase 7 commit, both fixed.

- **(High) action-body ownership was FeatureMembership for EVERY member.** The
  action body reuses the shared `member` grammar, and the mapper owned all nested
  members via FeatureMembership -- so `action def A { part def P; package Nested;
  action step; }` created FeatureMembership -> PartDefinition and FeatureMembership
  -> Package (both NON-features), which validated clean and re-exported. Fixed with
  mapping SEPARATION (the option the finding preferred over restricting the
  grammar): `_build_members` now takes `owner_is_type` instead of a fixed
  `membership_type`, and owns each member PER KIND -- a Feature (usage) under a Type
  (action body) via FeatureMembership; a non-feature (nested definition/package), or
  anything under a non-Type namespace (package body), via OwningMembership. So a
  FeatureMembership only ever points at a Feature, and nested definitions remain
  valid namespace members. Added a model-derived `broken-feature-membership` rule (a
  plain FeatureMembership -- EXACT type, so the requirement membership subtypes keep
  their own rules -- must own exactly one Feature) as the safety net for
  hand-edited/API models.
- **(Medium) SuccessionAsUsage/FlowUsage claimed UI-edit=yes.** The implementation
  adds only diagram PROJECTION/drop, not the toolbox create-tool + property-page
  edit that the matrix's `UI-edit=yes` definition requires (the interactive connect
  adapter was explicitly deferred). The two rows are corrected to `UI-edit=no`
  (Diagram stays `yes` -- projection is real); the matrix note states it explicitly.

### Completion Phase 5a: Imports, Imported Memberships, Visibility & Ambiguity (verified 2026-06-23)

Resolution deepening (the first of the 5a-5e series carved out of the original
Phase 5). No new metamodel -- Import, VisibilityKind, and Membership.visibility
already existed (kernel stays 35); 5a wires grammar + mapping + an import-aware
resolver onto them.

- **Grammar / visibility prefix.** `[<vis>] import <QName> [::*] ;`. `::*` is a
  single `WILDCARD` terminal (`/::\s*\*/`), NOT `"::" "*"`, to avoid a shift/reduce
  conflict with the `::` qualified-name separator. The `public`/`private` prefix is
  hoisted to ONE place: `member: VISIBILITY? member_body`, and the `member`
  transformer applies it to whatever node (any member, or an import) via
  `dataclasses.replace`, so each member rule does not repeat it. A `visibility`
  field was added to every member AST node + a new `ast.Import`.
- **Visibility defaults (set explicitly).** A MEMBER defaults to PUBLIC (the SysML
  default) and an IMPORT to PRIVATE (the KerML default). The generated
  `Membership.visibility`/`Import.visibility` default is private, so the mapper sets
  member visibility explicitly (public unless declared private) -- otherwise every
  member would be private and un-importable.
- **Import target resolution (phase 2, owned-only).** `_resolve_imports` resolves
  each import's target with `_resolve_type(..., use_imports=False)`, so an import
  never resolves THROUGH another import (no transitive chains); a wildcard must land
  on a Namespace. Unresolved imports keep no target and are reported by the existing
  model-derived `unresolved-import` rule. Imports are resolved BEFORE the
  typed-usage/subject passes so those can see imported members.
- **Import-aware resolver + ambiguity.** `_resolve_type` now, at each scope, checks
  owned members first (any visibility -- own scope), then the scope's imports: a
  wildcard contributes the target namespace's PUBLIC members (`_public_member_named`
  honours member visibility, so a `private` member is not imported), a named import
  contributes the element by its name. Distinct candidates are de-duplicated by id;
  MORE THAN ONE distinct candidate returns the `_AMBIGUOUS` sentinel, which the type
  and subject resolvers record in `MappingResult.ambiguous` for the new
  `ambiguous-name` rule (threaded through `validate`, the CLI, round-trip, and KPAR
  import). An own member shadows an import; a nearer scope shadows a farther one.
- **Persistence-robust boolean.** A generated `_attribute[bool]` reloads from
  `.gaphor` as the STRING `"True"`/`"False"` (non-empty, so a bare truthiness test
  reads `"False"` as True). `kerml_kernel.is_import_all` normalizes it; used by the
  resolver, export, and round-trip so `isImportAll` survives save/reload. (Visibility
  is a StrEnum, which compares equal to its string form, so it needed no helper.)
- **Export / round-trip.** A namespace body emits its import statements then its
  members; a member emits a `private ` prefix only when private (public is the
  default), an import a `public ` prefix only when public. The canonical form gained
  `Import` (namespace, target, wildcard, visibility) and private-member `Visibility`
  entries. An unresolved import (no target) is skipped on export (reported by
  validation), mirroring a broken connector end.
- **Deferred (noted).** Transitive re-export through `public` imports, recursive
  imports (`::**`), and import aliases (Phase 5b).

### Completion Phase 5b: Aliases (verified 2026-06-23)

Resolution deepening (the second of the 5a-5e series). No new metamodel --
Membership already carries `memberName`/`memberElement`/`visibility` (kernel stays
35); 5b wires grammar + mapping + the resolver onto them.

- **Grammar / AST / parser.** `[<vis>] alias <NAME> for <QName> ;`, added as a
  `member_body` alternative so it reuses the shared `public`/`private` member prefix
  (default public). New `ast.Alias(name, target, visibility, line)`; the
  `alias_statement` transformer builds it, the `member` transformer applies the
  prefix like every other member.
- **Alias = NON-owning Membership.** An alias maps to a plain `kerml.Membership`
  (NOT an OwningMembership): it gives a foreign element an additional name
  (`memberName`) in the namespace WITHOUT owning it (`memberElement` is a non-owning
  reference; the target stays owned by its real namespace). Kernel helpers
  centralize the contract: `add_alias` (wire the non-owning membership +
  memberName + visibility), `set_alias_target` (bind the target in phase 2),
  `is_alias` (non-owning Membership with a memberName -- excludes every
  OwningMembership subkind, so Subject/Actor/Stakeholder/FramedConcern memberships
  are never mistaken for aliases), and `aliases` (a namespace's alias memberships).
- **Resolution through aliases.** `owned_member_named` now iterates memberships and
  matches `membership.memberName or effective_name(member)`, so an alias resolves by
  its alias name to the foreign element it references; a normal owned member
  (memberName unset) still matches by element name. This makes an alias resolve
  wherever a name resolves: a usage typed by the alias name, an alias to an imported
  name, and -- via `_public_member_named` also matching memberName -- a wildcard
  `import <ns>::*` that re-exports a public alias.
- **Target resolution (phase 2, import-aware, fixpoint).** `_resolve_aliases` runs
  AFTER imports and BEFORE typed usages. Each alias target resolves with the full
  import-aware `_resolve_type` (an alias may target an own/imported/aliased name).
  Because an alias may target another alias, resolution iterates to a fixpoint --
  each pass binds any alias whose target now resolves, repeating while progress is
  made -- so alias-to-alias chains settle regardless of declaration order; a cycle
  makes no progress and stays unresolved.
- **`members()` scoped to owned.** `kerml_kernel.members` now yields only the
  memberElements of OWNING memberships, excluding aliases (whose target lives in
  another namespace). A no-op for every pre-alias case (every membership owned its
  member), it stops export / round-trip / duplicate-detection from treating a
  foreign aliased element as one of the namespace's own members. Name resolution
  that must see aliases uses `owned_member_named`, not `members()`.
- **Validation.** New model-derived `unresolved-alias` (an alias whose target never
  resolved, i.e. no memberElement) -- SUPPRESSED when the target was ambiguous
  (recorded in `ambiguous` -> reported `ambiguous-name`), so an ambiguous alias is
  not double-reported (the same contract as connection ends / frame references from
  the 5a finding). `duplicate-name` now counts the name-in-namespace of every
  membership (`memberName or effective_name`), so an alias colliding with an owned
  member or another alias is caught.
- **Export / round-trip / persist.** A namespace body now renders from its
  memberships: owning memberships by member kind, alias memberships as
  `[private ]alias <name> for <path>;` (from the membership, NOT by re-rendering the
  foreign target; an unresolved alias is skipped, reported by validation, mirroring
  an unresolved import). The canonical form gained an `Alias` entry (namespace,
  alias name, target, visibility). The non-owning membership + memberName +
  visibility + target survive save/reload, and resolution through a reloaded alias
  still finds the target.
- **Deferred (noted).** Aliases inside action bodies are not fingerprinted by
  round-trip (the visit recurses only into packages, as for all members); a NAMED
  import of an alias (`import <ns>::E`) imports the underlying element under its real
  name, not the alias name. See `test_aliases.py`.

### Completion Phase 5c: Inherited Members (verified 2026-06-24)

Resolution deepening (the third of the 5a-5e series). One new metamodel class:
`Subclassification` (kernel 35 -> 36), the only kernel change in the 5a-5e series so
far -- inheritance has no honest representation without the heritage relationship.

- **Metamodel (regen).** Seeded `Subclassification` into `KERNEL_SEED` and
  regenerated `kerml.py` in Docker. It is a `Specialization` between Classifiers; its
  `superclassifier`/`subclassifier` REDEFINE the base general/specific and generate
  as their own stored ends (exactly like Subsetting's subsetted/subsetting ends), so
  the convention from `set_feature_type`/`add_reference_subsetting` carries over: the
  subkind-specific ends carry the relation, the base general/specific stay unset. The
  M1b count assertion and the SUPPORT_MATRIX kernel paragraph were updated to 36.
- **Grammar -- the `:>` token.** `:>` is the KerML specializes/subsets token,
  overloaded: subclassification between definitions, subsetting between usages
  (`:>>`/redefines is out of 5c scope). `part def Name specialization_part? (";" |
  definition_body)` with `specialization_part: ":>" qualified_name ("," ...)*` and
  `definition_body: "{" member* "}"` (the shared `member` list, so any nested usage
  kind works); `part_usage` gains `subsetting_part: ":>" qualified_name`. Lark's
  longest-match lexing keeps `:>` distinct from `:` (typing) and `::` (separator).
- **Definition bodies reuse the action-body machinery.** A PartDefinition IS a Type,
  so `owner_is_type=True` (added for Phase 7 action bodies) already owns body
  FEATURES via FeatureMembership and nested definitions/packages via OwningMembership.
  The `_build_members` recursion just added `ast.PartDefinition` to the action branch;
  a body-less `part def` has empty members, so it is a no-op.
- **Non-owning heritage ends.** `add_subclassification(subtype, supertype)` owns the
  Subclassification on the subtype; the supertype is a non-owning reference (mirrors
  `set_feature_type`). `add_subsetting` does the same for a plain Subsetting (NOT a
  ReferenceSubsetting -- `subsettings()` filters by exact type so the 5c subsetting
  form and the 6d framed-concern reference form never read each other's links).
- **Create-on-resolve (mirrors typing).** `_resolve_subclassifications` and
  `_resolve_subsettings` run in phase 2 and create the relationship ONLY when the
  target resolves; an ambiguous target is recorded in `ambiguous` (-> ambiguous-name),
  a non-resolving / wrong-kind target in `unresolved_supertypes` /
  `unresolved_subsettings` (-> unresolved-specialization / unresolved-subsetting).
  Because the relationship is mapping-created, these are mapping-context diagnostics
  (a reloaded model has none) -- and an ambiguous target is NOT double-reported (it is
  absent from the unresolved dicts). Subclassifications resolve BEFORE the typed-usage
  and subsetting passes so inherited-member lookup sees the supertype links.
- **Inherited resolution is a new axis in `_resolve_type`.** The resolver walks
  enclosing NAMESPACES; inheritance is orthogonal (supertypes are not in the owning
  chain). At each scope that is a Type, after owned members and before imports, it
  consults `inherited_member_named` -- a cycle-guarded breadth-first walk of
  supertypes returning the first PUBLIC member by name (own shadows inherited;
  private is not inherited; KerML local order owned -> inherited -> imported). This
  makes inheritance work for BOTH the typing path (a usage typed by an inherited
  nested definition) and the subsetting path (a usage subsetting an inherited
  feature), with no per-caller special-casing.
- **`members()` already scoped to owned (Phase 5b) pays off.** Export, round-trip,
  and duplicate detection iterate `members()` (owned members), so inherited members
  are never mistaken for a type's own -- inheritance shows up only through the
  resolver and the explicit `supertypes()`/`inherited_member_named` helpers.
- **Export / round-trip.** A `part def` re-emits `:> Super, ...` (each supertype by a
  name that re-resolves from the namespace containing the definition) and its body
  (the action-body renderer, generalized to `_type_body`); a usage re-emits `:> y`
  where the subsetted feature is emitted by a BARE name when it is an own OR INHERITED
  member (so `:> wheel` round-trips as `:> wheel`, not `:> Vehicle::wheel`), else the
  path from root. The canonical form gained `Subclassification` (definition qn,
  supertype qn) and `Subsetting` (usage qn, subsetted qn) entries, and `visit`
  recurses into part-def bodies so nested members round-trip.
- **Deferred (noted).** Subclassification/bodies on non-part definitions
  (attribute/port/connection/interface), redefinition (`:>>`), and feature-chain
  references (5e). Round-trip still does not recurse into ACTION bodies (unchanged
  from Phase 7); only part-def bodies are fingerprinted. See
  `test_inherited_members.py`.

### Completion Phase 5c-1: Inherited Members review findings fix (verified 2026-06-24)

Three review findings on the Phase 5c-1 inherited-members work (Subclassification /
Subsetting). (The canonical Redefinition surface is now its own planned Phase 5c-2.)

- **High -- inherited-name conflicts must be ambiguous, not first-wins.** The
  initial `inherited_member_named` did a BFS and returned the FIRST public inherited
  member, so `A {part x;} B {part x;} C :> A, B { part y :> x; }` silently bound `y`
  to `A::x`. Replaced it with `inherited_members_named(type_, name) -> list`, which
  returns ALL distinct candidates (deduped by id, so a diamond -- the same member via
  two paths -- is one result, but two unrelated supertypes declaring the name are
  two). `_resolve_type` now treats more-than-one inherited candidate exactly like
  more-than-one import candidate: it returns `_AMBIGUOUS`, so the conflict is
  reported `ambiguous-name` and does NOT bind. A qualified `:> A::x` sidesteps the
  conflict (it resolves `A`, then descends). The `ambiguous-name` message was
  generalized from "visible from more than one import" to "resolves to more than one
  element (ambiguous: imported or inherited)". Export's `_feature_ref_name` likewise
  emits a bare name only when it re-resolves UNAMBIGUOUSLY to the target (the sole
  inherited member of that name, with no shadowing own member), else the path.
- **Medium -- multiple unresolved supertypes collapsed to one diagnostic.**
  `_resolve_subclassifications` keyed unresolved supertypes by subtype id with
  `setdefault`, so `:> Missing1, Missing2` reported only `Missing1`.
  `MappingResult.unresolved_supertypes` is now `id -> list[str]` (every unresolved
  supertype appended), and `_check_unresolved_specializations` / the KPAR importer
  iterate the list, so each bad supertype is reported.
- **Medium -- broken persisted heritage was unvalidated.** The 5c specialization /
  subsetting rules are mapping-context only (the relationship is created only when
  the target resolves), so a hand- or API-mutated Subclassification with no
  `superclassifier`, or plain Subsetting with no `subsettedFeature`, produced no
  diagnostic and export silently dropped it. Added MODEL-DERIVED
  `_check_broken_specializations` (mirrors `_check_unresolved_imports` /
  `_check_connection_end_integrity`): `broken-subclassification` /
  `broken-subsetting`. Plain Subsetting is matched by EXACT type so the framed-concern
  ReferenceSubsetting (which carries `referencedFeature`, not `subsettedFeature`) is
  not flagged. See `test_inherited_members.py` (the 5c-2 section).
