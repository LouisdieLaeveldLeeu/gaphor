# CLAUDE.md

## SysML v2 Invariants

These rules are durable project constraints for SysML v2 work in Gaphor.

1. SysML v2 is independent from UML. Do not subclass or reuse Gaphor's UML element classes for SysML2 semantics.
2. KerML is the semantic base. SysML v2 user concepts are built on the KerML kernel, never directly on Gaphor primitives.
3. Textual syntax is the core entry point. Diagrams come after text, semantics, validation, persistence, and export already work for a construct.
4. Diagrams are projections, not storage. The semantic element is the truth; a diagram item is a view onto it through Gaphor's subject mechanism.
5. Validation is built in, not bolted on.
6. Import/export is tested by round-trip, not by inspection.
7. Python access is first-class. Every construct is creatable and queryable from Python.
8. Unsupported constructs are explicit: preserved-and-warned only when safely losslessly preservable, or reported as an error. Never silently drop syntax.
9. Every supported construct is real end to end, with the full M2 chain passing.
10. Conformance is proven by tests, not by claims.

## Claim Discipline

Never describe a construct or capability as supported until its row in `docs/sysml-v2/SUPPORT_MATRIX.md` is genuinely complete for the claimed capability. Under-claim by default.

## Phase Stops

- M0 stops after recon, scaffold, verification, and commit for human review.
- Do not build the KerML kernel before M0 approval.
- M2 stops after the first vertical round-trip result and coverage baseline for human review.
