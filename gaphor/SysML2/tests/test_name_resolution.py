"""Deeper name resolution: nearest-first enclosing-namespace lookup (Phase 5).

The resolver now looks a (qualified) type name up by walking outward from the
usage's own namespace through each enclosing namespace to the model root, nearest
declaration first. This resolves names in enclosing packages and
relative-qualified names, beyond the old same-namespace / root-qualified scope.
Imports, aliases, inherited members, visibility, implicit specialization, and
feature chains remain follow-up phases (they need grammar/semantic support).
"""

from __future__ import annotations

from gaphor.core.modeling import ElementFactory
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2 import sysml2
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.roundtrip import round_trip


def _map(text: str):
    factory = ElementFactory()
    return factory, map_package(parse(text), factory)


def _part_usage(factory, name: str) -> sysml2.PartUsage:
    return next(u for u in factory.select(sysml2.PartUsage) if u.declaredName == name)


def test_simple_name_resolves_in_enclosing_namespace():
    # `Engine` referenced in nested package B resolves to the enclosing A::Engine.
    factory, result = _map(
        "package A { part def Engine; package B { part e : Engine; } }"
    )
    assert not result.unresolved_types
    typed = kk.feature_type(_part_usage(factory, "e"))
    assert isinstance(typed, sysml2.PartDefinition)
    assert kk.qualified_name(typed).endswith("A::Engine")


def test_relative_qualified_name_resolves_via_enclosing_scope():
    # `A::Engine` referenced from within the enclosing package (A is a sibling),
    # not from the root, now resolves.
    factory, result = _map(
        "package Outer { package A { part def Engine; } part x : A::Engine; }"
    )
    assert not result.unresolved_types
    typed = kk.feature_type(_part_usage(factory, "x"))
    assert kk.qualified_name(typed).endswith("Outer::A::Engine")


def test_nearest_first_shadowing():
    # An inner Engine shadows an outer Engine of the same name.
    factory, result = _map(
        "package A { part def Engine; "
        "package B { part def Engine; part e : Engine; } }"
    )
    assert not result.unresolved_types
    typed = kk.feature_type(_part_usage(factory, "e"))
    assert kk.qualified_name(typed).endswith("A::B::Engine")  # inner, not A::Engine


def test_deep_nesting_resolves_outermost_declaration():
    factory, result = _map(
        "package A { part def Engine; "
        "package B { package C { part e : Engine; } } }"
    )
    assert not result.unresolved_types
    typed = kk.feature_type(_part_usage(factory, "e"))
    assert kk.qualified_name(typed).endswith("A::Engine")


def test_root_qualified_name_still_resolves():
    factory, result = _map(
        "package A { part def Engine; } package B { part e : A::Engine; }"
    )
    assert not result.unresolved_types
    typed = kk.feature_type(_part_usage(factory, "e"))
    assert kk.qualified_name(typed).endswith("A::Engine")


def test_same_namespace_name_still_resolves():
    factory, result = _map("part def Engine;\npart e : Engine;")
    assert not result.unresolved_types
    assert kk.feature_type(_part_usage(factory, "e")).declaredName == "Engine"


def test_unknown_name_is_unresolved():
    factory, result = _map("package B { part e : Missing; }")
    assert result.unresolved_types


def test_enclosing_resolution_round_trips():
    result = round_trip(
        "package A { part def Engine; package B { part e : Engine; } }"
    )
    assert result.preserved
    assert result.valid
