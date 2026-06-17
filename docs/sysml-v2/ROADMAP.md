# SysML v2 Support-Matrix Completion Roadmap

Goal: complete `SUPPORT_MATRIX.md` honestly: every row reaches its maximum
defensible status (`supported`, `alpha` with a named dependency, or
`internal-only` with a documented rationale), and every `yes` cell is backed by
conformance tests. For user-facing constructs, `supported` still means all nine
cells (Parse, Import, Create-API, Persist, Validate, Export, Round-trip,
Diagram, UI-edit) are `yes`; structural kernel rows are not forced into
impossible Parse/UI-edit claims.

This is a planning artifact. Per the project's phase-stop discipline, each phase
below STOPS for human review before implementation; nothing here is built until
its phase is greenlit. Phases are sized to land green, CI-confirmed, and
honestly claimed (claim discipline: a cell advances only with a passing test).

## Current state (baseline)

- KerML kernel (18 generated non-enum classes): `internal-only` -- Create-API +
  Persist.
- KerML Package: `alpha` (Parse..Round-trip).
- SysML PartDefinition, PartUsage: `alpha` + Diagram (projection core).
- SysML AttributeDefinition, AttributeUsage: `alpha`.
- SysML ActionUsage, RequirementUsage, PortUsage, ConnectionUsage: `not-started`.
- Resolution scope so far: same-namespace + simple qualified name (incl. nested
  + cross-package). No inheritance / visibility / aliases / feature chains.

## What `supported` requires (per construct), beyond the current `alpha`

1. Diagram projection: a diagram item that views the element (box or line),
   created by projecting an existing element; persists/reloads; cascade-deletes.
   Relationship items need a view-only connector (see `connectors.py`).
2. UI-edit: a toolbox entry that creates the semantic element AND projects it,
   and a property page to edit it. This requires the SysML2/KerML modeling
   languages to provide real `toolbox_definition`, `element_types`,
   `diagram_types`, and `model_browser_model` (today all stubbed to raise).
3. Conformance tests covering every claimed cell, and removal of any `alpha`
   caveats that no longer hold.

## Dependency gates and risks

Some constructs cannot honestly reach `supported` without deeper semantics the
kickoff names as later milestones. These are gates, not background concerns: a
construct phase that needs one stops at `alpha`, names the dependency
explicitly, and schedules the dependency phase before claiming `supported`.

- Deeper name resolution: inheritance, visibility, aliases, feature chains.
- The real read-only standard-library loader (e.g. typing by library value types
  such as `Real`/`String`; usages whose definitions live in the stdlib). This is
  a required decision gate before primitive/value-typed AttributeUsage can be
  marked `supported`.
- Out of scope for this whole effort (excluded, not deferred): behavior /
  actions / states, analysis & verification cases, calculations & parametrics,
  KPAR & the SysML v2 API client, collaboration.

ConnectionUsage in particular depends on connector/end semantics, and several
usages depend on stdlib value types; these cap at `alpha` until the dependency
phases land.

## Phases

Each phase = a coherent, independently shippable, CI-green increment. STOP +
human review at the end of every phase.

### Phase A -- UI foundation (unblocks UI-edit for all constructs)
Stand up the real modeling-language UI surface that every `supported` claim
needs: `toolbox_definition`, `element_types`, `diagram_types`,
`model_browser_model` for the SysML2 (and KerML where relevant) languages,
replacing the current `raise` stubs. Add a SysML2 diagram type. No per-construct
toolbox entries yet -- just the framework so later phases can register them.
Exit: the language no longer raises on these; smoke tests can enumerate SysML2
element/diagram metadata and instantiate the SysML2 diagram type; gates + CI
green.

### Phase B -- Promote PartDefinition / PartUsage to `supported`
On the Phase A foundation: toolbox entries that create-and-project Part def/
usage, property pages (rename, set type), and conformance tests for all nine
cells. Diagram already done. Resolves the `alpha` caveat for these two.
Exit: PartDefinition + PartUsage rows = `supported`, every cell tested.

