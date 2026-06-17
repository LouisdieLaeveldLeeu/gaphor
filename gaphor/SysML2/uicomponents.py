"""SysML v2 UI/diagram module loader.

Importing this module registers the SysML2 diagram items (`@represents`) and the
projection `drop` handlers (`@drop.register`) via their decorators. It is wired
as a `gaphor.modules` entry point so Gaphor loads it at startup.
"""

from gaphor.SysML2 import diagramitems, drop  # noqa: F401
