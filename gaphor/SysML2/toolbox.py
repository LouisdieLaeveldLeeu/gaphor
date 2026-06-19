"""SysML v2 toolbox and diagram metadata.

Phase A introduced the modeling-language UI foundation. Later construct phases
added the per-construct create-and-project toolbox entries recorded in the
support matrix.
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


requirements = ToolSection(
    gettext("Requirements"),
    (
        ToolDef(
            "toolbox-constraint-definition",
            gettext("Constraint Definition"),
            "gaphor-constraint-symbolic",
            None,
            new_item_factory(
                sysml2_items.ConstraintDefinitionItem,
                sysml2_model.ConstraintDefinition,
                config_func=_declared_name_config("ConstraintDefinition"),
            ),
            handle_index=SE,
        ),
        ToolDef(
            "toolbox-constraint-usage",
            gettext("Constraint Usage"),
            "gaphor-constraint-symbolic",
            None,
            new_item_factory(
                sysml2_items.ConstraintUsageItem,
                sysml2_model.ConstraintUsage,
                config_func=_declared_name_config("constraintUsage"),
            ),
            handle_index=SE,
        ),
        ToolDef(
            "toolbox-requirement-definition",
            gettext("Requirement Definition"),
            "gaphor-requirement-symbolic",
            None,
            new_item_factory(
                sysml2_items.RequirementDefinitionItem,
                sysml2_model.RequirementDefinition,
                config_func=_declared_name_config("RequirementDefinition"),
            ),
            handle_index=SE,
        ),
        ToolDef(
            "toolbox-requirement-usage",
            gettext("Requirement Usage"),
            "gaphor-requirement-symbolic",
            None,
            new_item_factory(
                sysml2_items.RequirementUsageItem,
                sysml2_model.RequirementUsage,
                config_func=_declared_name_config("requirementUsage"),
            ),
            handle_index=SE,
        ),
    ),
)


ports = ToolSection(
    gettext("Ports"),
    (
        ToolDef(
            "toolbox-port-definition",
            gettext("Port Definition"),
            "gaphor-proxy-port-symbolic",
            None,
            new_item_factory(
                sysml2_items.PortDefinitionItem,
                sysml2_model.PortDefinition,
                config_func=_declared_name_config("PortDefinition"),
            ),
            handle_index=SE,
        ),
        ToolDef(
            "toolbox-port-usage",
            gettext("Port Usage"),
            "gaphor-proxy-port-symbolic",
            None,
            new_item_factory(
                sysml2_items.PortUsageItem,
                sysml2_model.PortUsage,
                config_func=_declared_name_config("portUsage"),
            ),
            handle_index=SE,
        ),
    ),
)


connections = ToolSection(
    gettext("Connections"),
    (
        ToolDef(
            "toolbox-connection-definition",
            gettext("Connection Definition"),
            "gaphor-association-symbolic",
            None,
            new_item_factory(
                sysml2_items.ConnectionDefinitionItem,
                sysml2_model.ConnectionDefinition,
                config_func=_declared_name_config("ConnectionDefinition"),
            ),
            handle_index=SE,
        ),
        ToolDef(
            "toolbox-connection-usage",
            gettext("Connection Usage"),
            "gaphor-connector-symbolic",
            None,
            new_item_factory(
                sysml2_items.ConnectionUsageItem,
                sysml2_model.ConnectionUsage,
                config_func=_declared_name_config("connectionUsage"),
            ),
            handle_index=SE,
        ),
    ),
)


sysml2_toolbox_actions: ToolboxDefinition = (
    packages,
    parts,
    attributes,
    actions,
    requirements,
    ports,
    connections,
)

sysml2_diagram_types: DiagramTypes = (
    SysML2DiagramType(
        SysML2Diagram,
        i18nize("SysML v2 Diagram"),
        (packages, parts, attributes, actions, requirements, ports, connections),
    ),
)

sysml2_element_types = ()

kerml_toolbox_actions: ToolboxDefinition = ()
kerml_diagram_types: DiagramTypes = ()
kerml_element_types = ()
