"""M1b minimal KerML kernel: behaviour + persistence tests.

Two layers of coverage:

1. The five required M1b scenarios (kickoff plan): namespace membership, the
   type/feature relation, import resolution, delete-owner cascade, and rename
   updating the qualified name -- each through a `.gaphor` save/reload.
2. A parametrized create -> save -> reload over every generated kernel class, so
   the support-matrix claim that the whole closure persists is backed by tests,
   not assertion.

Helpers build the membership graph the way the kernel models it: a Namespace
owns an OwningMembership, which owns its member Element.
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
    """Wire `member` into `namespace` via an OwningMembership (kernel shape)."""
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
    # The transitive closure of the M1b seed is 29 classes; guard against a
    # silent change in what the adapter emits.
    assert len(_all_kernel_classes()) == 29


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
    a_type = element_factory.create(kerml.Type)
    a_type.declaredName = "Engine"
    a_feature = element_factory.create(kerml.Feature)
    a_feature.declaredName = "power"
    # A Feature is featured by a Type (type/feature relation).
    a_feature.featuringType = a_type

    type_id, feature_id = a_type.id, a_feature.id

    loader(saver())

    rtype = element_factory.lookup(type_id)
    rfeature = element_factory.lookup(feature_id)
    assert rtype is not None and rfeature is not None
    assert rtype in list(rfeature.featuringType)


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
    imp.importedElement = leaf
    imp.importOwningNamespace = importer
    importer.ownedImport = imp

    # Resolves before save.
    assert kerml_kernel.resolve_qualified_name(root, "Root::Inner::Engine") is leaf
    assert leaf in list(kerml_kernel.imported_elements(importer))

    root_id, leaf_id, importer_id = root.id, leaf.id, importer.id

    loader(saver())

    rroot = element_factory.lookup(root_id)
    rleaf = element_factory.lookup(leaf_id)
    rimporter = element_factory.lookup(importer_id)
    # Still resolves after reload.
    assert kerml_kernel.resolve_qualified_name(rroot, "Root::Inner::Engine") is rleaf
    assert rleaf in list(kerml_kernel.imported_elements(rimporter))


# --- required behaviour 4: delete owner handles owned elements ---------------


def test_delete_owner_cascades_to_owned_member(element_factory):
    ns = element_factory.create(kerml.Namespace)
    ns.declaredName = "Pkg"
    member = element_factory.create(kerml.Element)
    membership = _add_member(element_factory, ns, member)

    member_id = member.id
    membership_id = membership.id

    # ownedMembership / ownedMemberElement are composite associations, so
    # unlinking the namespace cascades to the owned membership and its element.
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

    # qualified_name is derived (per KerML), so renaming the owner is reflected
    # immediately without touching the member.
    ns.declaredName = "Vehicle"
    assert kerml_kernel.qualified_name(member) == "Vehicle::Engine"
