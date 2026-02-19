from __future__ import annotations

from typing import Dict, List, Set, Tuple
from vcdvcd import VCDVCD


# In jouw trace heten pages "_0", "_1", ...  (zoals in GTKWave screenshot / vcd)
# Zet PAGE_PREFIX = "" als je ALLE signalen wil behandelen als "pages".
PAGE_PREFIX = "_"


def is_page_signal(sig: str) -> bool:
    return sig.startswith(PAGE_PREFIX) if PAGE_PREFIX else True


def print_help() -> None:
    print(
        """
Available commands:
  help
  quit
  load-trace <path>
  step [n]            # ga n stappen vooruit (default 1); update actieve pages + toon diff
  page-step           # spring naar volgende moment dat pages veranderen (aan/uit)
  break <i>           # breakpoint op step index
  unbreak <i>         # verwijder breakpoint
  breakpoints         # lijst breakpoints
  registers           # toon huidige registers (step + actieve pages)
"""
    )


def load_vcd_trace(path: str) -> Tuple[List[Dict[str, str]], List[int]]:
    """
    Parse VCD inclusief init-blok (value changes vóór de eerste #timestamp).
    Returns:
      - events: list per timestamp met alleen de changes {sig: val}
      - times:  list van timestamps (zelfde index als events)
    """
    id2name: Dict[str, str] = {}
    time_map: Dict[int, Dict[str, str]] = {}

    in_header = True
    current_time = 0
    time_map[current_time] = {}

    with open(path, "r", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            # Header: definities lezen
            if in_header:
                if line.startswith("$var"):
                    # $var wire 1 ! _0 $end
                    parts = line.split()
                    if len(parts) >= 5:
                        code = parts[3]
                        name = parts[4]
                        id2name[code] = name
                    continue

                if line.startswith("$enddefinitions"):
                    in_header = False
                    continue

                continue  # andere headerlijnen negeren

            # Data: timestamps
            if line.startswith("#"):
                current_time = int(line[1:])
                if current_time not in time_map:
                    time_map[current_time] = {}
                continue

            # Ignore $dumpvars/$end etc.
            if line.startswith("$"):
                continue

            # Value changes:
            # 1-bit: 1! 0xK z" etc.
            # vector: b1010 <code>
            if line[0] in ("0", "1", "x", "z", "X", "Z"):
                val = line[0].lower()
                code = line[1:].strip()
            elif line[0] in ("b", "B"):
                # b101010 !  (of: b101010 <code>)
                parts = line.split()
                if len(parts) != 2:
                    continue
                val = parts[0][1:]  # alleen bits
                code = parts[1]
            else:
                continue

            name = id2name.get(code)
            if name is None:
                continue

            time_map[current_time][name] = val

    times_sorted = sorted(time_map.keys())
    events = [time_map[t] for t in times_sorted]
    return events, times_sorted



def _apply_changes(
    current_values: Dict[str, str],
    active_pages: Set[str],
    changes: Dict[str, str],
) -> Tuple[Set[str], Set[str]]:
    """
    Past changes toe op current_values en active_pages.
    Geeft (added_pages, removed_pages) terug.
    """
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


def do_single_step(state: dict, count: int = 1) -> None:
    trace: List[Dict[str, str]] = state["trace"]
    times: List[int] = state["times"]

    if not trace:
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

        # "registers" = snapshot van actieve pages op dit moment
        state["registers"]["step"] = idx
        state["registers"]["time"] = t
        state["registers"]["pages"] = set(state["active_pages"])
        state["last_diff"] = (added, removed)

        # stop op breakpoint
        if idx in state["breakpoints"]:
            print(f"breakpoint hit at step {idx}")
            break

    if steps_done == 0:
        print("end of trace")
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
            print("+", " ".join(shown[:50]), ("..." if len(shown) > 50 else ""))
        if removed:
            shown = sorted(removed)
            print("-", " ".join(shown[:50]), ("..." if len(shown) > 50 else ""))


def page_step_command(state: dict) -> None:
    """
    Spring naar het volgende moment waarop pages veranderen.
    """
    if not state["trace"]:
        print("no trace loaded")
        return

    while True:
        before_idx = state["trace_index"]
        do_single_step(state, 1)

        # end of trace?
        if state["trace_index"] == before_idx:
            return

        added, removed = state.get("last_diff", (set(), set()))
        if added or removed:
            return


def break_command(step: str, state: dict) -> None:
    try:
        i = int(step)
        state["breakpoints"].add(i)
        print(f"breakpoint set at step {i}")
    except ValueError:
        print("break: step must be an integer")


def unbreak_command(step: str, state: dict) -> None:
    try:
        i = int(step)
        if i in state["breakpoints"]:
            state["breakpoints"].remove(i)
            print(f"removed breakpoint {i}")
        else:
            print("no such breakpoint")
    except ValueError:
        print("unbreak: step must be an integer")


def show_breakpoints(state: dict) -> None:
    if not state["breakpoints"]:
        print("no breakpoints")
    else:
        print("breakpoints:", ", ".join(str(x) for x in sorted(state["breakpoints"])))


def registers_command(state: dict) -> None:
    regs = state.get("registers", {})
    step = regs.get("step")
    t = regs.get("time")
    pages: Set[str] = regs.get("pages", set())
    print("step:", step, "| time:", t)
    print("active_pages_count:", len(pages))
    pages_sorted = sorted(pages)
    print("active_pages:", pages_sorted[:100], ("..." if len(pages_sorted) > 100 else ""))


def interpret_command(command: str, state: dict) -> None:
    parts = command.split()
    if not parts:
        return

    cmd = parts[0]

    if cmd == "load-trace":
        if len(parts) < 2:
            print("usage: load-trace <path>")
            return

        events, times = load_vcd_trace(parts[1])
        state["trace"] = events
        state["times"] = times
        state["trace_index"] = -1

        # reset running state
        state["current_values"] = {}
        state["active_pages"] = set()
        state["last_diff"] = (set(), set())
        state["registers"]["step"] = None
        state["registers"]["time"] = None
        state["registers"]["pages"] = set()

        print(f"Loaded trace with {len(events)} timestamps.")
        print("Tip: 'step 1' applies first timestamp; 'page-step' jumps between page changes.")
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

    if cmd == "break":
        if len(parts) != 2:
            print("usage: break <step_index>")
            return
        break_command(parts[1], state)
        return

    if cmd == "unbreak":
        if len(parts) != 2:
            print("usage: unbreak <step_index>")
            return
        unbreak_command(parts[1], state)
        return

    if cmd == "breakpoints":
        show_breakpoints(state)
        return

    if cmd == "registers":
        registers_command(state)
        return

    print("no valid command (type 'help')")


def main() -> None:
    print("-- PYTHON CLI STEPPER --")
    print("Type 'help' for commands.\n")

    state = {
        "trace": [],
        "times": [],
        "trace_index": -1,
        "breakpoints": set(),
        # running state:
        "current_values": {},  # sig -> last value
        "active_pages": set(),  # pages that are '1' NOW
        "last_diff": (set(), set()),  # (added, removed)
        "registers": {"step": None, "time": None, "pages": set()},
    }

    while True:
        command = input("cli> ")
        interpret_command(command, state)


if __name__ == "__main__":
    main()
