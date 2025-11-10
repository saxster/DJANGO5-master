"""
Runtime customizations for the Intelliwiz Django 5 workspace.

Problem
-------
On macOS (Apple Silicon), the stock NumPy wheels can segfault inside the
macOS-specific `_mac_os_check` sanity test (`polyfit` -> LAPACK) **before**
Django has a chance to start up.

Workaround
----------
We insert a lightweight `MetaPathFinder` at interpreter startup that intercepts
the *first* `numpy` import, temporarily masks `sys.platform` so the sanity check
is skipped, and then restores the real value. This keeps developer workflows
unblocked without modifying third-party packages on disk.

Set `INTELLIWIZ_BYPASS_NUMPY_MAC_CHECK=0` to disable the workaround.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import os
import sys
from types import ModuleType
from typing import Optional

_BYPASS_DEFAULT = "1"  # opt-out via env var (0/false/no)
_BYPASS_ENV = os.environ.get("INTELLIWIZ_BYPASS_NUMPY_MAC_CHECK", _BYPASS_DEFAULT)
_SHOULD_BYPASS = (
    sys.platform == "darwin"
    and _BYPASS_ENV.lower() not in {"0", "false", "no"}
)


if _SHOULD_BYPASS:
    class _NumpyBypassLoader(importlib.abc.Loader):
        """Wrap the real loader to mask sys.platform during exec."""

        def __init__(self, wrapped_loader: importlib.abc.Loader) -> None:
            self._wrapped_loader = wrapped_loader
            setattr(self._wrapped_loader, "_intelliwiz_numpy_bypass", True)

        def create_module(self, spec):
            if hasattr(self._wrapped_loader, "create_module"):
                return self._wrapped_loader.create_module(spec)  # type: ignore[no-any-return]
            return None

        def exec_module(self, module: ModuleType) -> None:
            original_platform = sys.platform
            try:
                sys.platform = "darwin-intelliwiz-numpy-bypass"
                self._wrapped_loader.exec_module(module)
            finally:
                sys.platform = original_platform


    class _NumpyBypassFinder(importlib.abc.MetaPathFinder):
        """Finder that installs the loader above for the first numpy import."""

        TARGET = "numpy"

        def find_spec(self, fullname: str, path: Optional[list[str]], target=None):
            if fullname != self.TARGET:
                return None
            spec = importlib.machinery.PathFinder.find_spec(fullname, path)
            if not spec or not spec.loader:
                return spec
            if getattr(spec.loader, "_intelliwiz_numpy_bypass", False):
                return spec  # already wrapped
            spec.loader = _NumpyBypassLoader(spec.loader)
            return spec


    # Insert ahead of default finders so we intercept before the standard loader.
    sys.meta_path.insert(0, _NumpyBypassFinder())
