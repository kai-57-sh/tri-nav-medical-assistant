"""Capability registry for TriNav v2 runtime."""

import inspect
from typing import Any, cast

from src.core.capability.protocol import Capability


class CapabilityRegistry:
    """In-memory registry of runtime capabilities keyed by capability name."""

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        """Register a capability; raises ValueError when name is already taken."""

        capability_obj = cast(Any, capability)
        name = getattr(capability_obj, "name", None)
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                "Capability must define non-empty string 'name' "
                "(e.g. capability.name = 'triage')."
            )

        version = getattr(capability_obj, "version", None)
        if not isinstance(version, str) or not version.strip():
            raise TypeError(
                f"Capability '{name}' must define string 'version' "
                "(e.g. capability.version = 'v1')."
            )

        for method_name in ("plan", "run", "fallback"):
            method = getattr(capability_obj, method_name, None)
            if method is None:
                raise TypeError(
                    f"Capability '{name}' must define async method '{method_name}'."
                )
            if not callable(method):
                raise TypeError(
                    f"Capability '{name}.{method_name}' must be callable and async."
                )
            if not inspect.iscoroutinefunction(method):
                raise TypeError(
                    f"Capability '{name}' must define async method '{method_name}'."
                )

        if name in self._capabilities:
            raise ValueError(f"Capability '{name}' is already registered")

        self._capabilities[name] = capability

    def get(self, name: str) -> Capability | None:
        """Return capability by name, if present."""

        return self._capabilities.get(name)

    def list_names(self) -> list[str]:
        """Return capability names in registration order."""

        return list(self._capabilities.keys())
