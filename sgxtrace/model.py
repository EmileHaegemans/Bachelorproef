"""
Dataclasses shared between the parser, navigator and attack engines.

These are pure containers; all logic lives in parser.py, navigator.py,
attack.py and jpeg.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class TraceData:
    """
    Parsed VCD page-access trace and its pre-computed indices.

    Produced by parser.load_vcd_trace and consumed by every navigator,
    attack runner and analysis helper.
    """

    # Per-timestamp dict of changed signals (deltas only).
    # events[i] corresponds to timestamp times[i].
    events: List[Dict[str, str]]

    # Sorted list of every timestamp that appears in the trace.
    # Acts as the parallel index into events.
    times: List[int]

    # For every page signal, the list of (start_t, end_t) intervals
    # during which the page was continuously active.
    page_intervals: Dict[str, List[Tuple[int, int]]]

    # Chronological list of (t, page) tuples recording the first
    # activation (rising edge) of every page event in trace order.
    access_history: List[Tuple[int, str]]

    # Optional page_name -> "sym@addr, sym@addr" mapping populated by
    # sgxtrace.symbols.get_symbol_map. Empty by default.
    symbol_map: Dict[str, str] = field(default_factory=dict)

    # Per-signal (t, value) change history. Useful for inspecting
    # non-page signals or fine-grained debugging.
    signal_to_changes: Dict[str, List[Tuple[int, str]]] = field(default_factory=dict)

    # Pre-computed from_page -> {to_page: [t, ...]} index built from
    # access_history. Allows O(1) "what pages follow page X?" lookups.
    transition_map: Dict[str, Dict[str, List[int]]] = field(default_factory=dict)


@dataclass(frozen=True)
class StepResult:
    """
    Immutable result of a single TraceNavigator step.

    Returned by step() and page_step(). Tells the caller how far the
    navigator advanced, what changed, and whether a breakpoint or
    end-of-trace condition was hit.
    """

    # Number of raw events advanced. May be 0 when a pending
    # breakpoint was returned without advancing.
    steps_done: int

    # Final events/times index after this step.
    trace_index: int

    # Timestamp at trace_index, or None if the navigator is still at
    # its initial pre-trace position.
    time: Optional[int]

    # Pages that became active (rising edge) during this step.
    added: Set[str]

    # Pages that became inactive (falling edge) during this step.
    removed: Set[str]

    # Name of the page breakpoint that fired during this step,
    # or None if no breakpoint was hit.
    breakpoint_hit: Optional[str]

    # True when the navigator can no longer advance.
    end_of_trace: bool


@dataclass
class NavigatorState:
    """
    Mutable cursor state held by TraceNavigator.

    Tracks the navigator's position in the trace plus everything
    needed to resume stepping.
    """

    # Current index into TraceData.events / times.
    # -1 means "before the first event" (initial state).
    trace_index: int = -1

    # Last-seen value of every signal. Updated on every step.
    current_values: Dict[str, str] = field(default_factory=dict)

    # Set of page signals currently active (last seen value 1, no
    # falling edge since).
    active_pages: Set[str] = field(default_factory=set)

    # Pages on which the navigator should stop when they become active.
    page_breakpoints: Set[str] = field(default_factory=set)

    # (added, removed) page sets from the most recent step.
    last_diff: Tuple[Set[str], Set[str]] = field(default_factory=lambda: (set(), set()))

    # Queue of breakpoints that fired at the same timestamp as the one
    # already returned. Drained one at a time on subsequent calls.
    pending_breakpoints: List[str] = field(default_factory=list)
