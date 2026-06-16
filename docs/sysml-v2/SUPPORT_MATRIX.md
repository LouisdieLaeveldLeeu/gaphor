# SysML v2 Support Matrix

Spec pin: OMG SysML 2.0 formal and OMG KerML 1.0 formal, published September 2025. Machine-readable abstract syntax and library artifacts are pinned to the OMG `20250201` artifact set unless `MAPPING_DECISIONS.md` records an explicit update.

Status vocabulary:

- `not-started`: no tested capability is present.
- `internal-only`: scaffolding or internal API exists, but not enough for user-facing claims.
- `alpha`: the listed cells are implemented and tested, but the construct remains early and constrained.
- `supported`: the listed construct is complete for the claimed surface and has conformance tests.

Do not advance any cell from `no` without a passing focused test. Do not use `supported` until the construct is complete end to end for the claimed surface.

The `_GeneratorSpike Element` row is **not** a SysML2/KerML semantic construct. It is the M1a feasibility-spike artifact (a single semantics-free class) and must not be read as KerML `Element` support.

M1b status (internal-only): the listed KerML kernel classes are generated from the normative MOF XMI through Gaphor's coder, and every generated kernel class has a tested create-via-`ElementFactory` and `.gaphor` save/reload (parametrized over the whole 29-class closure). The five required kernel behaviours — namespace membership, type/feature relation, import resolution, delete-owner cascade, rename-updates-qualifiedName — are tested through a behaviour layer (`kerml_kernel.py`). These are `Create-API`+`Persist` only: there is no grammar (`Parse`), text `Import`, scoped `Validate`, `Export`, or `Round-trip` yet — those begin with M2. The kernel also defines structural classes beyond the listed eight (the closure includes specialization/feature-relationship and annotation classes plus the `FeatureDirectionKind`/`VisibilityKind` enumerations); they are generated and persistence-tested but are not called out as individual rows until a milestone gives them behaviour.

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
| SysML PartDefinition | no | no | no | no | no | no | no | no | no | not-started |
| SysML PartUsage | no | no | no | no | no | no | no | no | no | not-started |
| SysML ActionUsage | no | no | no | no | no | no | no | no | no | not-started |
| SysML RequirementUsage | no | no | no | no | no | no | no | no | no | not-started |
| SysML AttributeUsage | no | no | no | no | no | no | no | no | no | not-started |
| SysML PortUsage | no | no | no | no | no | no | no | no | no | not-started |
| SysML ConnectionUsage | no | no | no | no | no | no | no | no | no | not-started |
