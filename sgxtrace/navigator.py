from __future__ import annotations

from typing import Dict, Set, Tuple

from .model import NavigatorState, StepResult, TraceData
from .parser import is_page_signal, normalize_page_name


def _apply_changes(
    current_values: Dict[str, str],
    active_pages: Set[str],
    changes: Dict[str, str],
) -> Tuple[List[str], List[str]]:
    added: List[str] = []
    removed: List[str] = []

    for sig, val in changes.items():
        current_values[sig] = val

        if not is_page_signal(sig):
            continue

        if val == "1":
            if sig not in active_pages:
                active_pages.add(sig)
                added.append(sig)
        else:
            if sig in active_pages:
                active_pages.remove(sig)
                removed.append(sig)

    return added, removed


class TraceNavigator:
    def __init__(self, trace: TraceData):
        self.trace = trace
        self.state = NavigatorState()
        self._history_times = [item[0] for item in self.trace.access_history]

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
        old_breakpoints = self.state.page_breakpoints
        self.state = NavigatorState()
        self.state.page_breakpoints = old_breakpoints

    def add_breakpoint(self, page: str) -> str:
        normalized = normalize_page_name(page, self.trace.page_intervals)
        self.state.page_breakpoints.add(normalized)
        return normalized

    def remove_breakpoint(self, page: str) -> bool:
        normalized = normalize_page_name(page, self.trace.page_intervals)
        if normalized in self.state.page_breakpoints:
            self.state.page_breakpoints.remove(normalized)
            # Remove from pending if it's there
            self.state.pending_breakpoints = [p for p in self.state.pending_breakpoints if p != normalized]
            return True
        return False

    def list_breakpoints(self) -> list[str]:
        return sorted(self.state.page_breakpoints)

    def step(self, count: int = 1) -> StepResult:
        # If we have pending breakpoints, return the first one
        if self.state.pending_breakpoints:
            hit = self.state.pending_breakpoints.pop(0)
            return StepResult(
                steps_done=0,
                trace_index=self.state.trace_index,
                time=self.current_time,
                added=set(),
                removed=set(),
                breakpoint_hit=hit,
                end_of_trace=(self.state.trace_index + 1 >= len(self.trace.events)),
            )

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
        last_added: List[str] = []
        last_removed: List[str] = []

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
            last_added = added
            last_removed = removed

            # Check for breakpoints
            hits = [p for p in added if p in self.state.page_breakpoints]
            if hits:
                hit = hits[0]
                self.state.pending_breakpoints.extend(hits[1:])
                return StepResult(
                    steps_done=steps_done,
                    trace_index=self.state.trace_index,
                    time=self.current_time,
                    added=set(last_added),
                    removed=set(last_removed),
                    breakpoint_hit=hit,
                    end_of_trace=False,
                )

        end_of_trace = self.state.trace_index + 1 >= len(self.trace.events)

        return StepResult(
            steps_done=steps_done,
            trace_index=self.state.trace_index,
            time=self.current_time,
            added=set(last_added),
            removed=set(last_removed),
            breakpoint_hit=None,
            end_of_trace=end_of_trace,
        )

    def page_step(self) -> StepResult:
        # If we have pending breakpoints, return them first
        if self.state.pending_breakpoints:
            return self.step(0)

        current_time = self.current_time if self.current_time is not None else -1
        history_times = self._history_times

        import bisect
        # Find next event in access_history that is AFTER our current index 
        # (if multiple events at same timestamp)
        # Actually, since we don't track our index in access_history, 
        # it's better to just move by 1 timestamp at a time if we hit multiple.

        next_event_idx = bisect.bisect_right(history_times, current_time)

        if next_event_idx >= len(self.trace.access_history):
            # No more page events, jump to end
            return self.step(len(self.trace.events))

        next_time = self.trace.access_history[next_event_idx][0]
        target_idx = bisect.bisect_left(self.trace.times, next_time)
        steps_to_jump = target_idx - self.state.trace_index

        if steps_to_jump <= 0:
            # If we are already at the timestamp where more events exist, 
            # we need to force a step(1) to see if we missed anything 
            # (but wait, step(0) handles pending)
            # Actually, if we are at t=0 and next_time is 0, then we missed some events at t=0.
            # But TraceNavigator's trace_index=0 ALREADY processed all changes at t=0.
            # So if we are at trace_index=0, we've seen everything at t=0.
            # The only way to see "more" at t=0 is through pending_breakpoints.

            # If no pending, we MUST move to next timestamp.
            next_event_idx = bisect.bisect_right(history_times, current_time)
            if next_event_idx < len(self.trace.access_history):
                next_time = self.trace.access_history[next_event_idx][0]
                if next_time == current_time:
                    # Wait, bisect_right(history, T) should return index where history[i] > T.
                    # So next_time MUST be > current_time.
                    pass

        return self.step(steps_to_jump)