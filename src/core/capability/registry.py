"""Capability registry for TriNav v2 runtime."""

from src.core.capability.protocol import Capability


class CapabilityRegistry:
    """In-memory registry of runtime capabilities keyed by capability name."""

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        """Register a capability; raises ValueError when name is already taken."""

        if capability.name in self._capabilities:
            raise ValueError(f"Capability '{capability.name}' is already registered")

        self._capabilities[capability.name] = capability

    def get(self, name: str) -> Capability | None:
        """Return capability by name, if present."""

        return self._capabilities.get(name)

    def list_names(self) -> list[str]:
        """Return capability names in registration order."""

        return list(self._capabilities.keys())
