from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from .model import TraceData
from .navigator import TraceNavigator


class AttackRunner:
    """
    A declarative runner for trace-based attacks.
    It uses TraceNavigator to efficiently jump between pages of interest
    and triggers callbacks when specific pages are hit or transitions occur.
    """

    def __init__(self, trace: TraceData):
        self.nav = TraceNavigator(trace)
        self.page_callbacks: Dict[str, List[Callable[[AttackRunner], None]]] = {}
        self.transition_callbacks: Dict[Tuple[str, str], List[Callable[[AttackRunner], None]]] = {}
        
        self.state: Dict[str, Any] = {}
        self.last_interesting_page: Optional[str] = None
        self.current_page: Optional[str] = None
        self.verbose = False

    def on_page(self, page: str, callback: Callable[[AttackRunner], None]) -> None:
        """Register a callback for when a specific page is activated."""
        p_norm = self.nav.add_breakpoint(page)
        self.page_callbacks.setdefault(p_norm, []).append(callback)

    def on_transition(self, from_page: str, to_page: str, callback: Callable[[AttackRunner], None]) -> None:
        """Register a callback for a specific transition between two pages."""
        f_norm = self.nav.add_breakpoint(from_page)
        t_norm = self.nav.add_breakpoint(to_page)
        self.transition_callbacks.setdefault((f_norm, t_norm), []).append(callback)

    def run(self) -> None:
        """Execute the attack by jumping between breakpoints."""
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
