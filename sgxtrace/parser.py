"""
VCD reader for SGX-Step single-step traces.

Parses a Value Change Dump file produced by SGX-Step and converts it
into a TraceData with several pre-computed indices used by the
navigator and the attack engines.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .model import TraceData


# Prefix used for page signal names in VCD files (e.g. "_17").
PAGE_PREFIX = "_"


def is_page_signal(sig: str) -> bool:
    """
    Recognize page signals.

    Heuristic:
      - names starting with "_" (e.g. "_17")
      - pure numeric names (e.g. "17")

    @param sig the signal name to test
    @return True if the signal represents a memory page
    """
    return sig.startswith(PAGE_PREFIX) or sig.isdigit()


def normalize_page_name(page: str, available_pages: Dict[str, object] | None = None) -> str:
    """
    Normalize a user-supplied page name to its canonical form.

    Returns the input unchanged when it already exists in
    available_pages. Otherwise tries the "_"-prefixed variant; for
    example "7" is rewritten to "_7" when "_7" is the actual key.

    @param page the user-supplied page name
    @param available_pages a mapping whose keys are the canonical
                           page names (typically TraceData.page_intervals)
    @return the canonical page name, or the original input if no
            canonical form can be resolved
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
    Parse a VCD file into a TraceData.

    The file is read in a single pass:
      1. Header phase: $var lines build the VCD-id -> signal-name table.
      2. Event phase: every value change updates the per-timestamp
         events dict and the per-signal change history.
      3. Page signals additionally drive page_intervals (rising edge to
         falling edge) and access_history (rising edges only).
      4. After the pass, transition_map is built by walking
         access_history pairwise.

    @param path filesystem path to a .vcd file
    @return a fully-populated TraceData
    """
    id2name: Dict[str, str] = {}
    time_map: Dict[int, Dict[str, str]] = {}

    page_intervals: Dict[str, List[Tuple[int, int]]] = {}
    active_starts: Dict[str, int] = {}
    access_history: List[Tuple[int, str]] = []
    signal_to_changes: Dict[str, List[Tuple[int, str]]] = {}

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

            signal_to_changes.setdefault(name, []).append((current_time, val))

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

    transition_map: Dict[str, Dict[str, List[int]]] = {}
    for i in range(len(access_history) - 1):
        t_current, p_current = access_history[i]
        p_next = access_history[i + 1][1]

        if p_current not in transition_map:
            transition_map[p_current] = {}
        if p_next not in transition_map[p_current]:
            transition_map[p_current][p_next] = []

        transition_map[p_current][p_next].append(t_current)

    return TraceData(
        events=events,
        times=times_sorted,
        page_intervals=page_intervals,
        access_history=access_history,
        signal_to_changes=signal_to_changes,
        transition_map=transition_map,
    )