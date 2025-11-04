"""
Business Unit submodule - Split from monolithic business_unit.py

Exports:
- Bt: Core business unit model
- bu_defaults: Default preferences function
"""

from .bt_model import Bt
from .bt_helpers import bu_defaults

__all__ = ['Bt', 'bu_defaults']
