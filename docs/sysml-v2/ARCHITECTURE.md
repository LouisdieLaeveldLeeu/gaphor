# SysML v2 Architecture Scaffold

## Reused Gaphor Framework

SysML v2 reuses Gaphor's framework mechanics:

- `Base.id` provides repository identity for elements.
- `ElementFactory` is the central repository for create, lookup, select, and unlink.
- `.gaphor` persistence saves and loads `Base` properties by modeling-language namespace and element type.
- `Presentation.subject` separates diagram views from semantic elements.
- The model browser, toolbox, entry-point, and transaction services are integration points once SysML v2 has real semantic elements.

These are framework reuse points only. Existing UML and SysML v1 element classes are not SysML v2 semantic bases.

## New SysML v2 Layers

The implementation layers will be:

1. Grammar and AST: a layered KerML plus SysML textual grammar using Lark.
2. Semantic model: a generated KerML kernel, followed by SysML v2 user concepts that build on KerML.
3. Mapping: AST to semantic elements, with diagnostics.
4. Resolution: a dedicated name-resolution module.
5. Validation: structural and semantic checks with error, warning, and info severities.
6. Persistence: standard Gaphor `.gaphor` persistence through `Base` properties.
7. Export: textual SysML v2 from semantic elements.
8. Round-trip: canonical form comparison independent of raw text and ids.
9. KPAR import/export: archive inspection is done; semantic import proceeds
   next through a design contract, minimal normative-library import, then
   general user KPAR import.
10. Projection: optional diagrams as views onto semantic elements after textual and semantic paths are proven.
11. Diagram synthesis: a later product workflow that creates useful initial
    subject-bound diagrams from imported/existing semantic content. This is
    distinct from projection support: projection proves that a semantic element
    can be shown and edited on a diagram; synthesis decides which diagrams/items
    to create automatically.

## M0 Scaffold Boundary

M0 adds documentation, package and CLI placeholders, and verification gates. It does not add KerML semantic classes, SysML v2 user concepts, parser behavior, persistence behavior, validation behavior, or export behavior.

## Integration Direction

The first executable demo is CLI/Python round-trip for:

```sysml
part def Engine;
part vehicleEngine : Engine;
```

Diagram projection is a view concern. A diagram item must always project an existing semantic element or create a semantic element and then project it; symbol-only storage is out of scope. Automatic diagram synthesis from imported SysML2 text/KPAR content is a separate roadmap phase, not implied by per-construct projection support.
