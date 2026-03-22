from __future__ import annotations

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
    filtered: List[Tuple[int, int]] = []

    for start, end in intervals:
        if start_filter is not None and end < start_filter:
            continue
        if end_filter is not None and start > end_filter:
            continue
        filtered.append((start, end))

    return filtered


def get_top_pages(trace: TraceData, n: int = 10) -> List[Tuple[str, int]]:
    counts = Counter({page: len(intervals) for page, intervals in trace.page_intervals.items()})
    return counts.most_common(n)


def get_timeline_by_time(trace: TraceData, start_t: int, end_t: int) -> List[Tuple[int, str]]:
    results: List[Tuple[int, str]] = []

    for t, page in trace.access_history:
        if start_t <= t <= end_t:
            results.append((t, page))
        elif t > end_t:
            break

    return results


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

    The returned dictionary maps each following page to the timestamps at which
    the given page occurred before that transition.
    """
    target = normalize_page_name(page, trace.page_intervals)
    transitions: Dict[str, List[int]] = {}

    history = trace.access_history
    for i in range(len(history) - 1):
        t_current, p_current = history[i]
        if p_current == target:
            p_next = history[i + 1][1]
            transitions.setdefault(p_next, []).append(t_current)

    return transitions