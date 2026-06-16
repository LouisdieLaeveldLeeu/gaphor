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
| SysML PartDefinition | yes | yes | yes | yes | yes | yes | yes | no | no | alpha |
| SysML PartUsage | yes | yes | yes | yes | yes | yes | yes | no | no | alpha |
| SysML ActionUsage | no | no | no | no | no | no | no | no | no | not-started |
| SysML RequirementUsage | no | no | no | no | no | no | no | no | no | not-started |
| SysML AttributeUsage | no | no | no | no | no | no | no | no | no | not-started |
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

Coverage: 3 constructs round-trip-covered. `alpha`, not `supported`: resolution
is same-namespace + simple qualified-name only (Package adds nested-namespace
scoping and qualified names that span nesting), and Diagram/UI-edit are not yet
implemented (diagram projection is the optional deferred stretch).
