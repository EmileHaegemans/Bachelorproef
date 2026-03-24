from __future__ import annotations

from typing import Dict, Set, Tuple

from .model import NavigatorState, StepResult, TraceData
from .parser import is_page_signal, normalize_page_name


def _apply_changes(
    current_values: Dict[str, str],
    active_pages: Set[str],
    changes: Dict[str, str],
) -> Tuple[Set[str], Set[str]]:
    added: Set[str] = set()
    removed: Set[str] = set()

    for sig, val in changes.items():
        current_values[sig] = val

        if not is_page_signal(sig):
            continue

        if val == "1":
            if sig not in active_pages:
                active_pages.add(sig)
                added.add(sig)
        else:
            if sig in active_pages:
                active_pages.remove(sig)
                removed.add(sig)

    return added, removed


class TraceNavigator:
    def __init__(self, trace: TraceData):
        self.trace = trace
        self.state = NavigatorState()

    @property
    def current_step(self) -> int | None:
        if self.state.trace_index < 0:
            return None
        return self.state.trace_index

    @property
    def current_time(self) -> int | None:
        idx = self.state.trace_index
        if idx < 0 or idx >= len(self.trace.times):
            return None
        return self.trace.times[idx]

    @property
    def active_pages(self) -> set[str]:
        return set(self.state.active_pages)

    @property
    def last_diff(self) -> tuple[set[str], set[str]]:
        added, removed = self.state.last_diff
        return set(added), set(removed)

    def reset(self) -> None:
        self.state = NavigatorState()

    def add_breakpoint(self, page: str) -> str:
        normalized = normalize_page_name(page, self.trace.page_intervals)
        self.state.page_breakpoints.add(normalized)
        return normalized

    def remove_breakpoint(self, page: str) -> bool:
        normalized = normalize_page_name(page, self.trace.page_intervals)
        if normalized in self.state.page_breakpoints:
            self.state.page_breakpoints.remove(normalized)
            return True
        return False

    def list_breakpoints(self) -> list[str]:
        return sorted(self.state.page_breakpoints)

    def step(self, count: int = 1) -> StepResult:
        if count <= 0:
            return StepResult(
                steps_done=0,
                trace_index=self.state.trace_index,
                time=self.current_time,
                added=set(),
                removed=set(),
                breakpoint_hit=None,
                end_of_trace=(self.state.trace_index + 1 >= len(self.trace.events)),
            )

        steps_done = 0
        breakpoint_hit: str | None = None
        last_added: set[str] = set()
        last_removed: set[str] = set()

        for _ in range(count):
            idx = self.state.trace_index
            if idx + 1 >= len(self.trace.events):
                break

            idx += 1
            self.state.trace_index = idx
            steps_done += 1

            changes = self.trace.events[idx]
            added, removed = _apply_changes(
                self.state.current_values,
                self.state.active_pages,
                changes,
            )

            self.state.last_diff = (set(added), set(removed))
            last_added = set(added)
            last_removed = set(removed)

            for page in added:
                if page in self.state.page_breakpoints:
                    breakpoint_hit = page
                    return StepResult(
                        steps_done=steps_done,
                        trace_index=self.state.trace_index,
                        time=self.current_time,
                        added=last_added,
                        removed=last_removed,
                        breakpoint_hit=breakpoint_hit,
                        end_of_trace=False,
                    )

        end_of_trace = self.state.trace_index + 1 >= len(self.trace.events)

        return StepResult(
            steps_done=steps_done,
            trace_index=self.state.trace_index,
            time=self.current_time,
            added=last_added,
            removed=last_removed,
            breakpoint_hit=breakpoint_hit,
            end_of_trace=end_of_trace,
        )

    def page_step(self) -> StepResult:
        # Use binary search to find the next interesting time point in access_history
        current_time = self.current_time or -1
        history_times = [item[0] for item in self.trace.access_history]

        # Find index of first event with time > current_time
        import bisect
        next_event_idx = bisect.bisect_right(history_times, current_time)

        if next_event_idx >= len(self.trace.access_history):
            # No more page events, step to the end of the trace
            return self.step(len(self.trace.events))

        next_time = self.trace.access_history[next_event_idx][0]

        # Find the index in trace.times for this timestamp
        target_idx = bisect.bisect_left(self.trace.times, next_time)

        # Calculate how many steps to skip
        steps_to_jump = target_idx - self.state.trace_index

        return self.step(steps_to_jump)