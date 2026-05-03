"""
Read-only query helpers over a parsed TraceData.

These functions never mutate the trace; they only extract slices and
aggregates from the already-computed indices (page_intervals,
access_history, transition_map).
"""

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
    """
    Return the (start, end) activation intervals for a given page.

    When start_filter is set, intervals that ended before it are
    skipped. When end_filter is set, intervals that started after it
    are skipped.

    @param trace the parsed TraceData
    @param page the page name (normalized internally)
    @param start_filter optional minimum end timestamp
    @param end_filter optional maximum start timestamp
    @return list of (start_t, end_t) tuples; empty if the page is unknown
    """
    target = normalize_page_name(page, trace.page_intervals)

    if target not in trace.page_intervals:
        return []

    intervals = trace.page_intervals[target]
    if start_filter is None and end_filter is None:
        return intervals

    filtered: List[Tuple[int, int]] = []
    start_idx = 0
    if start_filter is not None:
        start_idx = bisect.bisect_left([i[1] for i in intervals], start_filter)

    for i in range(start_idx, len(intervals)):
        start, end = intervals[i]
        if end_filter is not None and start > end_filter:
            break
        filtered.append((start, end))

    return filtered


def get_top_pages(trace: TraceData, n: int = 10) -> List[Tuple[str, int]]:
    """
    Return the n most frequently activated pages.

    @param trace the parsed TraceData
    @param n maximum number of (page, count) entries to return
    @return list of (page_name, activation_count) sorted by count desc
    """
    counts = Counter({page: len(intervals) for page, intervals in trace.page_intervals.items()})
    return counts.most_common(n)


def get_timeline_by_time(trace: TraceData, start_t: int, end_t: int) -> List[Tuple[int, str]]:
    """
    Return access_history entries whose timestamp lies in [start_t, end_t].

    Uses bisect over the pre-extracted timestamp list for O(log n) slicing.

    @param trace the parsed TraceData
    @param start_t inclusive lower bound on timestamp
    @param end_t inclusive upper bound on timestamp
    @return list of (t, page) rising-edge events in chronological order
    """
    times = [item[0] for item in trace.access_history]

    start_idx = bisect.bisect_left(times, start_t)
    end_idx = bisect.bisect_right(times, end_t)

    return trace.access_history[start_idx:end_idx]


def get_access_trace_slice(trace: TraceData, start_idx: int, end_idx: int) -> List[Tuple[int, str]]:
    """
    Return a slice of access_history by index instead of by timestamp.

    Indices are clamped into [0, len(access_history)].

    @param trace the parsed TraceData
    @param start_idx inclusive lower bound on history index
    @param end_idx exclusive upper bound on history index
    @return list of (t, page) entries; empty if the range is invalid
    """
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

    @param trace the parsed TraceData
    @param page the source page name (normalized internally)
    @return mapping next_page -> list of timestamps at which the
            transition occurred; empty when no transitions are recorded
    """
    target = normalize_page_name(page, trace.page_intervals)
    return trace.transition_map.get(target, {})