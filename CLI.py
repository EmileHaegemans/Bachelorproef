from __future__ import annotations

from typing import Dict, List, Set, Tuple
from collections import Counter

from vcdvcd import VCDVCD


PAGE_PREFIX = "_"

def is_page_signal(sig: str) -> bool:
    # Recognizes both _0 and pure numbers (as in libjpeg trace)
    return sig.startswith(PAGE_PREFIX) or sig.isdigit()


def print_help() -> None:
    print(
        """
Available commands:
    help
    quit
    load-trace <path>
    step [n]            # go forward n steps (default 1)
    page-step           # jump to next moment pages change
    active-pages        # show current active pages
    frequency <page>    # show when and how long a page was accessed
    timeline <start_t> <end_t> # show chronological order based on time (t)
    acces-trace <s_idx> <e_idx> # show chronological order based on index
    transitions <page>  # show pages following the specified page (with timestamps)
    top-pages <amount>  # show the most accessed pages and their counts
    breakpoints         # list all breakpoints
    break-page <name>   # set breakpoint for page activation
    unbreak-page <name> # remove page breakpoint
"""
    )


def load_vcd_trace(path: str) -> Tuple[List[Dict[str, str]], List[int], Dict[str, List[Tuple[int, int]]], List[Tuple[int, str]]]:
    id2name: Dict[str, str] = {}
    time_map: Dict[int, Dict[str, str]] = {}

    page_intervals: Dict[str, List[Tuple[int, int]]] = {}
    active_starts: Dict[str, int] = {}
    access_history: List[Tuple[int, str]] = []

    in_header = True
    current_time = 0

    print(f"Loading {path}...")
    with open(path, "r", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            # Header
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

            # Data
            if line.startswith("#"):
                current_time = int(line[1:])
                if current_time not in time_map:
                    time_map[current_time] = {}
                continue

            # Value changes
            if line[0] in ("0", "1", "x", "z", "X", "Z"):
                val = line[0].lower()
                code = line[1:].strip()
            elif line[0] in ("b", "B"):
                parts = line.split()
                if len(parts) != 2:
                    continue
                val = parts[0][1:]  
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
                        if name not in page_intervals:
                            page_intervals[name] = []
                        page_intervals[name].append((start_t, current_time))

    # Close open intervals at the end
    for name, start_t in active_starts.items():
        if name not in page_intervals:
            page_intervals[name] = []
        page_intervals[name].append((start_t, current_time))

    times_sorted = sorted(time_map.keys())
    events = [time_map[t] for t in times_sorted]

    return events, times_sorted, page_intervals, access_history



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


def do_single_step(state: dict, count: int = 1, quiet: bool = False) -> None:
    trace: List[Dict[str, str]] = state["trace"]
    times: List[int] = state["times"]

    if not trace:
        if not quiet:
            print("no trace loaded")
        return

    steps_done = 0

    for _ in range(count):
        idx = state["trace_index"]
        if idx + 1 >= len(trace):
            break

        idx += 1
        state["trace_index"] = idx
        steps_done += 1

        changes = trace[idx]
        t = times[idx]

        added, removed = _apply_changes(
            state["current_values"],
            state["active_pages"],
            changes,
        )

        # registers
        state["registers"]["step"] = idx
        state["registers"]["time"] = t
        state["registers"]["pages"] = set(state["active_pages"])
        state["last_diff"] = (added, removed)

        # breakpoints check
        for page in added:
            if page in state["page_breakpoints"]:
                print(f"breakpoint hit: page {page} activated at step {idx}")
                return

    if steps_done == 0:
        if not quiet:
            print("end of trace")
        return
    
    if quiet:
        return

    plural = "step" if steps_done == 1 else "steps"
    t_now = state["registers"].get("time")
    active_n = len(state["active_pages"])
    print(f"performed {steps_done} {plural}")
    print(f"step {state['trace_index']} (of {len(trace) - 1}) | t={t_now} | active_pages={active_n}")

    added, removed = state.get("last_diff", (set(), set()))
    if added or removed:
        if added:
            shown = sorted(added)
            print("+", " ".join(shown))
        if removed:
            shown = sorted(removed)
            print("-", " ".join(shown))

def page_step_command(state: dict) -> None:
    if not state["trace"]:
        print("no trace loaded")
        return

    while True:
        before_idx = state["trace_index"]
        do_single_step(state, 1, quiet=True)

        # end of trace?
        if state["trace_index"] == before_idx:
            print("end of trace")
            return

        added, removed = state.get("last_diff", (set(), set()))
        if added or removed:
            trace = state["trace"]
            t_now = state["registers"].get("time")
            active_n = len(state["active_pages"])

            print("performed 1 page-step")
            print(
                f"step {state['trace_index']} (of {len(trace) - 1}) | "
                f"t={t_now} | active_pages={active_n}"
            )

            if added:
                shown = sorted(added)
                print("+", " ".join(shown))
            if removed:
                shown = sorted(removed)
                print("-", " ".join(shown))

            return


def break_page_command(page: str, state: dict) -> None:
    state["page_breakpoints"].add(page)
    print(f"breakpoint set for page {page}")


def unbreak_page_command(page: str, state: dict) -> None:
    if page in state["page_breakpoints"]:
        state["page_breakpoints"].remove(page)
        print(f"removed breakpoint for page {page}")
    else:
        print(f"no breakpoint for page {page}")


def show_breakpoints(state: dict) -> None:
    pages = state.get("page_breakpoints", set())
    if not pages:
        print("no page breakpoints")
    else:
        print("page breakpoints:", ", ".join(sorted(pages)))


def active_pages_command(state: dict) -> None:
    regs = state.get("registers", {})
    step = regs.get("step")
    t = regs.get("time")
    pages: Set[str] = regs.get("pages", set())
    print("step:", step, "| time:", t)
    print("active_pages_count:", len(pages))
    pages_sorted = sorted(pages)
    print("active_pages:", pages_sorted)

def freq_command(page: str, state: dict, start_filter: int = None, end_filter: int = None):
    mapping = state.get("page_intervals", {})

    target = page
    if target not in mapping and ("_" + target) in mapping:
        target = "_" + target

    if target in mapping:
        intervals = mapping[target]

        # Filter based on start time
        filtered = []
        for start, end in intervals:
            if start_filter is not None and start < start_filter:
                continue
            if end_filter is not None and start > end_filter:
                continue
            filtered.append((start, end))

        print(f"--- Access intervals for Page {target} ---")
        if start_filter is not None or end_filter is not None:
            print(f"Filter: accesses starting between {start_filter if start_filter is not None else 0} and {end_filter if end_filter is not None else 'end'}")

        print(f"Activations found: {len(filtered)}")

        for start, end in filtered:
            print(f"  {start:8} - {end:8} (duration: {end-start})")
    else:
        print(f"Page {target} not found in trace or never activated (1).")


def top_pages_command(n: int, state: dict):
    mapping = state.get("page_intervals", {})
    counts = Counter({p: len(t) for p, t in mapping.items()})

    print(f"Top {n} most activated pages:")
    for page, count in counts.most_common(n):
        print(f" page {page:10} : {count} accesses")


def timeline_time_command(state: dict, start_t: int, end_t: int):
    history = state.get("access_history", [])
    if not history:
        print("No access history available. Load a trace first.")
        return

    print(f"--- Timeline (time {start_t} to {end_t}) ---")
    found_any = False
    for i, (t, page) in enumerate(history):
        if t >= start_t and t <= end_t:
            print(f"[{i}] t={t} : {page}")
            found_any = True
        elif t > end_t:
            break

    if not found_any:
        print(f"No page accesses found between t={start_t} and t={end_t}.")


def acces_trace_command(state: dict, start_idx: int, end_idx: int):
    history = state.get("access_history", [])
    if not history:
        print("No access history available. Load a trace first.")
        return

    start_idx = max(0, start_idx)
    end_idx = min(len(history), end_idx)

    print(f"--- Access Trace (index {start_idx} to {end_idx}) ---")
    for i in range(start_idx, end_idx):
        t, page = history[i]
        print(f"[{i}] t={t} : {page}")


def transitions_command(page: str, state: dict):
    history = state.get("access_history", [])
    if not history:
        print("No access history available. Load a trace first.")
        return

    target = page
    if target not in state.get("page_intervals", {}) and ("_" + target) in state.get("page_intervals", {}):
        target = "_" + target

    transitions = {} # Dict[str, List[int]]
    
    for i in range(len(history) - 1):
        t_current, p_current = history[i]
        if p_current == target:
            p_next = history[i+1][1]
            if p_next not in transitions:
                transitions[p_next] = []
            transitions[p_next].append(t_current)

    if not transitions:
        print(f"No transitions found for page {target}.")
        return

    total_occurrences = sum(len(ts) for ts in transitions.values())

    print(f"--- Analysis of Transitions after Page {target} ---")
    print(f"Total times activated: {total_occurrences}\n")

    sorted_transitions = sorted(transitions.items(), key=lambda x: len(x[1]), reverse=True)

    for next_p, timestamps in sorted_transitions:
        count = len(timestamps)
        percentage = (count / total_occurrences) * 100
        print(f"  -> Followed by {next_p:10} : {count:5} times ({percentage:5.1f}%)")
        print(f"     At timestamps: {timestamps}")
        print("") 


def interpret_command(command: str, state: dict) -> None:
    parts = command.split()
    if not parts:
        return

    cmd = parts[0]

    if cmd == "load-trace":
        if len(parts) < 2:
            print("usage: load-trace <path>")
            return

        events, times, pageInt, hist = load_vcd_trace(parts[1])
        state["trace"] = events
        state["times"] = times
        state["trace_index"] = -1
        state["page_intervals"] = pageInt
        state["access_history"] = hist

        # reset
        state["current_values"] = {}
        state["active_pages"] = set()
        state["last_diff"] = (set(), set())
        state["registers"]["step"] = None
        state["registers"]["time"] = None
        state["registers"]["pages"] = set()

        print(f"Loaded trace with {len(events)} timestamps.")
        return

    if cmd == "quit":
        raise SystemExit(0)

    if cmd == "help":
        print_help()
        return

    if cmd == "page-step":
        page_step_command(state)
        return

    if cmd == "step":
        count = 1
        if len(parts) == 2:
            try:
                count = int(parts[1])
            except ValueError:
                print("step: argument must be an integer")
                return
        do_single_step(state, count)
        return

    if cmd == "break-page":
        if len(parts) != 2:
            print("usage: break-page <page_name>")
            return
        break_page_command(parts[1], state)
        return

    if cmd == "unbreak-page":
        if len(parts) != 2:
            print("usage: unbreak-page <page_name>")
            return
        unbreak_page_command(parts[1], state)
        return

    if cmd == "breakpoints":
        show_breakpoints(state)
        return

    if cmd == "active-pages":
        active_pages_command(state)
        return
    
    if cmd == "frequency":
        if len(parts) < 2:
            print("usage: frequency <page_name> [start_time] [end_time]")
            return
        
        page_name = parts[1]
        start_t = None
        end_t = None
        
        try:
            if len(parts) > 2:
                start_t = int(parts[2])
            if len(parts) > 3:
                end_t = int(parts[3])
            
            freq_command(page_name, state, start_t, end_t)
        except ValueError:
            print("Error: start_time and end_time must be integers.")
        return

    if cmd == "timeline":
        if len(parts) != 3:
            print("usage: timeline <start_time> <end_time>")
            return
        try:
            t1 = int(parts[1])
            t2 = int(parts[2])
            timeline_time_command(state, t1, t2)
        except ValueError:
            print("Error: timestamps must be integers.")
        return

    if cmd == "acces-trace":
        if len(parts) != 3:
            print("usage: acces-trace <start_index> <end_index>")
            return
        try:
            s_idx = int(parts[1])
            e_idx = int(parts[2])
            acces_trace_command(state, s_idx, e_idx)
        except ValueError:
            print("Error: indices must be integers.")
        return

    if cmd == "transitions":
        if len(parts) != 2:
            print("usage: transitions <page_name>")
            return
        transitions_command(parts[1], state)
        return
    
    if cmd == "top-pages":
        if len(parts) != 2:
            print("usage: top-pages <amount>")
            return
        try:
            n = int(parts[1])
            top_pages_command(n, state)
        except ValueError:
            print("amount must be a number")
        return

    print("no valid command (type 'help')")


def main() -> None:
    print("-- PYTHON CLI STEPPER --")
    print("Type 'help' for commands.\n")

    state = {
        "trace": [],
        "times": [],
        "trace_index": -1,
        "page_breakpoints": set(),
        "current_values": {},  
        "active_pages": set(),  
        "last_diff": (set(), set()),  #(add, rem)
        "registers": {"step": None, "time": None, "pages": set()},
    }

    while True:
        command = input("cli> ")
        interpret_command(command, state)


if __name__ == "__main__":
    main()
