"""Runtime plugin interfaces and registry."""

from .protocol import RuntimePlugin
from .registry import RuntimePluginRegistry

__all__ = ["RuntimePlugin", "RuntimePluginRegistry"]
