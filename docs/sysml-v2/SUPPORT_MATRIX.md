# SysML v2 Support Matrix

Spec pin: OMG SysML 2.0 formal and OMG KerML 1.0 formal, published September 2025. Machine-readable abstract syntax and library artifacts are pinned to the OMG `20250201` artifact set unless `MAPPING_DECISIONS.md` records an explicit update.

Status vocabulary:

- `not-started`: no tested capability is present.
- `internal-only`: a generated structural kernel base used by the SysML2 layer,
  with tested Create-API + Persist + behaviour, but no user-facing textual
  surface. For these rows `internal-only` is the **final, honest maximum**, not a
  way-station to `supported` (see "KerML kernel rows" below).
- `alpha`: the listed cells are implemented and tested, but the construct remains early and constrained.
- `supported`: the listed user-facing construct is complete for the claimed surface (the full nine cells) and has conformance tests.

Cell values: `yes` (implemented and focused-tested), `no` (not yet implemented),
and `n/a` (not applicable by design — the cell's capability does not exist for
this kind of row, e.g. there is no textual syntax for a structural kernel base,
so Parse/Import/Export/Diagram/UI-edit cannot apply). `n/a` is NOT a missing-work
marker; it is a deliberate, justified "this never applies here".

Do not advance any cell from `no` without a passing focused test. Do not use `supported` until the construct is complete end to end for the claimed surface.

KerML kernel rows (Phase H decision). The KerML structural bases (Element,
Namespace, Membership, Type, Feature, Specialization, Import, Documentation, ...)
are generated infrastructure that the SysML2 user constructs build on; they have
no textual concrete syntax (you never write `Feature x;`). Their honest maximum
is `internal-only`: Create-API and Persist are real and tested, the five kernel
behaviours are tested, but Parse, text Import, Export, Diagram, and UI-edit are
`n/a` -- not missing work. They are deliberately NOT promoted to `supported` and
no `kernel-supported` status is invented, because `supported` means a user-facing
construct with the full nine-cell surface; conflating the two would weaken the
vocabulary. Evidence for these rows: generated from the pinned OMG XMI, created
via `ElementFactory`, persist/reload, and behaviour tests for ownership,
membership, typing, imports, delete cascade, and qualified names.

M1b status (internal-only): the listed KerML kernel classes are generated from the normative MOF XMI through Gaphor's coder, and every generated kernel class has a tested create-via-`ElementFactory` and `.gaphor` save/reload (parametrized over the whole stored-reference closure — 28 classes: the original 12-class minimal kernel plus Classifier/Class/Structure and FeatureTyping (added in M2 so the kernel can serve as the supermodel the SysML layer generalizes and carry the stored typing relation), Package and DataType (the nesting namespace and the AttributeDefinition supermodel root), and the expression roots BooleanExpression/Predicate with their self-contained closure Expression/Step/Function/Behavior (added for Phase E so the SysML constraint/requirement layer generalizes a real KerML super instead of dropping it), the relationship roots AssociationStructure/Connector with their closure Association (added for Phase G so the SysML connection layer generalizes a real KerML super; Connector's end properties are derived and never persisted), and Conjugation (added for Phase 8a so the SysML port-conjugation layer generalizes a real KerML super; its originalType/conjugatedType reference Type and `conjugator` is derived, so it adds no new stored closure)). The five required kernel behaviours — namespace membership, type/feature relation, import resolution, delete-owner cascade, rename-updates-qualifiedName — are tested through a behaviour layer (`kerml_kernel.py`), along with delete-direction tests proving non-owning references do not cascade. These rows are `Create-API`+`Persist`; their Parse, text Import, scoped Validate, Export, Round-trip, Diagram, and UI-edit cells are `n/a` (not applicable by design — a structural kernel base has no textual concrete syntax), the final state decided in Phase H, not work pending a later milestone. Derived KerML features (owner, ownedElement, owningNamespace, member, qualifiedName, ...) are not persisted; they are computed in the behaviour layer. The closure also includes `Relationship`, `AnnotatingElement`, and `Comment` plus the `FeatureDirectionKind`/`VisibilityKind` enumerations; these are generated and persistence-tested but not called out as individual rows until a milestone gives them behaviour.

