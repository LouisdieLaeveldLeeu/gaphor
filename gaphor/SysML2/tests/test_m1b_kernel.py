"""M1b minimal KerML kernel: behaviour + persistence + delete-direction tests.

Coverage:

1. The five required M1b scenarios (kickoff plan): namespace membership, the
   type/feature relation, import resolution, delete-owner cascade, and rename
   updating the qualified name -- each through a `.gaphor` save/reload where
   persistence is relevant.
2. Delete-direction tests pinning the containment whitelist: the containment
   spine cascades; non-owning references (import target, specialization
   general/specific, membership member) do NOT.
3. A parametrized create -> save -> reload over every generated kernel class.

Only the stored Relationship spine is persisted; the derived surface (members,
owning namespace, qualified name, imported elements) is computed by
`kerml_kernel.py` and is verified to survive save/reload.
"""

from __future__ import annotations

import inspect

import pytest

from gaphor.core.modeling import ElementFactory
from gaphor.core.modeling.base import Base
from gaphor.SysML2 import kerml, kerml_kernel


def _all_kernel_classes() -> list[type[Base]]:
    return [
        obj
        for _name, obj in inspect.getmembers(kerml, inspect.isclass)
        if obj.__module__ == "gaphor.SysML2.kerml" and issubclass(obj, Base)
    ]


def _add_member(
    factory: ElementFactory, namespace: kerml.Namespace, member: kerml.Element
) -> kerml.OwningMembership:
    membership = factory.create(kerml.OwningMembership)
    return kerml_kernel.add_owned_member(namespace, member, membership)


# --- parametrized persistence over the whole closure -------------------------


@pytest.mark.parametrize("cls", _all_kernel_classes(), ids=lambda c: c.__name__)
def test_every_kernel_class_persists_and_reloads(cls, element_factory, saver, loader):
    element = element_factory.create(cls)
    element_id = element.id

    loader(saver())

    reloaded = element_factory.lookup(element_id)
    assert reloaded is not None
    assert isinstance(reloaded, cls)


def test_kernel_has_expected_class_count():
    # Following only STORED (non-derived) references, the kernel closure is 16
    # classes: the original 12-class minimal kernel, plus Classifier/Class/
    # Structure (supermodel roots the M2 SysML layer generalizes) and
    # FeatureTyping (the stored type/feature relation the tracer types with).
    assert len(_all_kernel_classes()) == 16


# --- required behaviour 1: namespace + membership round-trip -----------------


def test_namespace_membership_persists_and_reloads(element_factory, saver, loader):
    ns = element_factory.create(kerml.Namespace)
    ns.declaredName = "Pkg"
    member = element_factory.create(kerml.Element)
    member.declaredName = "Engine"
    _add_member(element_factory, ns, member)

    ns_id, member_id = ns.id, member.id

    loader(saver())

    rns = element_factory.lookup(ns_id)
    rmember = element_factory.lookup(member_id)
    assert rns is not None and rmember is not None
    assert rmember in list(kerml_kernel.members(rns))
    assert kerml_kernel.owned_member_named(rns, "Engine") is rmember


# --- required behaviour 2: type + feature relation round-trip ----------------


def test_type_feature_relation_persists_and_reloads(element_factory, saver, loader):
    # In the minimal kernel a Type owns its Feature through an OwningMembership
    # (the stored containment spine); FeatureMembership is reached only via
    # derived refs and is outside this closure.
    a_type = element_factory.create(kerml.Type)
    a_type.declaredName = "Engine"
    a_feature = element_factory.create(kerml.Feature)
    a_feature.declaredName = "power"
    _add_member(element_factory, a_type, a_feature)

    type_id, feature_id = a_type.id, a_feature.id

    loader(saver())

    rtype = element_factory.lookup(type_id)
    rfeature = element_factory.lookup(feature_id)
    assert rtype is not None and rfeature is not None
    assert rfeature in list(kerml_kernel.owned_elements(rtype))


# --- required behaviour 3: import resolution + round-trip --------------------


