"""
Declarative event-driven runner for trace-based side-channel attacks.

AttackRunner wraps a TraceNavigator and lets the caller register
callbacks on page activations and on page-to-page transitions. The
runner walks the trace via page_step() and dispatches callbacks at
every breakpoint hit.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from .model import TraceData
from .navigator import TraceNavigator


class AttackRunner:
    """
    Declarative runner for trace-based attacks.

    Uses TraceNavigator to jump between pages of interest and
    triggers user-supplied callbacks when specific pages are hit
    or specific transitions occur.
    """

    def __init__(self, trace: TraceData):
        """
        Wrap a parsed trace in a fresh runner.

        @param trace the TraceData to attack
        """
        self.nav = TraceNavigator(trace)
        self.page_callbacks: Dict[str, List[Callable[[AttackRunner], None]]] = {}
        self.transition_callbacks: Dict[Tuple[str, str], List[Callable[[AttackRunner], None]]] = {}

        # Shared scratchpad available to every callback. Attacks use
        # this to accumulate symbols, results and any per-attack state.
        self.state: Dict[str, Any] = {}

        # The previous breakpoint page hit, used to detect transitions.
        self.last_interesting_page: Optional[str] = None

        # The breakpoint page currently being processed.
        self.current_page: Optional[str] = None

        # When True, the runner prints a debug line at every breakpoint hit.
        self.verbose = False

    def on_page(self, page: str, callback: Callable[[AttackRunner], None]) -> None:
        """
        Register a callback fired when a page becomes active.

        Internally adds page as a navigator breakpoint.

        @param page the page name (canonicalized via normalize_page_name)
        @param callback function receiving this runner when the page activates
        """
        p_norm = self.nav.add_breakpoint(page)
        self.page_callbacks.setdefault(p_norm, []).append(callback)

    def on_transition(self, from_page: str, to_page: str, callback: Callable[[AttackRunner], None]) -> None:
        """
        Register a callback fired on a specific page transition.

        The callback fires when to_page activates immediately after
        from_page (i.e. with no other breakpoint hit in between).
        Both pages are added as navigator breakpoints.

        @param from_page the source page of the transition
        @param to_page the destination page of the transition
        @param callback function receiving this runner when the transition occurs
        """
        f_norm = self.nav.add_breakpoint(from_page)
        t_norm = self.nav.add_breakpoint(to_page)
        self.transition_callbacks.setdefault((f_norm, t_norm), []).append(callback)

    def run(self) -> None:
        """
        Execute the attack by jumping between breakpoints.

        Resets the navigator, then repeatedly calls page_step until
        end-of-trace. At every breakpoint hit fires all matching
        page callbacks first, then any transition callbacks for
        (last_interesting_page, current_page).
        """
        self.nav.reset()
        self.last_interesting_page = None
        self.current_page = None

        if self.verbose:
            print(f"Starting attack on trace with {len(self.nav.trace.events)} events...")
        
        while True:
            # Efficiently jump to the next page event
            # page_step() jumps to the next time ANY page changes, 
            # but it will stop early if it hits a breakpoint.
            res = self.nav.page_step()
            
            if res.breakpoint_hit:
                self.current_page = res.breakpoint_hit
                
                if self.verbose:
                    print(f"DEBUG: hit breakpoint {self.current_page} at t={res.time}")
                
                # Execute page callbacks
                for cb in self.page_callbacks.get(self.current_page, []):
                    cb(self)
                
                # Execute transition callbacks
                if self.last_interesting_page:
                    transition = (self.last_interesting_page, self.current_page)
                    for cb in self.transition_callbacks.get(transition, []):
                        if self.verbose:
                            print(f"DEBUG: transition {transition[0]} -> {transition[1]}")
                        cb(self)
                
                self.last_interesting_page = self.current_page
            
            if res.end_of_trace:
                if self.verbose:
                    print("End of trace reached.")
                break
            
            # If we didn't hit a breakpoint and it's not the end, 
            # it means we hit a regular page change. We just continue.
            if not res.breakpoint_hit and res.steps_done == 0:
                # Safety break to prevent actual infinite loops if navigator doesn't advance
                break
