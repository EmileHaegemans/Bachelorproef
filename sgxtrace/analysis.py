import bisect
from collections import Counter
from typing import Dict, List, Tuple

from .model import TraceData
from .parser import normalize_page_name


def get_page_intervals(
    trace: TraceData,
    page: str,
    start_filter: int | None = None,
    end_filter: int | None = None,
) -> List[Tuple[int, int]]:
    target = normalize_page_name(page, trace.page_intervals)

    if target not in trace.page_intervals:
        return []

    intervals = trace.page_intervals[target]

    # Use binary search to find relevant intervals if filters are provided
    if start_filter is None and end_filter is None:
        return intervals

    filtered: List[Tuple[int, int]] = []
    # Binary search to find the first interval that could match
    # Intervals are sorted by start time
    start_idx = 0
    if start_filter is not None:
        # Find first interval where end >= start_filter
        # Since intervals are sorted by start, and end > start, we can still use this as a heuristic
        # but a simple loop over the sorted intervals is already quite fast once we find the start point.
        start_idx = bisect.bisect_left([i[1] for i in intervals], start_filter)

    for i in range(start_idx, len(intervals)):
        start, end = intervals[i]
        if end_filter is not None and start > end_filter:
            break
        filtered.append((start, end))

    return filtered


def get_top_pages(trace: TraceData, n: int = 10) -> List[Tuple[str, int]]:
    counts = Counter({page: len(intervals) for page, intervals in trace.page_intervals.items()})
    return counts.most_common(n)


def get_timeline_by_time(trace: TraceData, start_t: int, end_t: int) -> List[Tuple[int, str]]:
    # Use binary search on access_history (sorted by timestamp)
    times = [item[0] for item in trace.access_history]

    start_idx = bisect.bisect_left(times, start_t)
    end_idx = bisect.bisect_right(times, end_t)

    return trace.access_history[start_idx:end_idx]


def get_access_trace_slice(trace: TraceData, start_idx: int, end_idx: int) -> List[Tuple[int, str]]:
    history = trace.access_history
    start_idx = max(0, start_idx)
    end_idx = min(len(history), end_idx)

    if start_idx >= end_idx:
        return []

    return history[start_idx:end_idx]


def get_transitions(trace: TraceData, page: str) -> Dict[str, List[int]]:
    """
    Return pages that immediately follow the given page in access_history.
    Uses the pre-calculated transition_map for O(1) lookup.
    """
    target = normalize_page_name(page, trace.page_intervals)
    return trace.transition_map.get(target, {})