| Construct | Parse | Import | Create-API | Persist | Validate | Export | Round-trip | Diagram | UI-edit | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| KerML Element | n/a | n/a | yes | yes | n/a | n/a | n/a | n/a | n/a | internal-only |
| KerML Namespace | n/a | n/a | yes | yes | n/a | n/a | n/a | n/a | n/a | internal-only |
| KerML Membership | n/a | n/a | yes | yes | n/a | n/a | n/a | n/a | n/a | internal-only |
| KerML OwningMembership | n/a | n/a | yes | yes | n/a | n/a | n/a | n/a | n/a | internal-only |
| KerML Type | n/a | n/a | yes | yes | n/a | n/a | n/a | n/a | n/a | internal-only |
| KerML Feature | n/a | n/a | yes | yes | n/a | n/a | n/a | n/a | n/a | internal-only |
| KerML Specialization | n/a | n/a | yes | yes | n/a | n/a | n/a | n/a | n/a | internal-only |
| KerML Import | n/a | n/a | yes | yes | n/a | n/a | n/a | n/a | n/a | internal-only |
| KerML Documentation | n/a | n/a | yes | yes | n/a | n/a | n/a | n/a | n/a | internal-only |
| KerML Package | yes | yes | yes | yes | yes | yes | yes | yes | yes | supported |
| SysML PartDefinition | yes | yes | yes | yes | yes | yes | yes | yes | yes | supported |
| SysML PartUsage | yes | yes | yes | yes | yes | yes | yes | yes | yes | supported |
| SysML AttributeDefinition | yes | yes | yes | yes | yes | yes | yes | yes | yes | supported |
| SysML AttributeUsage | yes | yes | yes | yes | yes | yes | yes | yes | yes | supported |
| SysML ActionDefinition | yes | yes | yes | yes | yes | yes | yes | yes | yes | alpha |
| SysML ActionUsage | yes | yes | yes | yes | yes | yes | yes | yes | yes | alpha |
| SysML ConstraintDefinition | yes | yes | yes | yes | yes | yes | yes | yes | yes | alpha |
| SysML ConstraintUsage | yes | yes | yes | yes | yes | yes | yes | yes | yes | alpha |
| SysML RequirementDefinition | yes | yes | yes | yes | yes | yes | yes | yes | yes | alpha |
| SysML RequirementUsage | yes | yes | yes | yes | yes | yes | yes | yes | yes | alpha |
| SysML PortDefinition | yes | yes | yes | yes | yes | yes | yes | yes | yes | supported |
| SysML PortUsage | yes | yes | yes | yes | yes | yes | yes | yes | yes | supported |
| SysML ConnectionDefinition | yes | yes | yes | yes | yes | yes | yes | yes | yes | supported |
| SysML ConnectionUsage | yes | yes | yes | yes | yes | yes | yes | yes | yes | supported |

## Round-Trip Coverage Metric

The growing coverage metric is the project's north-star dashboard: a construct
counts as covered only when it passes the canonical-form round-trip
(import -> save -> reload -> export -> re-parse, comparing structure and resolved
references, never ids or raw text). M2 establishes the harness
(`gaphor/SysML2/roundtrip.py`) and the first rows.

