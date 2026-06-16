# SysML v2 Mapping Decisions

## M0 Metamodel-Generation Finding

Sources checked:

- OMG SysML 2.0 specification page: https://www.omg.org/spec/SysML/2.0/About-SysML
- OMG KerML 1.0 specification page: https://www.omg.org/spec/KerML/1.0/About-KerML
- OMG final-adoption announcement: https://www.omg.org/news/releases/pr2025/07-21-25.htm
- Systems Modeling Community release repository: https://github.com/Systems-Modeling/SysML-v2-Release
- Systems Modeling Community releases: https://github.com/Systems-Modeling/SysML-v2-Release/releases

### What Gaphor Currently Generates From

Gaphor's current model-code pipeline generates Python model modules from checked-in Gaphor model files, not from arbitrary external Ecore, MOF XMI, or Eclipse XMI.

- `pyproject.toml` defines `poe` tasks that call `gaphor.codegen.coder:main`.
- `gaphor.codegen.coder` loads `.gaphor` model files through `gaphor.storage.load`.
- Current generated modules include `gaphor/core/modeling/coremodel.py`, `gaphor/UML/uml.py`, `gaphor/SysML/sysml.py`, `gaphor/RAAML/raaml.py`, and `gaphor/C4Model/c4model.py`.
- `tests/test_models_up_to_date.py` verifies generated output equals the checked-in generated modules.

This means M1a must prove an adapter path from normative SysML/KerML artifacts into the Gaphor generator's accepted model shape before the KerML kernel is built on it.

### Which SysML2 Artifacts Are Usable

Usable M0 inputs:

- OMG formal SysML 2.0 and KerML 1.0 specification documents for conformance authority.
- OMG normative MOF XMI for the SysML and KerML abstract syntax as metamodel source input.
- OMG normative KPAR library artifacts for standard-library interchange when that phase arrives.
- JSON schemas for abstract syntax and project interchange, mainly for future validation and API alignment.
- Systems Modeling Community release BNF files as parser seed material, cross-checked against the formal PDFs.
- Textual standard-library files in the release repository as readable fixtures and cross-checks, not as the sole conformance authority.

### Normative vs Reference Artifacts

Normative for this effort:

- OMG formal SysML 2.0 Language specification.
- OMG formal KerML 1.0 specification.
- OMG MOF XMI abstract syntax files for SysML and KerML.
- OMG KPAR model interchange projects listed as normative machine-readable documents.

Reference or convenience artifacts:

- Systems Modeling Community release repository packaging.
- Extracted `.kebnf`, `.kgbnf`, and HTML BNF files. They are derived from the specifications and useful for parser work, but must be checked against the formal docs when ambiguity or correction notes appear.
- Release repository XMI library representations using Eclipse XMI. Release notes state these are not fully normative OMG XMI.
- Pilot implementation behavior and Xtext grammar. These are useful comparators, not automatic conformance authority.

### Realistic Generator Path

Use a two-step generator strategy:

1. M1a imports a small normative MOF XMI slice into an intermediate mapping model and emits one generated, semantics-free Gaphor `Base` subclass with generated attributes and references.
2. Only after that generated class persists and reloads through `.gaphor`, extend the path to the minimal KerML kernel in M1b.

Do not hand-author the KerML or SysML metamodel as production code unless M1a proves the generation path unviable and a new human-approved plan replaces this decision.

## Grammar Tool

Decision: use Lark for the first SysML v2 textual grammar.

Tradeoff:

- Lark is pure Python, fits Gaphor packaging better, supports EBNF-style grammar composition, and is simple to exercise in pytest.
- ANTLR tracks the broader tooling ecosystem more closely and has a mature grammar workflow, but adds a Java-oriented toolchain and generated parser lifecycle that is heavier for Gaphor.

The grammar is one layered grammar: SysML textual notation extends KerML textual notation. Port from the BNF, not from intuition. Pilot/Xtext behavior may be used to understand ambiguities, not as the source of truth.

Lark is declared as a core dependency in `pyproject.toml` (`lark>=1.1,<2`, locked to 1.3.1 on 2026-06-16). It is a core dependency rather than an optional extra because SysML2 is registered as a first-class modeling language and is auto-loaded like UML/SysML/C4Model; a base install without it would fail once the parser layer imports `lark`. Being pure Python, Lark adds no build/ABI burden. No code imports it yet — it is staged ahead of the M2 grammar layer.

