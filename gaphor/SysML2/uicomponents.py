"""SysML v2 UI/diagram module loader.

Importing this module registers the SysML2 diagram items (`@represents`), the
projection `drop` handlers (`@drop.register`), connector adapters, and property
pages via their decorators. It is wired as a `gaphor.modules` entry point so
Gaphor loads it at startup.
"""

from gaphor.SysML2 import connectors, diagramitems, drop, propertypages  # noqa: F401
