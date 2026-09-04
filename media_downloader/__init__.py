#!/usr/bin/env python

import importlib
import inspect
from typing import Any

__all__: list[str] = []

CORE_MODULES: list[str] = ["media_downloader.media_downloader"]

OPTIONAL_MODULES = {
    "media_downloader.agent_server": "agent",
    "media_downloader.mcp_server": "mcp",
}


def _expose_members(module):
    """Expose public classes and functions from a module into globals and __all__."""
    for name, obj in inspect.getmembers(module):
        if (inspect.isclass(obj) or inspect.isfunction(obj)) and not name.startswith(
            "_"
        ):
            globals()[name] = obj
            if name not in __all__:
                __all__.append(name)


# Eagerly import core modules (keeps API wrappers fast & light)
for module_name in CORE_MODULES:
    if module_name:
        module = importlib.import_module(module_name)
        _expose_members(module)

# Dynamic/lazy loading of optional modules (agent_server, mcp_server)
_loaded_optional_modules: dict[str, Any] = {}


def _import_module_safely(module_name: str):
    """Try to import a module and return it, or None if not available."""
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


_AVAILABILITY_MARKERS = {
    "_MCP_AVAILABLE": "mcp_server",
    "_AGENT_AVAILABLE": "agent_server",
}


def _optional_module_available(marker_substring: str) -> bool:
    """Resolve one of the ``_*_AVAILABLE`` dynamic flags without eager imports."""
    module_name = next((k for k in OPTIONAL_MODULES if marker_substring in k), None)
    if module_name is None:
        return False
    return _import_module_safely(module_name) is not None


def _ensure_optional_module_loaded(module_name: str):
    if module_name not in _loaded_optional_modules:
        module = _import_module_safely(module_name)
        if module is not None:
            _loaded_optional_modules[module_name] = module
            _expose_members(module)
    return _loaded_optional_modules.get(module_name)


def _find_optional_attr(name: str) -> Any:
    for module_name in OPTIONAL_MODULES:
        module = _ensure_optional_module_loaded(module_name)
        if module is not None and hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __getattr__(name: str) -> Any:
    marker_substring = _AVAILABILITY_MARKERS.get(name)
    if marker_substring is not None:
        return _optional_module_available(marker_substring)
    return _find_optional_attr(name)


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + __all__)
