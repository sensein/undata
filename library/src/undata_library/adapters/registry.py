"""Adapter registry with auto-detection and entry point discovery."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

from .base import BaseAdapter

logger = logging.getLogger(__name__)

_BUILTIN_ADAPTERS: dict[str, str] = {
    "bids": "undata_library.adapters.bids:BIDSAdapter",
    "nwb": "undata_library.adapters.nwb:NWBAdapter",
    "dandi": "undata_library.adapters.dandi:DANDIAdapter",
    "openminds": "undata_library.adapters.openminds:OpenMINDSAdapter",
    "aind": "undata_library.adapters.aind:AINDAdapter",
    "json-schema": "undata_library.adapters.json_schema:JSONSchemaAdapter",
    "linkml": "undata_library.adapters.linkml:LinkMLAdapter",
    "csv": "undata_library.adapters.csv_dictionary:CSVDictionaryAdapter",
    "code-repo": "undata_library.adapters.code_repo:CodeRepoAdapter",
    "openneuro": "undata_library.adapters.openneuro:OpenNeuroAdapter",
    "reproschema": "undata_library.adapters.reproschema:ReproSchemaAdapter",
    "nda": "undata_library.adapters.nda:NDAAdapter",
}

# File extension → adapter name for auto-detection
_FORMAT_MAP: dict[str, str] = {
    ".json": "json-schema",
    ".yaml": "linkml",
    ".yml": "linkml",
    ".csv": "csv",
    ".tsv": "csv",
}


class AdapterRegistry:
    """Registry for schema source adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, type[BaseAdapter]] = {}
        self._instances: dict[str, BaseAdapter] = {}

    def register(self, adapter_class: type[BaseAdapter]) -> None:
        """Register an adapter class."""
        instance = adapter_class()
        self._adapters[instance.name] = adapter_class
        self._instances[instance.name] = instance

    def get(self, name: str) -> BaseAdapter:
        """Get adapter by name."""
        if name in self._instances:
            return self._instances[name]

        # Try builtin lazy load
        if name in _BUILTIN_ADAPTERS:
            cls = _load_class(_BUILTIN_ADAPTERS[name])
            self.register(cls)
            return self._instances[name]

        raise KeyError(f"Unknown adapter: {name}. Available: {list(self._instances.keys())}")

    def auto_detect(self, path: Path) -> BaseAdapter:
        """Auto-detect adapter from path characteristics."""
        if path.is_file():
            ext = path.suffix.lower()
            adapter_name = _FORMAT_MAP.get(ext)
            if adapter_name:
                return self.get(adapter_name)

        # Directory-level detection
        if path.is_dir():
            if (path / "pyproject.toml").exists() or (path / "package.json").exists():
                return self.get("code-repo")

        raise ValueError(f"Cannot auto-detect adapter for: {path}")

    def list_adapters(self) -> list[str]:
        """List all registered + builtin adapter names."""
        return sorted(set(self._instances.keys()) | set(_BUILTIN_ADAPTERS.keys()))

    def discover_entry_points(self) -> None:
        """Discover adapters registered via entry points."""
        try:
            from importlib.metadata import entry_points

            eps = entry_points(group="undata.adapters")
            for ep in eps:
                try:
                    cls = ep.load()
                    if isinstance(cls, type) and issubclass(cls, BaseAdapter):
                        self.register(cls)
                        logger.info("Discovered adapter via entry point: %s", ep.name)
                except Exception as exc:
                    logger.warning("Failed to load adapter entry point %s: %s", ep.name, exc)
        except Exception:
            pass


def get_default_registry() -> AdapterRegistry:
    """Create a registry with builtin adapters pre-registered."""
    registry = AdapterRegistry()
    # Lazy registration — builtins are loaded on first access
    registry.discover_entry_points()
    return registry


def _load_class(dotted: str) -> type[BaseAdapter]:
    """Load a class from 'module.path:ClassName' string."""
    module_path, class_name = dotted.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)
