"""AttributeUsage promotion: typing by standard-library value types (Phase 4).

`attribute x : Real;` resolves `Real` against the pinned ScalarValues library and
types the attribute via a read-only DataType proxy materialized in the user
model. The proxy is a real Type for FeatureTyping/validation/persistence but is
invisible to textual export and the round-trip canonical form, so the library
declaration is never dumped.
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
    result = map_package(parse(text), factory)
    return factory, result


def test_attribute_typed_by_library_real_resolves():
    factory, result = _map("attribute x : Real;")
    assert not result.unresolved_types
    assert not result.mistyped
    usage = next(iter(factory.select(sysml2.AttributeUsage)))
    typed = kk.feature_type(usage)
    assert isinstance(typed, kerml.DataType)
    assert typed.declaredName == "Real"


def test_qualified_library_name_resolves():
    factory, result = _map("attribute x : ScalarValues::Real;")
    assert not result.unresolved_types
    usage = next(iter(factory.select(sysml2.AttributeUsage)))
    assert kk.feature_type(usage).declaredName == "Real"


def test_string_boolean_integer_natural_resolve():
    for name in ("String", "Boolean", "Integer", "Natural"):
        factory, result = _map(f"attribute v : {name};")
        assert not result.unresolved_types, name
        usage = next(iter(factory.select(sysml2.AttributeUsage)))
        assert kk.feature_type(usage).declaredName == name


def test_library_typed_attribute_validates():
    factory, result = _map("attribute x : Real;")
    diagnostics = validate(factory, result.unresolved_types, result.mistyped)
    assert not has_errors(diagnostics)


def test_library_typed_attribute_exports_simple_name():
    factory, result = _map("attribute x : Real;")
    text = export_namespace(result.root)
    assert "attribute x : Real;" in text
    # The library declaration is never dumped.
    assert "datatype" not in text
    assert "attribute def Real" not in text


def test_proxy_is_not_exported_as_a_member():
    factory, result = _map("attribute x : Real;\nattribute y : String;")
    text = export_namespace(result.root)
    # Only the two user attributes, no proxy declaration lines.
    assert text.count("attribute ") == 2
    assert "Real;" in text and "String;" in text


def test_library_typed_attribute_round_trips():
    result = round_trip("attribute x : Real;")
    assert result.preserved
    assert result.valid


def test_library_typed_attribute_in_package_round_trips():
    result = round_trip("package P { attribute speed : Real; }")
    assert result.preserved
    assert result.valid


def test_one_proxy_reused_for_repeated_type():
    factory, _ = _map("attribute a : Real;\nattribute b : Real;")
    proxies = [e for e in factory.select(kerml.DataType) if type(e) is kerml.DataType]
    assert len(proxies) == 1  # a single shared "Real" proxy


def test_unknown_attribute_type_is_still_unresolved():
    factory, result = _map("attribute x : Nonexistent;")
    assert result.unresolved_types


def test_part_typed_by_value_type_name_is_not_library_resolved():
    # Only attribute usages get library value typing; a part declaring a value
    # type name stays unresolved (Real is not a PartDefinition).
    factory, result = _map("part p : Real;")
    assert result.unresolved_types


def test_attribute_typed_by_attribute_definition_still_works():
    factory, result = _map("attribute def Speed;\nattribute s : Speed;")
    assert not result.unresolved_types and not result.mistyped
    usage = next(iter(factory.select(sysml2.AttributeUsage)))
    assert kk.feature_type(usage).declaredName == "Speed"


def test_attribute_typed_by_part_definition_is_mistyped():
    factory, result = _map("part def Engine;\nattribute a : Engine;")
    assert result.mistyped  # Engine is a Structure, not a DataType


def test_library_value_type_names_lists_concrete_types():
    from gaphor.SysML2.mapping import library_value_type_names

    names = set(library_value_type_names())
    assert {"Boolean", "String", "Integer", "Real", "Natural"} <= names
    # Abstract library bases are not offered as concrete value types.
    assert "ScalarValue" not in names
    assert "Number" not in names


def test_set_attribute_library_type_api():
    from gaphor.SysML2.mapping import set_attribute_library_type

    factory = ElementFactory()
    root = factory.create(kerml.Namespace)
    usage = factory.create(sysml2.AttributeUsage)
    usage.declaredName = "x"
    kk.add_owned_member(root, usage, factory.create(kerml.OwningMembership))

    set_attribute_library_type(usage, "Real")

    typed = kk.feature_type(usage)
    assert type(typed) is kerml.DataType
    assert typed.declaredName == "Real"
    assert kk.owning_namespace(typed) is root
