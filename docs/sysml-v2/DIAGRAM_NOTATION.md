# SysML v2 Diagram Notation Mapping

The authority is the pinned OMG **SysML v2 Language** spec (`formal/26-03-02`,
`docs/sysml-v2/omg/20250201/SysML-v2-Language.pdf`), clause **8.2.3 Graphical
Notation** and its sub-clauses, plus the **KerML** spec (`formal/26-03-01`) for the
kernel-level relationship lines. This table is the contract for the faithful diagram
notation (Phase 15): one row per implemented, projectable construct.

Per **8.2.3.6 Definition and Usage Graphical Notation** every definition/usage node is
a *compartment stack*: a **name compartment** holding the keyword in guillemets
(`«<keyword> def»` for a definition, `«<keyword>»` for a usage) over the
`[direction] name [: Type]` line, followed by zero or more **labelled feature
compartments** shown only when non-empty. The shared toolkit is
`gaphor/SysML2/shapes.py`.

Prefixes noted in the spec (`abstract`, `variation`, `ref`, `individual`, visibility)
are a refinement tracked within Phase 15; this table fixes the base keyword,
compartments, and shape.

## Nodes (definitions and usages)

| Construct | Definition keyword | Usage keyword | Node shape | Feature compartments | Spec clause |
| --- | --- | --- | --- | --- | --- |
| Package | — | `«package»` (rendered as the folder/tab shape) | folder | packages / members | 8.2.3.5 |
| Part | `«part def»` | `«part»` | rectangle | `attributes`, `ports`, `parts`, `references`, `actions`, … | 8.2.3.11 |
| Attribute | `«attribute def»` | `«attribute»` | rectangle | `attributes` | 8.2.3.7 |
| Action | `«action def»` | `«action»` | rounded rectangle | `parameters`, `actions`, steps | 8.2.3.17 |
| Constraint | `«constraint def»` | `«constraint»` | rectangle | `parameters`, constraint expression | 8.2.3.20 |
| Requirement | `«requirement def»` | `«requirement»` | rectangle | `subject`, `doc` text, `assume`/`require` constraints, `actor`, `stakeholder` | 8.2.3.21 |
| Concern | `«concern def»` | `«concern»` | rectangle | framed `stakeholder`s, `subject` | 8.2.3.21 |
| Port | `«port def»` | `«port»` | PortUsage: small square on the OWNER's boundary (`~Original` label when conjugated). Per-diagram `PortDisplayMode` (boundary default / compartment / both_debug) selects boundary squares vs. a `ports` compartment vs. both -- presentation only, one PortUsage. PortDefinition: a box. | flow features | 8.2.3.12 |
| Connection | `«connection def»` | `«connection»` (usage rendered as a line) | rectangle / line | ends | 8.2.3.13 |
| Interface | `«interface def»` | `«interface»` (usage rendered as a line between ports) | rectangle / line | ends | 8.2.3.13–.14 |
| Flow | — | `«flow»` (rendered as a directed line) | line | — | 8.2.3.13 |
| Succession | — | `«succession»` (rendered as an arrow) | line | — | 8.2.3.17 |

## Relationship lines

| Relationship | Notation | Spec clause |
| --- | --- | --- |
| FeatureTyping (`: Type`) | solid line, hollow (unfilled) triangle arrowhead toward the type; usually shown inline as `: Type` in the name line | KerML typing / 8.2.3.6 |
| Specialization (`:>` / `specializes`) | solid line, hollow triangle arrowhead toward the general | KerML specialization |
| Subsetting (`:>` / `subsets`) | solid line, open arrowhead, `«subsets»` | KerML subsetting |
| Redefinition (`:>>` / `redefines`) | solid line, open arrowhead, `«redefines»` | KerML redefinition |
| Connection usage | solid line between the connected features, labelled with the connection name | 8.2.3.13 |
| Interface usage | solid line between ports | 8.2.3.13–.14 |
| Succession | solid line, filled arrowhead (control flow) | 8.2.3.17 |
| Flow | solid line, open arrowhead, item label (payload) | 8.2.3.13 |

## Toolkit → items

`gaphor/SysML2/shapes.py` provides: `sysml_keyword` / `keyword_label` (metaclass →
keyword, MRO-matched), `name_label` (`[direction] name [: Type]`), `name_compartment`,
`features_compartment(label, features)`, and `node_shape(item, *compartments)`. Each
`gaphor/SysML2/diagramitems.py` item composes its shape from these (Phase 15 wiring),
so every projected construct's notation traces to a row above.