| Construct | Round-trip covered | Harness test |
| --- | --- | --- |
| SysML PartDefinition | yes | `test_roundtrip.py::test_tracer_round_trip_preserves_canonical_form` |
| SysML PartUsage (typed + untyped) | yes | `test_roundtrip.py` |
| KerML Package (nested) | yes | `test_roundtrip.py::test_nested_package_round_trips` |
| SysML AttributeDefinition | yes | `test_roundtrip.py::test_attribute_definition_and_usage_round_trip` |
| SysML AttributeUsage (typed) | yes | `test_roundtrip.py` |
| SysML ActionDefinition | yes | `test_roundtrip.py::test_action_definition_and_usage_round_trip` |
| SysML ActionUsage (typed) | yes | `test_roundtrip.py` |
| SysML ConstraintDefinition | yes | `test_roundtrip.py::test_constraint_definition_and_usage_round_trip` |
| SysML ConstraintUsage (typed) | yes | `test_roundtrip.py` |
| SysML RequirementDefinition | yes | `test_roundtrip.py::test_requirement_definition_and_usage_round_trip` |
| SysML RequirementUsage (typed) | yes | `test_roundtrip.py` |
| SysML PortDefinition | yes | `test_roundtrip.py::test_port_definition_and_usage_round_trip` |
| SysML PortUsage (typed) | yes | `test_roundtrip.py` |
| SysML PortUsage (conjugated `~`) | yes | `test_port_conjugation.py::test_conjugated_port_round_trips` |
| SysML ConnectionDefinition | yes | `test_roundtrip.py::test_connection_definition_and_usage_round_trip` |
| SysML ConnectionUsage (typed) | yes | `test_roundtrip.py` |

Coverage: 15 constructs round-trip-covered. Package, PartDefinition, PartUsage,
and AttributeDefinition are `supported`: every matrix cell is implemented and
focused-tested for the claimed surface. Resolution remains same-namespace +
simple/qualified name (incl. nested + cross-package). Typing is kind-specific: a
usage is typed by exactly its own definition kind (a cross-kind type such as
`part p : AttributeDefinition` is a `type-kind-mismatch` error, not silently
accepted).

ActionDefinition and ActionUsage have all nine cells implemented and
focused-tested -- the seven semantic cells (D1), the Diagram cell (D2), and the
UI-edit cell (D3) -- for untyped actions and actions typed by an ActionDefinition
through KerML FeatureTyping (`action def Brake; action emergencyBrake : Brake;`).
The action FeatureTyping projects as a connected line view, the toolbox creates
the semantic element and its projection together, and property pages rename both
constructs and set/clear/replace an ActionUsage's ActionDefinition type (re-typing
replaces the stored FeatureTyping, no duplicates). Despite every cell being `yes`,
both rows are deliberately held at `alpha`, NOT `supported`, on a named behavioral
dependency: SysML actions also carry behavior not modeled here -- action bodies /
nested steps, succession and flow connections, and parameters. Only the
declaration-and-typing surface is proven; promotion to `supported` waits until
that behavioral surface is scheduled and built. This is the Phase-D behavioral
gate decision, taken explicitly per the roadmap.

ConstraintDefinition/Usage and RequirementDefinition/Usage (Phase E) have all
nine cells implemented and focused-tested for the declaration-and-typing surface
(`constraint def Limit; constraint c : Limit; requirement def MassReq;
requirement r : MassReq;`). RequirementDefinition/Usage generalize
ConstraintDefinition/Usage, which generalize the KerML expression roots
Predicate/BooleanExpression (added to the kernel as the Phase E prerequisite, so
the chain is faithful, not lossy). The diagram cell projects each as a
subject-bound box and projects the FeatureTyping line; the UI-edit cell adds
toolbox create-and-project tools, declared-name editing, and a single type page
that types a ConstraintUsage by a ConstraintDefinition and a RequirementUsage by
a RequirementDefinition (one page, never two dropdowns on the requirement). Like
actions, all four rows are deliberately held at `alpha`, NOT `supported`, on a
named dependency: a constraint's actual content -- its boolean expression body
(the predicate `{ ... }`) -- and a requirement's `subject`/`assume`/`require`
parameter parts are not modeled. Only the declaration-and-typing surface is
proven; promotion waits until the constraint-expression surface is scheduled and
built. This is the Phase-E constraint-expression gate decision, taken explicitly
per the roadmap.

