"""Flat model-browser model for SysML2/KerML elements.

This is the Phase A browser foundation: it lists SysML2/KerML elements without
claiming ownership-tree semantics or per-construct editing. Deeper grouping
belongs with the later UI-edit phases.
"""

from __future__ import annotations

import importlib.resources
import weakref
from unicodedata import normalize

import gi

gi.require_version("Pango", "1.0")
from gi.repository import Gio, GObject, Pango

from gaphor.core import event_handler
from gaphor.core.modeling import (
    Base,
    Diagram,
    ElementCreated,
    ElementDeleted,
    ElementUpdated,
    ModelFlushed,
    ModelReady,
    Presentation,
)
from gaphor.diagram.iconname import icon_name
from gaphor.i18n import gettext
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk

_BROWSER_LANGUAGES = {"KerML", "SysML2"}

# Structural plumbing: the relationship/membership EDGES that implement the model
# (ownership memberships, typing, specialization, conjugation, feature chaining,
# imports). They are not user concepts, so the browser hides them by default --
# unless an internal/debug view is requested (Phase 13 grooming). User USAGES that
# happen to be relationships (a ConnectionUsage IS a Connector) are NOT listed here,
# so they stay visible.
_PLUMBING_TYPES = (
    kerml.Membership,
    kerml.FeatureTyping,
    kerml.Specialization,
    kerml.Conjugation,
    kerml.FeatureChaining,
    kerml.Import,
)


def _browser_name(element: Base) -> str:
    if isinstance(element, Diagram):
        return element.name or gettext("<Unnamed diagram>")
    if declared_name := getattr(element, "declaredName", None):
        return str(declared_name)
    return type(element).__name__


def _is_plumbing(element: Base) -> bool:
    """Whether `element` is internal plumbing the groomed browser hides: a structural
    relationship edge, a library value-type proxy, an implicit universal base, a
    feature-chain helper, or a conjugated-port helper definition."""
    return (
        isinstance(element, _PLUMBING_TYPES)
        or isinstance(element, sysml2.ConjugatedPortDefinition)
        or kk.is_library_proxy(element)
        or kk.is_implicit_base(element)
        or kk.is_feature_chain(element)
    )


def _is_browser_element(element: Base, show_internal: bool = False) -> bool:
    if isinstance(element, Presentation):
        return False
    if element.__modeling_language__ not in _BROWSER_LANGUAGES:
        return False
    return show_internal or not _is_plumbing(element)


class TreeItem(GObject.Object):
    def __init__(self, element: Base):
        super().__init__()
        self.element = element
        self.sync()

    icon = GObject.Property(type=str)
    icon_visible = GObject.Property(type=bool, default=True)
    readonly_text = GObject.Property(type=str)
    attributes = GObject.Property(type=Pango.AttrList)
    editing = GObject.Property(type=bool, default=False)
    can_edit = GObject.Property(type=bool, default=True)

    @GObject.Property(type=str)
    def editable_text(self):
        if isinstance(self.element, Diagram):
            return self.element.name or ""
        return str(getattr(self.element, "declaredName", "") or "")

    @editable_text.setter  # type: ignore[no-redef]
    def editable_text(self, text):
        if isinstance(self.element, Diagram):
            self.element.name = text or ""
        elif hasattr(self.element, "declaredName"):
            self.element.declaredName = text or ""

    def sync(self) -> None:
        self.readonly_text = _browser_name(self.element)
        self.notify("editable-text")
        self.icon = icon_name(self.element)
        self.icon_visible = bool(self.icon)
        self.attributes = pango_attributes(self.element)

    def start_editing(self):
        self.editing = True


def tree_item_sort(a: TreeItem, b: TreeItem) -> int:
    an = normalize("NFC", a.readonly_text).casefold()
    bn = normalize("NFC", b.readonly_text).casefold()
    return (an > bn) - (an < bn)


class TreeModel:
    #: When True, the browser also lists internal plumbing (an internal/debug view).
    #: Class-level so a single toggle action grooms every open model browser; live
    #: instances are refreshed by `set_show_internal`.
    show_internal: bool = False
    _instances: "weakref.WeakSet[TreeModel]" = weakref.WeakSet()

    def __init__(self, event_manager, element_factory, on_select=None, on_sync=None):
        self.event_manager = event_manager
        self.element_factory = element_factory
        self._on_sync = on_sync
        self._root = Gio.ListStore.new(TreeItem.__gtype__)

        event_manager.subscribe(self.on_element_created)
        event_manager.subscribe(self.on_element_deleted)
        event_manager.subscribe(self.on_element_updated)
        event_manager.subscribe(self.on_model_ready)
        TreeModel._instances.add(self)

        self.on_model_ready()

    @classmethod
    def set_show_internal(cls, value: bool) -> None:
        """Toggle the internal/debug view for every open model browser and rebuild it."""
        cls.show_internal = value
        for instance in list(cls._instances):
            instance.on_model_ready()

    def shutdown(self) -> None:
        self.event_manager.unsubscribe(self.on_element_created)
        self.event_manager.unsubscribe(self.on_element_deleted)
        self.event_manager.unsubscribe(self.on_element_updated)
        self.event_manager.unsubscribe(self.on_model_ready)

    @property
    def template(self) -> str:
        return (
            importlib.resources.files("gaphor.SysML2") / "treeitem.ui"
        ).read_text(encoding="utf-8")

    @property
    def root(self) -> Gio.ListStore:
        return self._root

    def child_model(self, item: TreeItem) -> Gio.ListStore | None:
        return None

    def tree_item_sort(self, a, b) -> int:
        return tree_item_sort(a, b)

    def should_expand(self, item: TreeItem, element: Base) -> bool:
        return False

    def _find_index(self, element: Base) -> int | None:
        return next(
            (i for i, tree_item in enumerate(self._root) if tree_item.element is element),
            None,
        )

    def _sync_changed(self):
        if self._on_sync:
            self._on_sync()

    def add_element(self, element: Base) -> None:
        if (
            not _is_browser_element(element, type(self).show_internal)
            or self._find_index(element) is not None
        ):
            return
        self._root.append(TreeItem(element))
        self._sync_changed()

    def remove_element(self, element: Base) -> None:
        if (index := self._find_index(element)) is not None:
            self._root.remove(index)
            self._sync_changed()

    def sync_element(self, element: Base) -> None:
        if (index := self._find_index(element)) is not None:
            self._root[index].sync()
            self._root.items_changed(index, 1, 1)
            self._sync_changed()

    @event_handler(ElementCreated)
    def on_element_created(self, event: ElementCreated):
        self.add_element(event.element)

    @event_handler(ElementDeleted)
    def on_element_deleted(self, event: ElementDeleted):
        self.remove_element(event.element)

    @event_handler(ElementUpdated)
    def on_element_updated(self, event: ElementUpdated):
        self.sync_element(event.element)

    @event_handler(ModelReady, ModelFlushed)
    def on_model_ready(self, _event=None):
        self._root.remove_all()
        show_internal = type(self).show_internal
        for element in self.element_factory.select(
            lambda e: _is_browser_element(e, show_internal)
        ):
            self._root.append(TreeItem(element))
        self._sync_changed()


def pango_attributes(element):
    attrs = Pango.AttrList.new()
    attrs.insert(
        Pango.attr_weight_new(
            Pango.Weight.BOLD if isinstance(element, Diagram) else Pango.Weight.NORMAL
        )
    )
    return attrs
