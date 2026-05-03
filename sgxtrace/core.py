"""
Internal aggregator that re-exports the core trace primitives.

Exists so other modules (e.g. interactive.py) can import everything
they need from a single place without depending on the layout of the
sub-modules. The public package-level API lives in __init__.py.
"""

from __future__ import annotations

from .model import NavigatorState, StepResult, TraceData
from .navigator import TraceNavigator
from .parser import is_page_signal, load_vcd_trace, normalize_page_name
from .attack import AttackRunner

__all__ = [
    "TraceData",
    "TraceNavigator",
    "AttackRunner",
    "load_vcd_trace",
    "is_page_signal",
    "normalize_page_name",
    "NavigatorState",
    "StepResult",
]
