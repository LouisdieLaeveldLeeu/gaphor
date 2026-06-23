"""Imports, imported memberships, visibility & ambiguity (Phase 5a).

A namespace may `import A::B;` (a named element) or `import A::*;` (the public
members of a namespace), each optionally `public`/`private`; members carry a
`public`/`private` visibility prefix (default public). Name resolution is
nearest-first: an OWN member wins, otherwise the namespace's imports are consulted
(a wildcard brings only PUBLIC members; a named import brings the element). A name
visible from MORE THAN ONE import is reported `ambiguous-name`. Covers parse, map,
resolution through imports, visibility honoring, ambiguity, export, round-trip, and
persistence.
"""

from __future__ import annotations

from gaphor.core.modeling import ElementFactory
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.export import export_namespace
from gaphor.SysML2.grammar import ast
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.roundtrip import round_trip
from gaphor.SysML2.validation import has_errors, validate


def _map(text: str):
    factory = ElementFactory()
    return factory, map_package(parse(text), factory)


def _validate(factory, result):
    return validate(
        factory,
        result.unresolved_types,
        result.mistyped,
        result.unresolved_ends,
        result.unresolved_frame_refs,
        result.ambiguous,
    )


def _part(factory, name):
    return next(
        u for u in factory.select(sysml2.PartUsage) if u.declaredName == name
    )


# --- parse -------------------------------------------------------------------


def test_parse_imports_and_visibility():
    pkg = parse(
        "import A::B;\npublic import C::*;\nprivate part def P;\npublic attribute x;"
    )
    named, wild, p, x = pkg.members
    assert named == ast.Import(target=("A", "B"), wildcard=False)
    assert wild == ast.Import(target=("C",), wildcard=True, visibility="public")
    assert p.visibility == "private"
    assert x.visibility == "public"


# --- map ---------------------------------------------------------------------


def test_import_mapped_to_kerml_import():
    factory, _ = _map(
        "package Lib { part def Engine; }\n"
        "package App { import Lib::Engine; public import Lib::*; }"
    )
    imports = list(factory.select(kerml.Import))
    assert len(imports) == 2
    named = next(i for i in imports if not i.isImportAll)
    wild = next(i for i in imports if i.isImportAll)
    assert kk._single(named.target).declaredName == "Engine"
    assert wild.visibility == kerml.VisibilityKind.public
    assert named.visibility == kerml.VisibilityKind.private  # KerML import default


def test_member_visibility_default_public_and_explicit_private():
    factory, _ = _map("part def Pub;\nprivate part def Priv;")
    by_name = {
        kk._single(m.memberElement).declaredName: m
        for m in kk.owned_memberships(
            next(iter(factory.select(kerml.Namespace)))
        )
        if kk._single(m.memberElement) is not None
    }
    # the model root may include only these two; default public, explicit private
    assert by_name["Pub"].visibility == kerml.VisibilityKind.public
    assert by_name["Priv"].visibility == kerml.VisibilityKind.private


# --- resolution through imports ----------------------------------------------


def test_named_import_resolves_type():
    factory, result = _map(
        "package Lib { part def Engine; }\n"
        "package App { import Lib::Engine; part e : Engine; }"
    )
    assert not has_errors(_validate(factory, result))
    assert kk.feature_type(_part(factory, "e")).declaredName == "Engine"


def test_wildcard_import_resolves_type():
    factory, result = _map(
        "package Lib { part def Engine; }\n"
        "package App { import Lib::*; part e : Engine; }"
    )
    assert not has_errors(_validate(factory, result))
    assert kk.feature_type(_part(factory, "e")).declaredName == "Engine"


def test_private_member_not_imported_by_wildcard():
    factory, result = _map(
        "package Lib { private part def Secret; }\n"
        "package App { import Lib::*; part s : Secret; }"
    )
    # Secret is private -> NOT brought in by the wildcard -> unresolved.
    assert _part(factory, "s").id in result.unresolved_types
    assert any(d.rule == "usage-without-valid-type" for d in _validate(factory, result))


def test_own_member_shadows_import():
    factory, result = _map(
        "package Lib { part def Engine; }\n"
        "package App { import Lib::Engine; part def Engine; part e : Engine; }"
    )
    # App's OWN Engine wins over the imported one.
    own_engine = next(
        d
        for d in factory.select(sysml2.PartDefinition)
        if d.declaredName == "Engine" and "App" in kk.qualified_name(d)
    )
    assert kk.feature_type(_part(factory, "e")) is own_engine


def test_unresolved_import_is_reported():
    factory, result = _map("package App { import Missing::Thing; }")
    imp = next(iter(factory.select(kerml.Import)))
    assert kk._single(imp.target) is None
    assert any(d.rule == "unresolved-import" for d in _validate(factory, result))


# --- ambiguity ---------------------------------------------------------------


def test_ambiguous_name_from_two_imports_is_reported():
    factory, result = _map(
        "package A { part def Thing; }\n"
        "package B { part def Thing; }\n"
        "package C { import A::*; import B::*; part t : Thing; }"
    )
    assert _part(factory, "t").id in result.ambiguous
    diagnostics = _validate(factory, result)
    assert any(d.rule == "ambiguous-name" for d in diagnostics)
    # ambiguous -> did NOT bind a type
    assert kk.feature_type(_part(factory, "t")) is None


def test_same_element_two_imports_is_not_ambiguous():
    # Importing the SAME element by wildcard AND by name is one candidate, not an
    # ambiguity.
    factory, result = _map(
        "package A { part def Thing; }\n"
        "package C { import A::*; import A::Thing; part t : Thing; }"
    )
    assert not result.ambiguous
    assert kk.feature_type(_part(factory, "t")).declaredName == "Thing"


# --- export / round-trip -----------------------------------------------------


def test_export_emits_imports_and_visibility():
    _factory, result = _map(
        "package Lib { part def Engine; private part def Secret; }\n"
        "public import Lib::*;\npackage App { import Lib::Engine; part e : Engine; }"
    )
    text = export_namespace(result.root)
    assert "public import Lib::*;" in text
    assert "import Lib::Engine;" in text
    assert "private part def Secret;" in text


def test_imports_and_visibility_round_trip():
    result = round_trip(
        "package Lib { part def Engine; private part def Secret; }\n"
        "package App {\n"
        "  public import Lib::*;\n"
        "  import Lib::Engine;\n"
        "  private part hidden : Engine;\n"
        "  part e : Engine;\n"
        "}"
    )
    assert result.preserved
    assert result.valid


def test_visibility_changes_the_fingerprint():
    assert round_trip("part def P;").source_form != round_trip(
        "private part def P;"
    ).source_form


def test_import_changes_the_fingerprint():
    assert round_trip("package A { part def T; }").source_form != round_trip(
        "package A { part def T; }\npackage B { import A::*; }"
    ).source_form


# --- persistence -------------------------------------------------------------


def test_imports_and_visibility_survive_save_reload(element_factory, saver, loader):
    map_package(
        parse(
            "package Lib { part def Engine; }\n"
            "package App { public import Lib::*; private part def Hidden; }"
        ),
        element_factory,
    )

    loader(saver())

    imp = next(iter(element_factory.select(kerml.Import)))
    assert imp.isImportAll and imp.visibility == kerml.VisibilityKind.public
    assert kk._single(imp.target).declaredName == "Lib"
    hidden_ms = next(
        m
        for m in element_factory.select(kerml.OwningMembership)
        if (e := kk._single(m.memberElement)) is not None
        and e.declaredName == "Hidden"
    )
    assert hidden_ms.visibility == kerml.VisibilityKind.private
