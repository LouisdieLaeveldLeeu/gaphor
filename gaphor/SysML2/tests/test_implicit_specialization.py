"""Implicit specialization -- the universal root (Phase 5d).

Per KerML, every definition (Classifier) with no explicit `:>` implicitly
specializes the root `Anything`, and every usage (Feature) with no explicit
feature-specialization (`:>` / `:>>`) implicitly subsets the root `things`. The two
bases are read-only proxies (like the standard-library value-type proxies): real,
persisted elements that participate in the specialization structure but are skipped
in name resolution and never written on export or counted in the round-trip
fingerprint. A declared-but-unresolved specialization still suppresses the implicit
base (the user expressed intent).
"""

from __future__ import annotations

from gaphor.core.modeling import ElementFactory
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.export import export_namespace
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
        result.unresolved_supertypes,
        result.unresolved_subsettings,
        result.unresolved_redefinitions,
        result.self_redefinitions,
    )


def _def(factory, name):
    return next(
        d for d in factory.select(sysml2.PartDefinition) if d.declaredName == name
    )


def _part(factory, name):
    return next(
        u for u in factory.select(sysml2.PartUsage) if u.declaredName == name
    )


# --- the implicit bases ------------------------------------------------------


def test_definition_implicitly_specializes_anything():
    factory, result = _map("part def P;")
    p = _def(factory, "P")
    supers = list(kk.supertypes(p))
    assert len(supers) == 1
    base = supers[0]
    assert kk.is_implicit_base(base)
    assert type(base) is kerml.Classifier and base.declaredName == "Anything"
    assert not list(kk.explicit_supertypes(p))  # implicit, not user-written
    assert not has_errors(_validate(factory, result))


def test_usage_implicitly_subsets_things():
    factory, result = _map("part p;")
    p = _part(factory, "p")
    subs = list(kk.subsettings(p))
    assert len(subs) == 1
    base = kk._single(subs[0].subsettedFeature)
    assert kk.is_implicit_base(base)
    assert type(base) is kerml.Feature and base.declaredName == "things"
    assert not list(kk.explicit_subsettings(p))
    assert not has_errors(_validate(factory, result))


def test_typed_usage_still_subsets_things():
    # Typing does not root a feature (typing is feature->type), so even a typed usage
    # gets the implicit `things` subsetting.
    factory, _ = _map("part def Engine;\npart e : Engine;")
    base = kk._single(next(iter(kk.subsettings(_part(factory, "e")))).subsettedFeature)
    assert kk.is_implicit_base(base)


def test_implicit_anything_is_shared_and_not_duplicate():
    factory, result = _map("part def A;\npart def B;\npart x;\npart y;")
    supers = {s.id for n in ("A", "B") for s in kk.supertypes(_def(factory, n))}
    assert len(supers) == 1  # one shared Anything proxy for all definitions
    things = {
        kk._single(next(iter(kk.subsettings(_part(factory, n)))).subsettedFeature).id
        for n in ("x", "y")
    }
    assert len(things) == 1  # one shared things proxy for all usages
    # The proxies do not collide with each other or anything else.
    assert not any(d.rule == "duplicate-name" for d in _validate(factory, result))


# --- suppression by explicit specialization ----------------------------------


def test_explicit_supertype_suppresses_implicit_anything():
    factory, _ = _map("part def Vehicle;\npart def Car :> Vehicle;")
    assert [kk.effective_name(s) for s in kk.supertypes(_def(factory, "Car"))] == [
        "Vehicle"
    ]


def test_explicit_subsetting_suppresses_implicit_things():
    factory, _ = _map("part def C { part wheel; part spare :> wheel; }")
    spare = _part(factory, "spare")
    assert [
        kk.effective_name(kk._single(s.subsettedFeature))
        for s in kk.subsettings(spare)
    ] == ["wheel"]


def test_redefinition_suppresses_implicit_things():
    factory, _ = _map("part def V { part base; }\npart def C :> V { part r :>> base; }")
    r = _part(factory, "r")
    assert list(kk.redefinitions(r))  # rooted by the redefinition
    assert not list(kk.subsettings(r))  # so NOT given an implicit things-subsetting


def test_unresolved_explicit_suppresses_implicit():
    # A declared-but-broken `:> Missing` expresses intent, so no implicit Anything
    # masks it -- the unresolved-specialization error stands alone.
    factory, result = _map("part def Bad :> Missing;")
    assert not list(kk.supertypes(_def(factory, "Bad")))
    diagnostics = _validate(factory, result)
    assert any(d.rule == "unresolved-specialization" for d in diagnostics)


# --- the bases are not user symbols ------------------------------------------


def test_implicit_base_is_not_user_resolvable():
    # `Anything` is an internal proxy, never a resolvable user symbol.
    factory, result = _map("part def D;\npart x : Anything;")
    assert _part(factory, "x").id in result.unresolved_types
    assert any(
        d.rule == "usage-without-valid-type" for d in _validate(factory, result)
    )


# --- invisible to export / round-trip ----------------------------------------


def test_implicit_base_is_not_exported():
    _factory, result = _map("part def P;\npart p;\npart def C :> P;")
    text = export_namespace(result.root)
    assert "Anything" not in text
    assert "things" not in text
    assert "part def P;" in text
    assert "part p;" in text
    assert "part def C :> P;" in text


def test_implicit_base_round_trips():
    result = round_trip(
        "package Root {\n"
        "  part def P;\n"
        "  part p;\n"
        "  part def C :> P { part q; }\n"
        "}"
    )
    assert result.preserved
    assert result.valid


# --- persistence -------------------------------------------------------------


def test_implicit_base_survives_save_reload(element_factory, saver, loader):
    map_package(parse("part def P;\npart p;"), element_factory)

    loader(saver())

    p = next(
        d for d in element_factory.select(sysml2.PartDefinition) if d.declaredName == "P"
    )
    supers = list(kk.supertypes(p))
    assert len(supers) == 1 and kk.is_implicit_base(supers[0])
    usage = next(
        u for u in element_factory.select(sysml2.PartUsage) if u.declaredName == "p"
    )
    base = kk._single(next(iter(kk.subsettings(usage))).subsettedFeature)
    assert kk.is_implicit_base(base)
