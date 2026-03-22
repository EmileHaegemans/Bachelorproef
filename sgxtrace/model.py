from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class TraceData:
    events: List[Dict[str, str]]
    times: List[int]
    page_intervals: Dict[str, List[Tuple[int, int]]]
    access_history: List[Tuple[int, str]]


@dataclass(frozen=True)
class StepResult:
    steps_done: int
    trace_index: int
    time: Optional[int]
    added: Set[str]
    removed: Set[str]
    breakpoint_hit: Optional[str]
    end_of_trace: bool


@dataclass
class NavigatorState:
    trace_index: int = -1
    current_values: Dict[str, str] = field(default_factory=dict)
    active_pages: Set[str] = field(default_factory=set)
    page_breakpoints: Set[str] = field(default_factory=set)
    last_diff: Tuple[Set[str], Set[str]] = field(default_factory=lambda: (set(), set()))