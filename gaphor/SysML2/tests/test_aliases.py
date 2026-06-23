"""Alias declarations and resolution (Phase 5b).

`alias <Name> for <QName>;` gives an existing element an additional name in a
namespace: a NON-owning `Membership` (memberName=<Name>, memberElement=<QName>),
not an owned member. A name bound by an alias resolves wherever the alias is in
scope -- so a usage typed by the alias name, an alias to another alias, and a
wildcard import that re-exports an alias all resolve to the aliased element.
Aliases carry the shared `public`/`private` visibility prefix (default public).
Covers parse, map, resolution through aliases, ambiguity, duplicate-name,
unresolved aliases, export, round-trip, and persistence.
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


def _alias(factory, name):
    return next(m for m in factory.select(kerml.Membership) if kk.is_alias(m) and m.memberName == name)


# --- parse -------------------------------------------------------------------


def test_parse_alias_and_visibility():
    pkg = parse("alias E for Lib::Engine;\nprivate alias H for Lib::Hidden;")
    public_alias, private_alias = pkg.members
    assert public_alias == ast.Alias(name="E", target=("Lib", "Engine"))
    assert private_alias == ast.Alias(
        name="H", target=("Lib", "Hidden"), visibility="private"
    )


# --- map ---------------------------------------------------------------------


def test_alias_mapped_to_non_owning_membership():
    factory, _ = _map(
        "package Lib { part def Engine; }\n"
        "package App { alias E for Lib::Engine; }"
    )
    alias = _alias(factory, "E")
    # An alias is a PLAIN Membership (non-owning), not an OwningMembership.
    assert type(alias) is kerml.Membership
    assert not isinstance(alias, kerml.OwningMembership)
    target = kk._single(alias.memberElement)
    assert target.declaredName == "Engine"
    # It does NOT own the target (the target stays owned by Lib, not App).
    assert kk.owning_namespace(target).declaredName == "Lib"


def test_alias_default_public_and_explicit_private():
    factory, _ = _map(
        "part def Engine;\nalias E for Engine;\nprivate alias H for Engine;"
    )
    assert _alias(factory, "E").visibility == kerml.VisibilityKind.public
    assert _alias(factory, "H").visibility == kerml.VisibilityKind.private


# --- resolution through aliases ----------------------------------------------


def test_alias_resolves_type():
    factory, result = _map(
        "package Lib { part def Engine; }\n"
        "package App { alias E for Lib::Engine; part e : E; }"
    )
    assert not has_errors(_validate(factory, result))
    assert kk.feature_type(_part(factory, "e")).declaredName == "Engine"


def test_alias_to_alias_chain_resolves():
    # A targets B, B targets the real type; A is declared BEFORE B, so the
    # fixpoint resolution must settle the chain regardless of order.
    factory, result = _map(
        "part def Engine;\nalias A for B;\nalias B for Engine;\npart e : A;"
    )
    assert not has_errors(_validate(factory, result))
    assert kk.feature_type(_part(factory, "e")).declaredName == "Engine"


def test_wildcard_import_reexports_alias():
    # Lib's alias is a public membership, so `import Lib::*` brings it in under
    # the alias name and a usage in App resolves through it.
    factory, result = _map(
        "package Lib { part def Engine; alias E for Engine; }\n"
        "package App { import Lib::*; part e : E; }"
    )
    assert not has_errors(_validate(factory, result))
    assert kk.feature_type(_part(factory, "e")).declaredName == "Engine"


def test_alias_target_can_be_imported():
    # The alias target resolves with imports in scope: App imports Engine, then
    # aliases it; the alias resolves to the imported element.
    factory, result = _map(
        "package Lib { part def Engine; }\n"
        "package App { import Lib::*; alias E for Engine; part e : E; }"
    )
    assert not has_errors(_validate(factory, result))
    assert kk.feature_type(_part(factory, "e")).declaredName == "Engine"


# --- diagnostics -------------------------------------------------------------


def test_unresolved_alias_is_reported():
    factory, result = _map("package App { alias E for Missing::Thing; }")
    alias = _alias(factory, "E")
    assert kk._single(alias.memberElement) is None
    assert any(d.rule == "unresolved-alias" for d in _validate(factory, result))


def test_ambiguous_alias_target_is_reported():
    # An alias target visible from two imports is `ambiguous-name`, the alias does
    # NOT bind, and it is NOT also double-reported as unresolved.
    factory, result = _map(
        "package A { part def Thing; }\n"
        "package B { part def Thing; }\n"
        "package C { import A::*; import B::*; alias T for Thing; }"
    )
    diagnostics = _validate(factory, result)
    assert any(d.rule == "ambiguous-name" for d in diagnostics)
    assert not any(d.rule == "unresolved-alias" for d in diagnostics)
    assert kk._single(_alias(factory, "T").memberElement) is None


def test_alias_name_colliding_with_member_is_duplicate():
    factory, result = _map("part def Y;\npart def X;\nalias X for Y;")
    assert any(d.rule == "duplicate-name" for d in _validate(factory, result))


# --- export / round-trip -----------------------------------------------------


def test_export_emits_alias():
    _factory, result = _map(
        "package Lib { part def Engine; part def Hidden; }\n"
        "package App { alias E for Lib::Engine; private alias H for Lib::Hidden; }"
    )
    text = export_namespace(result.root)
    assert "alias E for Lib::Engine;" in text
    assert "private alias H for Lib::Hidden;" in text


def test_alias_round_trips():
    result = round_trip(
        "package Lib { part def Engine; }\n"
        "package App {\n"
        "  alias E for Lib::Engine;\n"
        "  part e : E;\n"
        "}"
    )
    assert result.preserved
    assert result.valid


def test_alias_changes_the_fingerprint():
    base = "package Lib { part def Engine; }\n"
    assert round_trip(base).source_form != round_trip(
        base + "package App { alias E for Lib::Engine; }"
    ).source_form


def test_alias_visibility_changes_the_fingerprint():
    base = "package Lib { part def Engine; }\npackage App { %s alias E for Lib::Engine; }"
    assert round_trip(base % "").source_form != round_trip(
        base % "private"
    ).source_form


# --- persistence -------------------------------------------------------------


def test_alias_survives_save_reload(element_factory, saver, loader):
    map_package(
        parse(
            "package Lib { part def Engine; }\n"
            "package App { private alias E for Lib::Engine; }"
        ),
        element_factory,
    )

    loader(saver())

    alias = next(
        m
        for m in element_factory.select(kerml.Membership)
        if kk.is_alias(m) and m.memberName == "E"
    )
    assert alias.visibility == kerml.VisibilityKind.private
    assert kk._single(alias.memberElement).declaredName == "Engine"
    # Resolution through the reloaded alias still finds the target.
    app = next(
        n
        for n in element_factory.select(kerml.Package)
        if n.declaredName == "App"
    )
    assert kk.owned_member_named(app, "E").declaredName == "Engine"