### Phase C1 -- Promote Package to `supported`
Add Package diagram projection (frame/box), toolbox entry, property page, and
conformance tests for all nine cells. Keep this separate from Attribute work
because package projection and namespace editing have a different risk profile.
Exit: KerML Package row = `supported`, every cell tested.

### Phase C2 -- Promote Attribute Definition/Usage
Add diagram projection for AttributeDefinition and AttributeUsage (boxes),
toolbox entries, property pages, and conformance tests. Before claiming
AttributeUsage `supported`, explicitly decide the stdlib-loader gate:
`attribute x : Real` and similar primitive/value-typed usages require the
read-only standard-library loader. If Z2 is not scheduled yet, AttributeUsage
stays `alpha` with that dependency named; AttributeDefinition and
AttributeUsage-typed-by-AttributeDefinition may still reach `supported`.
Exit: AttributeDefinition = `supported`; AttributeUsage = `supported` only if
the stdlib/value-type gate is cleared, otherwise `alpha` with named dependency.

### Phase D -- ActionUsage, split into three review gates
First not-started construct through the smaller vertical-tracer template:

1. D1 semantic chain: grammar (`action`...), mapping onto the kernel,
   Create-API, Persist, Validate, Export, and canonical Round-trip. STOP.
2. D2 diagram projection: project an existing ActionUsage as a diagram view,
   persist/reload the view, and cascade-delete it. STOP.
3. D3 UI-edit: toolbox create-and-project flow, property page, and conformance
   tests for all nine cells. STOP.

Exit: ActionUsage row = `supported`, or `alpha` with a named dependency if D1-D3
surface one.

### Phase E -- RequirementUsage, split into three review gates
Repeat the D1/D2/D3 pattern for RequirementUsage. Constraint or relationship
semantics discovered here become explicit dependency gates rather than hidden
scope creep.
Exit: RequirementUsage row = `supported` or `alpha` with named dependency.

### Phase F -- PortUsage, split into three review gates
Repeat the D1/D2/D3 pattern for PortUsage. Ports introduce interface,
conjugation, and feature-chain semantics; expect dependency gates to surface and
cap honestly if they do.
Exit: PortUsage row = `supported` or `alpha` with named dependency.

### Phase G -- ConnectionUsage, split into three review gates
Repeat the D1/D2/D3 pattern for ConnectionUsage. This is a relationship-style
usage, so the diagram phase reuses and extends the view-only connector work.
Connector/end semantics are likely a dependency gate.
Exit: ConnectionUsage row = `supported` or `alpha` with named dependency.

### Phase H -- KerML kernel rows: resolve `internal-only`
Decide and execute the honest end-state for the kernel rows (Element, Namespace,
Type, Feature, ...). They are structural bases, not user-facing textual
constructs, so "Parse/UI-edit" may never apply. Likely outcome: either define a
narrower `supported` surface for what they genuinely offer, or keep them
`internal-only` with a documented rationale (the matrix is "complete" when every
row's status is the honest maximum, not when every cell is forced to `yes`).
Exit: every kernel row has a final, justified status.

### Phase Z -- Dependency phases (scheduled to clear named caps)
If Phases C2 through G leave rows capped at `alpha` on a dependency gate,
schedule the needed dependency as its own phase here, each a substantial
milestone with its own review:
- Z1: deeper name resolution (inheritance / visibility / aliases / feature chains).
- Z2: read-only standard-library loader.
Then revisit the capped rows to promote them to `supported`.

## Definition of done

The matrix is complete when every row's status is its honest maximum and every
`yes` cell has a conformance test -- with any row that cannot reach `supported`
showing `alpha`/`internal-only` plus a documented, scheduled (or explicitly
excluded) reason. "Complete" means no silent gaps, not every cell forced green.
