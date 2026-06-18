"""SysML v2 toolbox and diagram metadata.

Phase A intentionally exposes the modeling-language UI foundation only. It does
not add per-construct toolbox entries; those land in the construct promotion
phases that also add property pages and conformance tests.
"""

from __future__ import annotations

from gaphas.item import SE

from gaphor.diagram.diagramtoolbox import (
    DiagramTypes,
    ToolboxDefinition,
    ToolDef,
    ToolSection,
    new_item_factory,
)
from gaphor.i18n import gettext, i18nize
from gaphor.SysML2 import kerml
from gaphor.SysML2 import sysml2 as sysml2_model
from gaphor.SysML2 import diagramitems as sysml2_items
from gaphor.SysML2.diagramtype import SysML2Diagram, SysML2DiagramType


def _declared_name_config(default_name: str):
    def config(item) -> None:
        if item.subject:
            item.subject.declaredName = default_name

    return config


packages = ToolSection(
    gettext("Packages"),
    (
        ToolDef(
            "toolbox-package",
            gettext("Package"),
            "gaphor-package-symbolic",
            None,
            new_item_factory(
                sysml2_items.PackageItem,
                kerml.Package,
                config_func=_declared_name_config("Package"),
            ),
            handle_index=SE,
        ),
    ),
)


parts = ToolSection(
    gettext("Parts"),
    (
        ToolDef(
            "toolbox-part-definition",
            gettext("Part Definition"),
            "gaphor-block-symbolic",
            None,
            new_item_factory(
                sysml2_items.PartDefinitionItem,
                sysml2_model.PartDefinition,
                config_func=_declared_name_config("PartDefinition"),
            ),
            handle_index=SE,
        ),
        ToolDef(
            "toolbox-part-usage",
            gettext("Part Usage"),
            "gaphor-usage-symbolic",
            None,
            new_item_factory(
                sysml2_items.PartUsageItem,
                sysml2_model.PartUsage,
                config_func=_declared_name_config("partUsage"),
            ),
            handle_index=SE,
        ),
    ),
)

attributes = ToolSection(
    gettext("Attributes"),
    (
        ToolDef(
            "toolbox-attribute-definition",
            gettext("Attribute Definition"),
            "gaphor-data-type-symbolic",
            None,
            new_item_factory(
                sysml2_items.AttributeDefinitionItem,
                sysml2_model.AttributeDefinition,
                config_func=_declared_name_config("AttributeDefinition"),
            ),
            handle_index=SE,
        ),
        ToolDef(
            "toolbox-attribute-usage",
            gettext("Attribute Usage"),
            "gaphor-property-symbolic",
            None,
            new_item_factory(
                sysml2_items.AttributeUsageItem,
                sysml2_model.AttributeUsage,
                config_func=_declared_name_config("attributeUsage"),
            ),
            handle_index=SE,
        ),
    ),
)


actions = ToolSection(
    gettext("Actions"),
    (
        ToolDef(
            "toolbox-action-definition",
            gettext("Action Definition"),
            "gaphor-activity-symbolic",
            None,
            new_item_factory(
                sysml2_items.ActionDefinitionItem,
                sysml2_model.ActionDefinition,
                config_func=_declared_name_config("ActionDefinition"),
            ),
            handle_index=SE,
        ),
        ToolDef(
            "toolbox-action-usage",
            gettext("Action Usage"),
            "gaphor-action-symbolic",
            None,
            new_item_factory(
                sysml2_items.ActionUsageItem,
                sysml2_model.ActionUsage,
                config_func=_declared_name_config("actionUsage"),
            ),
            handle_index=SE,
        ),
    ),
)


sysml2_toolbox_actions: ToolboxDefinition = (packages, parts, attributes, actions)

sysml2_diagram_types: DiagramTypes = (
    SysML2DiagramType(
        SysML2Diagram,
        i18nize("SysML v2 Diagram"),
        (packages, parts, attributes, actions),
    ),
)

sysml2_element_types = ()

kerml_toolbox_actions: ToolboxDefinition = ()
kerml_diagram_types: DiagramTypes = ()
kerml_element_types = ()
