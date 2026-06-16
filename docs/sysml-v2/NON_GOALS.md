# SysML v2 Non-Goals

The following are out of scope for the current kickoff:

- Implementing SysML v2 as SysML v1, UML, or UML stereotypes.
- Subclassing or reusing Gaphor UML element classes for SysML v2 semantics.
- Building diagrams before textual syntax, semantic mapping, validation, persistence, export, and round-trip are proven for a construct.
- Loading the full read-only standard library before the M2 tracer needs a tiny test-only fixture.
- Implementing behavior, actions, states, calculations, parametrics, analysis cases, verification cases, KPAR import/export, or the SysML v2 API client in the first vertical slice.
- Claiming support for any construct based on parser acceptance, documentation, generated class presence, or visual display alone.
- Comparing round-trip output by raw text or Gaphor element id.
- Using opaque preservation as a blanket fallback for unsupported syntax that contains untracked outbound references.