## Spec Version Pin

Pin to:

- SysML 2.0 formal, September 2025.
- KerML 1.0 formal, September 2025.
- Systems Modeling API and Services 1.0 formal only for identity/API alignment notes, not implementation in this kickoff.
- OMG `20250201` machine-readable artifacts for SysML and KerML abstract syntax and library KPARs.
- Systems Modeling Community release tag `2026-03` as the current convenience bundle for formal documents, BNF extraction files, and reference libraries.

The checked-in MOF XMI abstract-syntax inputs for M1a are under `docs/sysml-v2/omg/20250201/`:

- `KerML.xmi` from `https://www.omg.org/spec/KerML/20250201/KerML.xmi` (`ptc/25-04-04`).
- `SysML.xmi` from `https://www.omg.org/spec/SysML/20250201/SysML.xmi` (`ptc/25-02-15`).

Update policy: changing the pin requires a mapping decision update, support-matrix review, and focused regression fixtures for affected grammar, metamodel, library, and round-trip behavior.

## Test Environment

Decision: the canonical, reproducible test environment is a committed Docker image (`docker/Dockerfile`) based on Ubuntu 25.10, running `poetry run pytest` against `poetry.lock`. Both CI and local development run this image, so "verified" means the same thing everywhere. `poetry.lock` is the source of truth for Python dependencies; the image is the source of truth for the system runtime.

Rationale and rejected alternatives:

- Gaphor's UI import chain (`gaphor/conftest.py` -> `gaphor.ui`) requires libadwaita >= 1.8 and GtkSource 5. The development host is Ubuntu 24.04 LTS, capped at libadwaita 1.5.0, so the host Poetry venv cannot collect tests.
- Of the bases checked on 2026-06-16, only Ubuntu 25.10 cleared the floor (libadwaita 1.8.0, GTK 4.20, PyGObject 3.50, GtkSource 5.16). Fedora 41 (1.6.10) and Fedora 42 (1.7.12) were too old.
- Rejected: pip-installing pytest into the installed Flatpak Gaphor runtime. It worked as a one-off smoke check but is not a valid foundation: the test deps would live in unpinned, mutable `~/.var/app` user-site state outside `poetry.lock`, resolved against a different Python (3.13) than the lockfile, and a Flatpak update can discard it. It splits the dependency source of truth and is not reproducible across machines or CI.
- Rejected (as a requirement): upgrading the host OS to Ubuntu 26.04. It would fix the Poetry path natively but is not reproducible across a team and is not needed once the image exists.

The image also supports interactive GUI launch (`docker/run-gui.sh`, X11 socket passthrough) as a convenience, but GUI interaction is not the foundation: correctness is proven headless via `docker/run-tests.sh` (xvfb), exactly as Gaphor's own CI runs GUI-dependent tests. This is consistent with the invariant that diagrams/GUI come last.

Verified 2026-06-16: the image builds, the full suite collects (2430 tests), the four M0 SysML2 CLI tests pass, and a core ElementFactory slice passes.

## Element Identity

Repository identity uses Gaphor's native `Base.id` and `ElementFactory` ownership of elements.

Do not introduce a parallel repository id. Add a SysML/API-facing `elementId` only when API or export compatibility requires it. Round-trip equivalence never depends on either Gaphor ids or imported textual ids.

Keep these identities distinct:

- Gaphor internal `Base.id`.
- SysML/API-facing `elementId`, if introduced later.
- Text import ids minted during import.
- Canonical round-trip identity, based on structure and resolved references.

## Round-Trip Equivalence

Round-trip equivalence is canonical structural comparison over:

- element types,
- ownership tree,
- memberships,
- typing and specialization relations,
- references resolved to their target by canonical path,
- documentation,
- qualified names.

It explicitly excludes text formatting and Gaphor element id equality.

## Name Resolution Target Design

Full target:

- unqualified lookup through owner namespaces,
- simple and nested qualified-name lookup,
- imports,
- inherited members,
- visibility,
- aliases,
- nested namespaces,
- implicit specialization,
- feature chains,
- diagnostics for ambiguous and unresolved names.

M2 scope only:

- same-namespace lookup,
- simple qualified-name lookup,
- unresolved-symbol diagnostic.

Do not implement inheritance, visibility, aliases, or feature chains during the first tracer.
