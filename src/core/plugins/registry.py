"""In-memory runtime plugin registry."""

from __future__ import annotations

import inspect
from typing import Any

from src.core.plugins.protocol import RuntimePlugin
from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult


class RuntimePluginRegistry:
    """Registers runtime plugins and applies before/after hooks in order."""

    def __init__(self) -> None:
        self._plugins: dict[str, RuntimePlugin] = {}

    def register(self, plugin: RuntimePlugin) -> None:
        """Register one runtime plugin."""

        name = getattr(plugin, "name", None)
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Runtime plugin must define non-empty string 'name'.")
        if name in self._plugins:
            raise ValueError(f"Runtime plugin '{name}' is already registered")

        for method_name in ("before_execute", "after_execute"):
            method = getattr(plugin, method_name, None)
            if method is None or not callable(method):
                raise TypeError(f"Runtime plugin '{name}' missing callable '{method_name}'.")
            if not inspect.iscoroutinefunction(method):
                raise TypeError(f"Runtime plugin '{name}.{method_name}' must be async.")

        self._plugins[name] = plugin

    def list_names(self) -> list[str]:
        """List registered plugin names in registration order."""

        return list(self._plugins.keys())

    async def apply_before_execute(self, context: ExecutionContext) -> ExecutionContext:
        """Apply before hooks in order; isolate plugin failures per plugin."""

        current = context
        for plugin in self._plugins.values():
            try:
                next_context = await plugin.before_execute(current)
            except Exception as exc:
                current = self._append_plugin_error(current, plugin_name=plugin.name, stage="before", exc=exc)
                continue
            if not isinstance(next_context, ExecutionContext):
                current = self._append_plugin_error(
                    current,
                    plugin_name=plugin.name,
                    stage="before",
                    exc=TypeError("before_execute returned non-ExecutionContext"),
                )
                continue
            current = next_context
        return current

    async def apply_after_execute(
        self,
        context: ExecutionContext,
        results: list[CapabilityResult],
    ) -> list[CapabilityResult]:
        """Apply after hooks in order; keep last good results on plugin failures."""

        _ = context
        current = list(results)
        for plugin in self._plugins.values():
            try:
                maybe_results = await plugin.after_execute(context, current)
            except Exception:
                continue
            if not self._is_result_list(maybe_results):
                continue
            current = maybe_results
        return current

    def _append_plugin_error(
        self,
        context: ExecutionContext,
        *,
        plugin_name: str,
        stage: str,
        exc: Exception,
    ) -> ExecutionContext:
        metadata: dict[str, Any] = dict(context.metadata)
        errors_raw = metadata.get("_plugin_errors")
        errors: list[str]
        if isinstance(errors_raw, list):
            errors = [str(item) for item in errors_raw]
        else:
            errors = []
        errors.append(f"{plugin_name}:{stage}:{type(exc).__name__}:{exc}")
        metadata["_plugin_errors"] = errors
        return context.model_copy(update={"metadata": metadata})

    def _is_result_list(self, value: Any) -> bool:
        if not isinstance(value, list):
            return False
        return all(isinstance(item, CapabilityResult) for item in value)
