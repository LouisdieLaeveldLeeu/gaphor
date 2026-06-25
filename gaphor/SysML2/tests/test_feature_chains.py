"""Feature-chain connector endpoints (`connect a.b to c.d`, Phase 5e).

A connector endpoint may be a FEATURE CHAIN `a.b.c`: the head resolves nearest-first
and each `.step` resolves as a member of the previous feature's TYPE (own, else its
sole inherited member). A resolved chain is a synthesized anonymous Feature owning an
ordered FeatureChaining per step (the faithful KerML representation), set as the
connector's source/target. The chain feature is invisible as a user member (no
implicit base, not exported as a member) and renders as the dotted path. Covers
connection, flow, and succession ends; parse, map, multi-step + inherited steps,
broken chains, export, round-trip, and persistence.
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

# A two-level model: `a : A`, A has `b : B`, B has `c`; plus a plain `x`.
_MODEL = (
    "part def B { part c; }\n"
    "part def A { part b : B; }\n"
    "part a : A;\n"
    "part x;\n"
)


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


def _connector(factory, cls, name):
    return next(c for c in factory.select(cls) if c.declaredName == name)


def _chain_names(end):
    return [kk.effective_name(s) for s in kk.chaining_features(end)]


# --- parse -------------------------------------------------------------------


def test_parse_feature_chain_endpoint():
    pkg = parse("connection c connect a.b.c to x;")
    conn = pkg.members[0]
    assert conn.source == ast.FeatureChain(head=("a",), rest=("b", "c"))
    assert conn.target == ("x",)  # plain endpoint stays a tuple


def test_parse_qualified_head_chain():
    pkg = parse("connection c connect P::a.b to x;")
    assert pkg.members[0].source == ast.FeatureChain(head=("P", "a"), rest=("b",))


# --- map / resolution --------------------------------------------------------


def test_connection_chain_resolves_through_feature_types():
    factory, result = _map(_MODEL + "connection conn connect a.b.c to x;")
    assert not has_errors(_validate(factory, result))
    conn = _connector(factory, sysml2.ConnectionUsage, "conn")
    source = kk._single(conn.source)
    assert kk.is_feature_chain(source)
    # The chain steps are the actual a, b, c features (b in A, c in B).
    a, b, c = list(kk.chaining_features(source))
    assert _chain_names(source) == ["a", "b", "c"]
    assert kk.owning_namespace(b).declaredName == "A"
    assert kk.owning_namespace(c).declaredName == "B"
    assert kk._single(conn.target).declaredName == "x"


def test_flow_and_succession_chain_ends():
    factory, result = _map(
        _MODEL + "flow fl from a.b to x;\nsuccession su first x then a.b;"
    )
    assert not has_errors(_validate(factory, result))
    flow_source = kk._single(_connector(factory, sysml2.FlowUsage, "fl").source)
    succ_target = kk._single(
        _connector(factory, sysml2.SuccessionAsUsage, "su").target
    )
    assert _chain_names(flow_source) == ["a", "b"]
    assert _chain_names(succ_target) == ["a", "b"]


def test_chain_step_can_be_inherited():
    # `b` is inherited into A from a supertype; the chain step still resolves.
    factory, result = _map(
        "part def Base { part b : B; }\npart def B { part c; }\n"
        "part def A :> Base;\npart a : A;\npart x;\n"
        "connection conn connect a.b.c to x;"
    )
    assert not has_errors(_validate(factory, result))
    source = kk._single(_connector(factory, sysml2.ConnectionUsage, "conn").source)
    assert _chain_names(source) == ["a", "b", "c"]


# --- the chain feature is invisible as a user member -------------------------


def test_chain_feature_gets_no_implicit_base():
    factory, _ = _map(_MODEL + "connection conn connect a.b.c to x;")
    source = kk._single(_connector(factory, sysml2.ConnectionUsage, "conn").source)
    # A synthesized chain feature is not a user usage: no implicit `things`.
    assert not list(kk.subsettings(source))


# --- diagnostics -------------------------------------------------------------


def test_broken_chain_step_is_reported():
    # `a.b.missing` -- `missing` is not a member of B (b's type).
    factory, result = _map(_MODEL + "connection conn connect a.b.missing to x;")
    assert _connector(factory, sysml2.ConnectionUsage, "conn").id in result.unresolved_ends
    assert any(d.rule == "broken-connection-end" for d in _validate(factory, result))


def test_chain_through_untyped_feature_is_reported():
    # `x.b` -- x is untyped, so there is no type to navigate into.
    factory, result = _map(_MODEL + "connection conn connect x.b to a;")
    assert any(d.rule == "broken-connection-end" for d in _validate(factory, result))


def test_broken_chain_leaves_no_orphan_chain_feature():
    # A half-broken connection (one chain end broken) leaves NEITHER end set and no
    # synthesized chain feature -- ends stay atomic.
    factory, _ = _map(_MODEL + "connection conn connect a.b.missing to x;")
    conn = _connector(factory, sysml2.ConnectionUsage, "conn")
    assert kk._single(conn.source) is None and kk._single(conn.target) is None
    assert not list(factory.select(kerml.FeatureChaining))


def test_broken_persisted_feature_chaining_is_reported():
    factory = ElementFactory()
    chain = factory.create(kerml.Feature)
    chaining = factory.create(kerml.FeatureChaining)
    chain.ownedRelationship = chaining
    chaining.owningRelatedElement = chain
    # No chainingFeature -> broken (model-derived).
    assert any(d.rule == "broken-feature-chain" for d in validate(factory))


# --- export / round-trip -----------------------------------------------------


def test_export_emits_dotted_chain():
    _factory, result = _map(
        _MODEL + "connection conn connect a.b.c to x;\nflow fl from a.b to x;"
    )
    text = export_namespace(result.root)
    assert "connect a.b.c to x;" in text
    assert "from a.b to x;" in text
    assert "things" not in text  # chain feature never leaks as a member/base


def test_feature_chain_round_trips():
    result = round_trip(
        "package P {\n" + _MODEL + "  connection conn connect a.b.c to x;\n"
        "  flow fl from a.b to x;\n"
        "  succession su first x then a.b;\n"
        "}"
    )
    assert result.preserved
    assert result.valid


def test_chain_endpoint_changes_the_fingerprint():
    base = "package P {\n" + _MODEL + "  connection conn connect %s to x;\n}"
    assert round_trip(base % "a.b.c").source_form != round_trip(
        base % "a.b"
    ).source_form


# --- persistence -------------------------------------------------------------


def test_feature_chain_survives_save_reload(element_factory, saver, loader):
    map_package(parse(_MODEL + "connection conn connect a.b.c to x;"), element_factory)

    loader(saver())

    conn = next(
        c
        for c in element_factory.select(sysml2.ConnectionUsage)
        if c.declaredName == "conn"
    )
    source = kk._single(conn.source)
    assert kk.is_feature_chain(source)
    assert [kk.effective_name(s) for s in kk.chaining_features(source)] == [
        "a",
        "b",
        "c",
    ]