def test_import_resolves_qualified_name_and_round_trips(element_factory, saver, loader):
    root = element_factory.create(kerml.Namespace)
    root.declaredName = "Root"
    inner = element_factory.create(kerml.Namespace)
    inner.declaredName = "Inner"
    _add_member(element_factory, root, inner)
    leaf = element_factory.create(kerml.Element)
    leaf.declaredName = "Engine"
    _add_member(element_factory, inner, leaf)

    importer = element_factory.create(kerml.Namespace)
    importer.declaredName = "Client"
    imp = element_factory.create(kerml.Import)
    kerml_kernel.add_import(importer, leaf, imp)

    assert kerml_kernel.resolve_qualified_name(root, "Root::Inner::Engine") is leaf
    assert leaf in list(kerml_kernel.imported_elements(importer))

    root_id, leaf_id, importer_id = root.id, leaf.id, importer.id

    loader(saver())

    rroot = element_factory.lookup(root_id)
    rleaf = element_factory.lookup(leaf_id)
    rimporter = element_factory.lookup(importer_id)
    assert kerml_kernel.resolve_qualified_name(rroot, "Root::Inner::Engine") is rleaf
    assert rleaf in list(kerml_kernel.imported_elements(rimporter))


# --- required behaviour 4: delete owner cascades to owned member -------------


def test_delete_owner_cascades_to_owned_member(element_factory):
    ns = element_factory.create(kerml.Namespace)
    member = element_factory.create(kerml.Element)
    membership = _add_member(element_factory, ns, member)

    member_id, membership_id = member.id, membership.id

    # The containment spine (ownedRelationship / ownedRelatedElement) is
    # composite, so unlinking the namespace cascades to the membership and the
    # owned member.
    ns.unlink()

    assert element_factory.lookup(membership_id) is None
    assert element_factory.lookup(member_id) is None


# --- required behaviour 5: rename namespace updates qualified names ----------


def test_rename_namespace_updates_qualified_name(element_factory):
    ns = element_factory.create(kerml.Namespace)
    ns.declaredName = "Pkg"
    member = element_factory.create(kerml.Element)
    member.declaredName = "Engine"
    _add_member(element_factory, ns, member)

    assert kerml_kernel.qualified_name(member) == "Pkg::Engine"

    ns.declaredName = "Vehicle"
    assert kerml_kernel.qualified_name(member) == "Vehicle::Engine"


# --- delete-direction: non-owning references must NOT cascade ----------------


def test_delete_import_does_not_delete_imported_element(element_factory):
    importer = element_factory.create(kerml.Namespace)
    imported = element_factory.create(kerml.Element)
    imp = element_factory.create(kerml.Import)
    kerml_kernel.add_import(importer, imported, imp)

    imported_id = imported.id
    imp.unlink()

    assert element_factory.lookup(imported_id) is not None


def test_delete_specializing_type_does_not_delete_general(element_factory):
    # A Feature is a Type; a Specialization relates specific->general via
    # non-owning refs, so deleting the specific type must not delete the general
    # one. (Specialization is the M1b-era relationship used here; FeatureTyping
    # also proves this property and is covered by the M2 persistence tests.)
    general = element_factory.create(kerml.Type)
    specific = element_factory.create(kerml.Feature)
    spec = element_factory.create(kerml.Specialization)
    spec.general = general
    spec.specific = specific

    general_id = general.id
    specific.unlink()

    assert element_factory.lookup(general_id) is not None


def test_delete_specialization_does_not_delete_general_or_specific(element_factory):
    general = element_factory.create(kerml.Type)
    specific = element_factory.create(kerml.Type)
    spec = element_factory.create(kerml.Specialization)
    spec.general = general
    spec.specific = specific

    general_id, specific_id = general.id, specific.id
    spec.unlink()

    assert element_factory.lookup(general_id) is not None
    assert element_factory.lookup(specific_id) is not None


def test_delete_member_does_not_delete_owning_namespace(element_factory):
    ns = element_factory.create(kerml.Namespace)
    member = element_factory.create(kerml.Element)
    _add_member(element_factory, ns, member)

    ns_id = ns.id
    member.unlink()

    assert element_factory.lookup(ns_id) is not None
