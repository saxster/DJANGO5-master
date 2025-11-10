"""
Workspace bootstrap helpers (numpy macOS guard, etc.).

The NumPy wheel available in offline builds crashes on macOS (Apple Silicon)
inside `_mac_os_check` because LAPACK/Accelerate is missing vectors. Importing
NumPy at process start therefore kills `manage.py migrate`, Celery workers,
and any Django command.

We install a tiny `MetaPathFinder` that intercepts the very first `numpy`
import, temporarily masks `sys.platform` so the sanity check is skipped, and
then restores the real value. This mirrors upstream guidance until a patched
wheel is available.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import os
import sys
import warnings
from types import ModuleType
from typing import Optional

_GUARD_INSTALLED = False


def _should_bypass_numpy_check() -> bool:
    if sys.platform != "darwin":
        return False
    env_value = os.environ.get("INTELLIWIZ_BYPASS_NUMPY_MAC_CHECK", "1")
    return env_value.lower() not in {"0", "false", "no"}


def _install_numpy_guard() -> None:
    global _GUARD_INSTALLED
    if _GUARD_INSTALLED or not _should_bypass_numpy_check():
        return

    class _NumpyBypassLoader(importlib.abc.Loader):
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
        TARGET = "numpy"

        def find_spec(
            self,
            fullname: str,
            path: Optional[list[str]],
            target=None,
        ):
            if fullname != self.TARGET:
                return None
            spec = importlib.machinery.PathFinder.find_spec(fullname, path)
            if not spec or not spec.loader:
                return spec
            if getattr(spec.loader, "_intelliwiz_numpy_bypass", False):
                return spec
            spec.loader = _NumpyBypassLoader(spec.loader)
            return spec

    sys.meta_path.insert(0, _NumpyBypassFinder())
    _GUARD_INSTALLED = True


def _patch_protobuf_message_factory() -> None:
    """
    google-protobuf 5.x removed MessageFactory.GetPrototype.
    TensorFlow and other dependencies still call it, so we provide a shim
    that delegates to GetMessageClass when the method is missing.
    """
    try:
        from google.protobuf import message_factory
    except ImportError:
        return

    factory_cls = message_factory.MessageFactory
    if hasattr(factory_cls, "GetPrototype"):
        return

    def _get_prototype(self, descriptor):
        get_message_class = getattr(self, "GetMessageClass", None)
        if get_message_class is None:
            raise AttributeError("MessageFactory lacks GetMessageClass")
        return get_message_class(descriptor)

    factory_cls.GetPrototype = _get_prototype  # type: ignore[attr-defined]


_WARNING_FILTER_INSTALLED = False


def _suppress_protobuf_messagefactory_warning() -> None:
    """Hide the noisy GetPrototype deprecation warning until deps upgrade."""
    global _WARNING_FILTER_INSTALLED
    if _WARNING_FILTER_INSTALLED:
        return
    warnings.filterwarnings(
        "ignore",
        message=r".*MessageFactory.*GetPrototype.*",
        category=Warning,
        module=r"google\\.protobuf.*",
    )
    _WARNING_FILTER_INSTALLED = True


_install_numpy_guard()
_patch_protobuf_message_factory()
_suppress_protobuf_messagefactory_warning()

__all__ = ["_install_numpy_guard"]
