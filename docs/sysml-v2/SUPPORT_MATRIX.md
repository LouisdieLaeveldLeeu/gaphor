# SysML v2 Support Matrix

Spec pin: OMG SysML 2.0 formal and OMG KerML 1.0 formal, published September 2025. Machine-readable abstract syntax and library artifacts are pinned to the OMG `20250201` artifact set unless `MAPPING_DECISIONS.md` records an explicit update.

Status vocabulary:

- `not-started`: no tested capability is present.
- `internal-only`: scaffolding or internal API exists, but not enough for user-facing claims.
- `alpha`: the listed cells are implemented and tested, but the construct remains early and constrained.
- `supported`: the listed construct is complete for the claimed surface and has conformance tests.

Do not advance any cell from `no` without a passing focused test. Do not use `supported` until the construct is complete end to end for the claimed surface.

The `_GeneratorSpike Element` row below is **not** a SysML2/KerML semantic construct. It is the M1a feasibility-spike artifact: a semantics-free class generated from the normative MOF XMI through Gaphor's coder, used only to prove the generator + persistence path. It carries no KerML semantics and must not be read as KerML `Element` support.

| Construct | Parse | Import | Create-API | Persist | Validate | Export | Round-trip | Diagram | UI-edit | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| _GeneratorSpike Element (M1a) | no | no | yes | yes | no | no | no | no | no | internal-only |
| KerML Element | no | no | no | no | no | no | no | no | no | not-started |
| KerML Namespace | no | no | no | no | no | no | no | no | no | not-started |
| KerML Membership | no | no | no | no | no | no | no | no | no | not-started |
| KerML OwningMembership | no | no | no | no | no | no | no | no | no | not-started |
| KerML Type | no | no | no | no | no | no | no | no | no | not-started |
| KerML Feature | no | no | no | no | no | no | no | no | no | not-started |
| KerML Specialization | no | no | no | no | no | no | no | no | no | not-started |
| KerML Import | no | no | no | no | no | no | no | no | no | not-started |
| KerML Documentation | no | no | no | no | no | no | no | no | no | not-started |
| SysML PartDefinition | no | no | no | no | no | no | no | no | no | not-started |
| SysML PartUsage | no | no | no | no | no | no | no | no | no | not-started |
| SysML ActionUsage | no | no | no | no | no | no | no | no | no | not-started |
| SysML RequirementUsage | no | no | no | no | no | no | no | no | no | not-started |
| SysML AttributeUsage | no | no | no | no | no | no | no | no | no | not-started |
| SysML PortUsage | no | no | no | no | no | no | no | no | no | not-started |
| SysML ConnectionUsage | no | no | no | no | no | no | no | no | no | not-started |
