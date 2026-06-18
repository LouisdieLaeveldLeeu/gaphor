# SysML v2 Support Matrix

Spec pin: OMG SysML 2.0 formal and OMG KerML 1.0 formal, published September 2025. Machine-readable abstract syntax and library artifacts are pinned to the OMG `20250201` artifact set unless `MAPPING_DECISIONS.md` records an explicit update.

Status vocabulary:

- `not-started`: no tested capability is present.
- `internal-only`: scaffolding or internal API exists, but not enough for user-facing claims.
- `alpha`: the listed cells are implemented and tested, but the construct remains early and constrained.
- `supported`: the listed construct is complete for the claimed surface and has conformance tests.

Do not advance any cell from `no` without a passing focused test. Do not use `supported` until the construct is complete end to end for the claimed surface.

The `_GeneratorSpike Element` row is **not** a SysML2/KerML semantic construct. It is the M1a feasibility-spike artifact (a single semantics-free class) and must not be read as KerML `Element` support.

M1b status (internal-only): the listed KerML kernel classes are generated from the normative MOF XMI through Gaphor's coder, and every generated kernel class has a tested create-via-`ElementFactory` and `.gaphor` save/reload (parametrized over the whole stored-reference closure — 24 classes: the original 12-class minimal kernel plus Classifier/Class/Structure and FeatureTyping (added in M2 so the kernel can serve as the supermodel the SysML layer generalizes and carry the stored typing relation), Package and DataType (the nesting namespace and the AttributeDefinition supermodel root), and the expression roots BooleanExpression/Predicate with their self-contained closure Expression/Step/Function/Behavior (added for Phase E so the SysML constraint/requirement layer generalizes a real KerML super instead of dropping it)). The five required kernel behaviours — namespace membership, type/feature relation, import resolution, delete-owner cascade, rename-updates-qualifiedName — are tested through a behaviour layer (`kerml_kernel.py`), along with delete-direction tests proving non-owning references do not cascade. These are `Create-API`+`Persist` only: there is no grammar (`Parse`), text `Import`, scoped `Validate`, `Export`, or `Round-trip` yet — those begin with M2. Derived KerML features (owner, ownedElement, owningNamespace, member, qualifiedName, ...) are not persisted; they are computed in the behaviour layer. The closure also includes `Relationship`, `AnnotatingElement`, and `Comment` plus the `FeatureDirectionKind`/`VisibilityKind` enumerations; these are generated and persistence-tested but not called out as individual rows until a milestone gives them behaviour.

| Construct | Parse | Import | Create-API | Persist | Validate | Export | Round-trip | Diagram | UI-edit | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| _GeneratorSpike Element (M1a) | no | no | yes | yes | no | no | no | no | no | internal-only |
| KerML Element | no | no | yes | yes | no | no | no | no | no | internal-only |
| KerML Namespace | no | no | yes | yes | no | no | no | no | no | internal-only |
| KerML Membership | no | no | yes | yes | no | no | no | no | no | internal-only |
| KerML OwningMembership | no | no | yes | yes | no | no | no | no | no | internal-only |
| KerML Type | no | no | yes | yes | no | no | no | no | no | internal-only |
| KerML Feature | no | no | yes | yes | no | no | no | no | no | internal-only |
| KerML Specialization | no | no | yes | yes | no | no | no | no | no | internal-only |
| KerML Import | no | no | yes | yes | no | no | no | no | no | internal-only |
| KerML Documentation | no | no | yes | yes | no | no | no | no | no | internal-only |
| KerML Package | yes | yes | yes | yes | yes | yes | yes | yes | yes | supported |
| SysML PartDefinition | yes | yes | yes | yes | yes | yes | yes | yes | yes | supported |
| SysML PartUsage | yes | yes | yes | yes | yes | yes | yes | yes | yes | supported |
| SysML AttributeDefinition | yes | yes | yes | yes | yes | yes | yes | yes | yes | supported |
| SysML AttributeUsage | yes | yes | yes | yes | yes | yes | yes | yes | yes | alpha |
| SysML ActionDefinition | yes | yes | yes | yes | yes | yes | yes | yes | yes | alpha |
| SysML ActionUsage | yes | yes | yes | yes | yes | yes | yes | yes | yes | alpha |
| SysML RequirementUsage | no | no | no | no | no | no | no | no | no | not-started |
| SysML PortUsage | no | no | no | no | no | no | no | no | no | not-started |
| SysML ConnectionUsage | no | no | no | no | no | no | no | no | no | not-started |

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

Coverage: 7 constructs round-trip-covered. Package, PartDefinition, PartUsage,
and AttributeDefinition are `supported`: every matrix cell is implemented and
focused-tested for the claimed surface. Resolution remains same-namespace +
simple/qualified name (incl. nested + cross-package).

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

AttributeUsage stays `alpha` on a named dependency. Every one of its cells is
implemented and focused-tested -- including the Diagram and UI-edit cells added
in Phase C2 -- for untyped usages and usages typed by an AttributeDefinition
through KerML FeatureTyping. It is held at `alpha` (not `supported`) because the
construct is not complete end to end: primitive / value-library typing (e.g.
`attribute x : Real`) requires the read-only standard-library loader, scheduled
as roadmap phase Z2. AttributeUsage is promoted to `supported` only once Z2
lands and `attribute x : Real` round-trips. This is the C2 standard-library gate
decision, taken explicitly per the roadmap.

Diagram cell scope. `Diagram=yes` for Package, PartDefinition, PartUsage,
AttributeDefinition, AttributeUsage, ActionDefinition, and ActionUsage means a
diagram item (an `ElementPresentation`) projects an EXISTING semantic element via
Gaphor's `subject` mechanism (never symbol-only), the view->element link persists
and reloads through `.gaphor`, and deleting the element removes its projection.
Package projection is a package frame/box view of the namespace; semantic
namespace ownership remains in the KerML ownership spine.

UI-edit scope for Package, PartDefinition, PartUsage, AttributeDefinition,
AttributeUsage, ActionDefinition, and ActionUsage. `UI-edit=yes` means the SysML2
toolbox has Package, Part Definition, Part Usage, Attribute Definition, Attribute
Usage, Action Definition, and Action Usage tools that create the semantic element
and its projection together (never symbol-only), and property pages can rename
all seven constructs. PartUsage can set/clear/replace a PartDefinition type;
AttributeUsage can set/clear/replace an AttributeDefinition type; ActionUsage can
set/clear/replace an ActionDefinition type. Re-typing replaces the stored
FeatureTyping instead of accumulating duplicates.

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
