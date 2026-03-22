from __future__ import annotations

from typing import Dict, List, Tuple

from .model import TraceData


PAGE_PREFIX = "_"


def is_page_signal(sig: str) -> bool:
    """
    Recognize page signals.
    Current heuristic:
    - names starting with "_"
    - pure numeric names
    """
    return sig.startswith(PAGE_PREFIX) or sig.isdigit()


def normalize_page_name(page: str, available_pages: Dict[str, object] | None = None) -> str:
    """
    Normalize a user-provided page name.
    If '7' is given and '_7' exists, return '_7'.
    """
    if available_pages is None:
        return page

    if page in available_pages:
        return page

    prefixed = PAGE_PREFIX + page
    if prefixed in available_pages:
        return prefixed

    return page


def load_vcd_trace(path: str) -> TraceData:
    """
    Load a VCD trace and convert it into trace data structures.

    Returns:
        TraceData:
            - events: per timestamp, only changed signals
            - times: sorted timestamps
            - page_intervals: activation intervals per page
            - access_history: chronological page activations
    """
    id2name: Dict[str, str] = {}
    time_map: Dict[int, Dict[str, str]] = {}

    page_intervals: Dict[str, List[Tuple[int, int]]] = {}
    active_starts: Dict[str, int] = {}
    access_history: List[Tuple[int, str]] = []

    in_header = True
    current_time = 0

    with open(path, "r", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            if in_header:
                if line.startswith("$var"):
                    parts = line.split()
                    if len(parts) >= 5:
                        code = parts[3]
                        name = parts[4]
                        id2name[code] = name
                    continue

                if line.startswith("$enddefinitions"):
                    in_header = False
                    continue

                continue

            if line.startswith("#"):
                try:
                    current_time = int(line[1:])
                except ValueError:
                    continue

                if current_time not in time_map:
                    time_map[current_time] = {}
                continue

            if line[0] in ("0", "1", "x", "z", "X", "Z"):
                val = line[0].lower()
                code = line[1:].strip()
            elif line[0] in ("b", "B"):
                parts = line.split()
                if len(parts) != 2:
                    continue
                val = parts[0][1:].lower()
                code = parts[1]
            else:
                continue

            name = id2name.get(code)
            if name is None:
                continue

            if current_time not in time_map:
                time_map[current_time] = {}

            time_map[current_time][name] = val

            if is_page_signal(name):
                if val == "1":
                    if name not in active_starts:
                        active_starts[name] = current_time
                        access_history.append((current_time, name))
                elif val in ("0", "x", "z"):
                    if name in active_starts:
                        start_t = active_starts.pop(name)
                        page_intervals.setdefault(name, []).append((start_t, current_time))

    for name, start_t in active_starts.items():
        page_intervals.setdefault(name, []).append((start_t, current_time))

    times_sorted = sorted(time_map.keys())
    events = [time_map[t] for t in times_sorted]

    return TraceData(
        events=events,
        times=times_sorted,
        page_intervals=page_intervals,
        access_history=access_history,
    )