PortDefinition and PortUsage are `supported` for the declaration-and-typing
surface INCLUDING conjugation (`port def Fuel; port p : Fuel; port q : ~Fuel;`).
Phase F first built the unconjugated surface (every cell implemented and
focused-tested; PortDefinition generalizes Structure/OccurrenceDefinition and
PortUsage generalizes OccurrenceUsage -> ... -> Feature, so no kernel growth was
needed), and held both rows at `alpha` on a named dependency: port conjugation
and interface / flow-direction semantics were unmodeled.

Phase 8a delivered port conjugation faithfully and lifted the rows to
`supported`. KerML `Conjugation` (kernel) and SysML `PortConjugation`,
`ConjugatedPortDefinition`, `ConjugatedPortTyping` are generated from the pinned
XMI; `port p : ~Fuel` types `p` by the original's implicit conjugate through a
ConjugatedPortTyping (the conjugate + its PortConjugation are owned by the
original, cascade on delete, and are invisible to name resolution, duplicate
checks, and textual export). Every cell now covers conjugation: Parse/Import
(`: ~<type>`, port-scoped), Create-API/Persist (`conjugation.set_conjugated_port_type`
+ `.gaphor` round-trip), Validate (non-port target -> mistyped; dangling
conjugate -> `broken-conjugation`, model-derived), Export/Round-trip (re-emits
`~Fuel`; the canonical form distinguishes `: Fuel` from `: ~Fuel`), Diagram (a
conjugated port projects as a subject-bound PortUsageItem; the conjugate is never
projectable), and UI-edit (the PortUsage type page's conjugation toggle).

Flow direction `in`/`out`/`inout` on ports (and all other usages) was since added
in Phase 8b -- see the feature-direction note below. Still explicitly OUT of the
promoted port surface, scheduled as a named follow-up (not silently implied by
`supported`): InterfaceDefinition / InterfaceUsage semantics (Phase 8c). This was
the Phase-8a port-conjugation gate decision, taken explicitly per the roadmap.

Feature direction (Phase 8b) is supported on ALL usages (Part/Attribute/Action/
Constraint/Requirement/Port/Connection): `in`/`out`/`inout` parse, map to the
nullable KerML `Feature::direction`, export, round-trip, show in the diagram
label, and edit via a direction property page; undirected is the absent (None)
state, distinct from `in`. This adds direction to the existing declaration-and-
typing surface of each usage, so it changes no row's status: the already-
`supported` rows (Part*, Attribute*, Port*, Connection*) now also cover direction,
and the `alpha` rows (Action*, Constraint*, Requirement*) gain direction while
staying capped on their other named dependencies. The nullable enum is a scoped
coder generation rule (opt-in), so Gaphor's UML/Core/SysML/RAAML stay unchanged.

ConnectionDefinition and ConnectionUsage (Phase G) have all nine cells
implemented and focused-tested for the declaration-and-typing surface
(`connection def C; connection c : C;`). ConnectionDefinition generalizes
{AssociationStructure, PartDefinition} and ConnectionUsage generalizes
{ConnectorAsUsage -> Connector, PartUsage}; the KerML relationship roots
AssociationStructure/Connector were added to the kernel as the Phase G
prerequisite, so the chain is faithful. Because ConnectionUsage IS a PartUsage
(and ConnectionDefinition IS a PartDefinition), the export/round-trip/diagram/UI
paths all treat the more-derived connection kind first: a connection renders as
`connection`, projects as a ConnectionUsageItem (not the inherited part item),
and its type page lists ConnectionDefinitions only -- the PartUsage type page
defers for a connection so it never gets a second, wrong-kind dropdown. Both rows
are `supported` (Phase 9) for the binary, non-chain connector-end surface. A
`connection c connect a to b;` resolves each endpoint nearest-first to a feature
and stores it as the connector's `source`/`target`; broken or non-feature
endpoints are validated (`broken-connection-end`); the connection exports its
connect clause and round-trips (the canonical form carries the endpoint qualified
names); and it projects as a LINE whose head/tail bind to the source/target items
(a view onto the connector ends -- anchoring or drawing authors the ends without
duplicating the connection). See `test_connection_ends.py` and the connection
line-binding tests in `test_diagram_projection.py`.

Deferred (named follow-up): feature-chain endpoints (`connect a.b to c.d`) depend
on Phase 5e, and n-ary/unnamed connection forms are later work -- both beyond the
binary non-chain surface promoted here.

AttributeUsage is `supported` (Phase 4). Every cell is implemented and
focused-tested for untyped usages, usages typed by an in-model AttributeDefinition
through KerML FeatureTyping, AND usages typed by a standard-library value type
(e.g. `attribute x : Real`). The library dependency that previously capped it at
`alpha` is now satisfied by the KPAR path (Phases 3a-3b): the mapper resolves a
value-type name against the pinned `ScalarValues` library and types the attribute
through a read-only library value-type proxy (a `kerml.DataType` materialized in
the user model, invisible to textual export and the canonical form). The full
chain -- parse, map, validate, export, round-trip, persist, diagram, and UI-edit
(the property page also offers the library value types) -- passes focused tests
for `attribute x : Real` and related primitive value types. See
`test_attribute_value_typing.py`.

Diagram cell scope. `Diagram=yes` for Package, PartDefinition, PartUsage,
AttributeDefinition, AttributeUsage, ActionDefinition, ActionUsage,
ConstraintDefinition, ConstraintUsage, RequirementDefinition, RequirementUsage,
PortDefinition, PortUsage, ConnectionDefinition, and ConnectionUsage means a
diagram item (an `ElementPresentation`) projects an EXISTING semantic element via
Gaphor's `subject` mechanism (never symbol-only), the view->element link persists
and reloads through `.gaphor`, and deleting the element removes its projection.
Package projection is a package frame/box view of the namespace; semantic
namespace ownership remains in the KerML ownership spine.

UI-edit scope for Package, PartDefinition, PartUsage, AttributeDefinition,
AttributeUsage, ActionDefinition, ActionUsage, ConstraintDefinition,
ConstraintUsage, RequirementDefinition, RequirementUsage, PortDefinition,
PortUsage, ConnectionDefinition, and ConnectionUsage. `UI-edit=yes` means the
SysML2 toolbox has a create-and-project tool for each (never symbol-only), and
property pages can rename every one of them. PartUsage can set/clear/replace a
PartDefinition type; AttributeUsage an AttributeDefinition; ActionUsage an
ActionDefinition; ConstraintUsage a ConstraintDefinition; RequirementUsage a
RequirementDefinition (a single type page serves both constraint and requirement
usages, choosing the definition kind from the subject's own type, so a
RequirementUsage never gets two dropdowns); PortUsage a PortDefinition; and
ConnectionUsage a ConnectionDefinition (the PartUsage type page defers for a
ConnectionUsage, so the connection -- a PartUsage subclass -- never gets a second,
wrong-kind dropdown). Re-typing replaces the stored FeatureTyping instead of
accumulating duplicates.

The FeatureTyping relation projects as a line (`FeatureTypingItem`) whose
`subject` is the EXISTING typing -- it appears only when both ends are already
projected, binds the existing element (no duplicate), persists/reloads, and
cascade-deletes. The line's handles ARE anchored to the endpoint box items via a
custom connector (`FeatureTypingConnect`) that reuses the existing subject
instead of the default find-or-create connector (which would duplicate the
typing on connect). So the typing line is now a fully visually-wired view of an
existing relation. (No separate `FeatureTyping` matrix row: it is a relationship
view that accompanies the PartUsage/PartDefinition rows, not a standalone
construct claim.)
