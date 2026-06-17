# SysML v2 Support-Matrix Completion Roadmap

Goal: drive every row in `SUPPORT_MATRIX.md` to `supported` -- all nine cells
(Parse, Import, Create-API, Persist, Validate, Export, Round-trip, Diagram,
UI-edit) `yes`, each backed by conformance tests. This is the plan from the
current state to a fully filled matrix.

This is a planning artifact. Per the project's phase-stop discipline, each phase
below STOPS for human review before implementation; nothing here is built until
its phase is greenlit. Phases are sized to land green, CI-confirmed, and
honestly claimed (claim discipline: a cell advances only with a passing test).

## Current state (baseline)

- KerML kernel (18 generated classes): `internal-only` -- Create-API + Persist.
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

## Flagged dependency / risk (NOT yet scheduled as phases)

Some constructs cannot honestly reach `supported` without deeper semantics the
kickoff names as later milestones. These are risks the roadmap acknowledges but
does not yet sequence; a construct that needs them stops at `alpha` until they
land, and the affected phase will name the dependency explicitly:

- Deeper name resolution: inheritance, visibility, aliases, feature chains.
- The real read-only standard-library loader (e.g. typing by library value
  types such as `Real`/`String`; usages whose definitions live in the stdlib).
- Out of scope for this whole effort (excluded, not deferred): behavior /
  actions / states, analysis & verification cases, calculations & parametrics,
  KPAR & the SysML v2 API client, collaboration.

ConnectionUsage in particular depends on connector/end semantics, and several
usages depend on stdlib value types; these will likely cap at `alpha` until the
dependency phases are scheduled.

## Phases

Each phase = a coherent, independently shippable, CI-green increment. STOP +
human review at the end of every phase.

### Phase A -- UI foundation (unblocks UI-edit for all constructs)
Stand up the real modeling-language UI surface that every `supported` claim
needs: `toolbox_definition`, `element_types`, `diagram_types`,
`model_browser_model` for the SysML2 (and KerML where relevant) languages,
replacing the current `raise` stubs. Add a SysML2 diagram type. No per-construct
toolbox entries yet -- just the framework so later phases can register them.
Exit: the language no longer raises on these; a smoke test creates an element
via the toolbox/element-create path and projects it; gates + CI green.

### Phase B -- Promote PartDefinition / PartUsage to `supported`
On the Phase A foundation: toolbox entries that create-and-project Part def/
usage, property pages (rename, set type), and conformance tests for all nine
cells. Diagram already done. Resolves the `alpha` caveat for these two.
Exit: PartDefinition + PartUsage rows = `supported`, every cell tested.

### Phase C -- Promote Package + Attribute Def/Usage to `supported`
Diagram projection for Package (a frame/box) and Attribute def/usage (boxes);
toolbox + property pages; conformance tests. Note: AttributeUsage typed by a
primitive/value type (`attribute x : Real`) needs the stdlib-loader dependency
-- if unscheduled, this row caps at `alpha` with the dependency noted, and only
AttributeDefinition + AttributeUsage-typed-by-AttributeDefinition reach
`supported`.
Exit: Package + AttributeDefinition `supported`; AttributeUsage `supported` or
`alpha`-with-dependency, explicitly.

### Phase D -- ActionUsage: full chain + diagram + UI
First not-started construct through the entire matrix: grammar (`action`...),
mapping onto the kernel, persist/validate/export/round-trip, diagram item,
toolbox, property page, conformance tests. Establishes the template for the
remaining usages.
Exit: ActionUsage row = `supported` (or `alpha` if it hits a flagged dependency,
named).

### Phase E -- RequirementUsage: full chain + diagram + UI
As Phase D for RequirementUsage. May surface constraint/relationship semantics;
if those touch a flagged dependency, cap at `alpha` with the dependency named.
Exit: RequirementUsage row = `supported` or `alpha`-with-dependency.

### Phase F -- PortUsage: full chain + diagram + UI
As above for PortUsage. Ports introduce interface/conjugation semantics; expect
a flagged dependency to surface -- name it and cap honestly if so.
Exit: PortUsage row = `supported` or `alpha`-with-dependency.

### Phase G -- ConnectionUsage: full chain + diagram + UI
As above for ConnectionUsage; this is a relationship-style usage, so it reuses
and extends the view-only connector work. Most likely to need connector/end
semantics from a flagged dependency.
Exit: ConnectionUsage row = `supported` or `alpha`-with-dependency.

### Phase H -- KerML kernel rows: resolve `internal-only`
Decide and execute the honest end-state for the kernel rows (Element, Namespace,
Type, Feature, ...). They are structural bases, not user-facing textual
constructs, so "Parse/UI-edit" may never apply. Likely outcome: either define a
narrower `supported` surface for what they genuinely offer, or keep them
`internal-only` with a documented rationale (the matrix is "complete" when every
row's status is the honest maximum, not when every cell is forced to `yes`).
Exit: every kernel row has a final, justified status.

### Phase Z -- Dependency phases (scheduled only if needed to clear caps)
If Phases C-G leave rows capped at `alpha` on a flagged dependency, schedule the
needed dependency as its own phase here, each a substantial milestone with its
own review:
- Z1: deeper name resolution (inheritance / visibility / aliases / feature chains).
- Z2: read-only standard-library loader.
Then revisit the capped rows to promote them to `supported`.

## Definition of done

The matrix is complete when every row's status is its honest maximum and every
`yes` cell has a conformance test -- with any row that cannot reach `supported`
showing `alpha`/`internal-only` plus a documented, scheduled (or explicitly
excluded) reason. "Complete" means no silent gaps, not every cell forced green.
