# SysML v2 Non-Goals

The original kickoff non-goals protected the first vertical slice from going
wide before the generated KerML/SysML2 path, persistence, validation, export,
round-trip, diagram projection, and UI-edit surfaces were proven. The project has
now moved past that boundary. These are the current non-goals:

- Implementing SysML v2 as SysML v1, UML, or UML stereotypes.
- Subclassing or reusing Gaphor UML element classes for SysML v2 semantics.
- Claiming support for a construct before textual syntax, semantic mapping,
  validation, persistence, export, round-trip, diagram projection, UI-edit, and
  focused tests are complete for the claimed surface.
- Claiming support for any construct based on parser acceptance, documentation, generated class presence, or visual display alone.
- Comparing round-trip output by raw text or Gaphor element id.
- Using opaque preservation as a blanket fallback for unsupported syntax that contains untracked outbound references.

KPAR is no longer a blanket non-goal. Pinned KPAR artifacts and read-only archive
inspection have landed; semantic KPAR import is now the next completion track in
three stages (import design contract, minimal normative-library import, general
user KPAR import), followed later by KPAR export/round-trip. The SysML v2
API/client surface is also no longer dismissed by the old kickoff boundary; it is
a later decision phase and must remain separate from Gaphor's internal identity
model unless that phase proves a concrete API-facing need.
