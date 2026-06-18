# SysML v2 Support Matrix

Spec pin: OMG SysML 2.0 formal and OMG KerML 1.0 formal, published September 2025. Machine-readable abstract syntax and library artifacts are pinned to the OMG `20250201` artifact set unless `MAPPING_DECISIONS.md` records an explicit update.

Status vocabulary:

- `not-started`: no tested capability is present.
- `internal-only`: scaffolding or internal API exists, but not enough for user-facing claims.
- `alpha`: the listed cells are implemented and tested, but the construct remains early and constrained.
- `supported`: the listed construct is complete for the claimed surface and has conformance tests.

Do not advance any cell from `no` without a passing focused test. Do not use `supported` until the construct is complete end to end for the claimed surface.

The `_GeneratorSpike Element` row is **not** a SysML2/KerML semantic construct. It is the M1a feasibility-spike artifact (a single semantics-free class) and must not be read as KerML `Element` support.

M1b status (internal-only): the listed KerML kernel classes are generated from the normative MOF XMI through Gaphor's coder, and every generated kernel class has a tested create-via-`ElementFactory` and `.gaphor` save/reload (parametrized over the whole stored-reference closure — 16 classes: the original 12-class minimal kernel plus Classifier/Class/Structure and FeatureTyping, added in M2 so the kernel can serve as the supermodel the SysML layer generalizes and carry the stored typing relation). The five required kernel behaviours — namespace membership, type/feature relation, import resolution, delete-owner cascade, rename-updates-qualifiedName — are tested through a behaviour layer (`kerml_kernel.py`), along with delete-direction tests proving non-owning references do not cascade. These are `Create-API`+`Persist` only: there is no grammar (`Parse`), text `Import`, scoped `Validate`, `Export`, or `Round-trip` yet — those begin with M2. Derived KerML features (owner, ownedElement, owningNamespace, member, qualifiedName, ...) are not persisted; they are computed in the behaviour layer. The closure also includes `Relationship`, `AnnotatingElement`, and `Comment` plus the `FeatureDirectionKind`/`VisibilityKind` enumerations; these are generated and persistence-tested but not called out as individual rows until a milestone gives them behaviour.

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
| KerML Package | yes | yes | yes | yes | yes | yes | yes | no | no | alpha |
| SysML PartDefinition | yes | yes | yes | yes | yes | yes | yes | yes | yes | supported |
| SysML PartUsage | yes | yes | yes | yes | yes | yes | yes | yes | yes | supported |
| SysML AttributeDefinition | yes | yes | yes | yes | yes | yes | yes | no | no | alpha |
| SysML AttributeUsage | yes | yes | yes | yes | yes | yes | yes | no | no | alpha |
| SysML ActionUsage | no | no | no | no | no | no | no | no | no | not-started |
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

Coverage: 5 constructs round-trip-covered. PartDefinition and PartUsage are
`supported`: every matrix cell is implemented and focused-tested. Package,
AttributeDefinition, and AttributeUsage remain `alpha`; their missing diagram and
UI-edit cells are tracked in the roadmap. Resolution remains same-namespace +
simple/qualified name (incl. nested + cross-package). Note: AttributeUsage typing
is by an AttributeDefinition; the distinct primitive/value-type axis (e.g.
`attribute x : Real`) is later work -- this construct establishes the attribute
definition/usage pattern on a DataType base, not full value-type semantics.

Diagram cell scope. `Diagram=yes` for PartDefinition means the projection core:
a box item (an `ElementPresentation`) projects an EXISTING PartDefinition or
PartUsage via Gaphor's `subject` mechanism (never symbol-only), the
view->element link persists and reloads through `.gaphor`, and deleting the
element removes its projection.

UI-edit scope for PartDefinition/PartUsage. `UI-edit=yes` means the SysML2
toolbox has Part Definition and Part Usage tools that create the semantic
element and its projection together (never symbol-only), and property pages can
rename both constructs and set/clear/replace a PartUsage's PartDefinition type.
Re-typing replaces the stored FeatureTyping instead of accumulating duplicates.

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
