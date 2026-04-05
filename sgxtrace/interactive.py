from __future__ import annotations

import dataclasses
from typing import Optional

from .analysis import (
    get_access_trace_slice,
    get_page_intervals,
    get_timeline_by_time,
    get_top_pages,
    get_transitions,
)
from .core import TraceNavigator, load_vcd_trace, normalize_page_name
from .symbols import find_pages_for_symbol, get_symbol_map, get_symbols_for_page


def print_help() -> None:
    print(
        """
Available commands:
    help
    quit
    load-trace <path>
    load-binary <path>            # load ELF symbols for page mapping
    show-map                      # print the page-to-symbol mapping
    map-page <page>               # show all functions on a specific page
    map-symbol <name>             # find which page a function belongs to
    step [n]                      # go forward n steps (default 1)
    page-step                     # jump to next moment pages change
    active-pages                  # show current active pages
    frequency <page> [start] [end]
    timeline <start_t> <end_t>    # show chronological order based on time
    access-trace <s_idx> <e_idx>  # show chronological order based on index
    transitions <page>            # show pages following the specified page
    top-pages <amount>            # show the most accessed pages and their counts
    breakpoints                   # list all breakpoints
    break-page <name>             # set breakpoint for page activation
    unbreak-page <name>           # remove page breakpoint
"""
    )


def _print_step_result(
    result,
    nav: TraceNavigator,
    page_step: bool = False,
) -> None:
    total_events = len(nav.trace.events)
    active_pages_count = len(nav.active_pages)

    if result.steps_done == 0:
        if result.end_of_trace:
            print("end of trace")
        else:
            print("no step performed")
        return

    if page_step:
        print("performed 1 page-step")
    else:
        plural = "step" if result.steps_done == 1 else "steps"
        print(f"performed {result.steps_done} {plural}")

    print(
        f"step {result.trace_index} (of {total_events - 1}) | "
        f"t={result.time} | active_pages={active_pages_count}"
    )

    if result.added:
        print("+", " ".join(sorted(result.added)))
    if result.removed:
        print("-", " ".join(sorted(result.removed)))

    if result.breakpoint_hit is not None:
        print(f"breakpoint hit: page {result.breakpoint_hit} activated at step {result.trace_index}")


def _print_active_pages(nav: TraceNavigator) -> None:
    print("step:", nav.current_step, "| time:", nav.current_time)
    pages = sorted(nav.active_pages)
    print("active_pages_count:", len(pages))
    print("active_pages:", pages)


def _print_frequency(page: str, nav: TraceNavigator, start_t: int | None, end_t: int | None) -> None:
    target = normalize_page_name(page, nav.trace.page_intervals)
    intervals = get_page_intervals(nav.trace, target, start_t, end_t)
    print(f"--- Access intervals for Page {target} ---")

    if start_t is not None or end_t is not None:
        print(
            f"Filter: accesses starting between "
            f"{start_t if start_t is not None else 0} and "
            f"{end_t if end_t is not None else 'end'}"
        )

    print(f"Activations found: {len(intervals)}")
    for start, end in intervals:
        print(f"  {start:8} - {end:8} (duration: {end - start})")

    if not intervals:
        print("No matching activations found.")


def _print_timeline(nav: TraceNavigator, start_t: int, end_t: int) -> None:
    rows = get_timeline_by_time(nav.trace, start_t, end_t)
    print(f"--- Timeline (time {start_t} to {end_t}) ---")
    if not rows:
        print(f"No page accesses found between t={start_t} and t={end_t}.")
        return

    for i, (t, page) in enumerate(rows):
        print(f"[{i}] t={t} : {page}")


def _print_access_trace(nav: TraceNavigator, start_idx: int, end_idx: int) -> None:
    rows = get_access_trace_slice(nav.trace, start_idx, end_idx)
    print(f"--- Access Trace (index {start_idx} to {end_idx}) ---")
    if not rows:
        print("No access history available in the requested range.")
        return

    base_index = max(0, start_idx)
    for offset, (t, page) in enumerate(rows):
        print(f"[{base_index + offset}] t={t} : {page}")


def _print_transitions(page: str, nav: TraceNavigator) -> None:
    target = normalize_page_name(page, nav.trace.page_intervals)
    transitions = get_transitions(nav.trace, target)

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


def _print_top_pages(amount: int, nav: TraceNavigator) -> None:
    top = get_top_pages(nav.trace, amount)
    print(f"Top {amount} most activated pages:")
    for page, count in top:
        print(f" page {page:10} : {count} accesses")


def _print_symbol_map(nav: TraceNavigator) -> None:
    if not nav.trace.symbol_map:
        print("No symbol map loaded. Use 'load-binary <path>' first.")
        return

    print("--- Page to Symbol Map ---")

    def page_key(p: str) -> int:
        try:
            return int(p.lstrip("_"), 16)
        except ValueError:
            return 0

    sorted_pages = sorted(nav.trace.symbol_map.keys(), key=page_key)
    for p in sorted_pages:
        symbol = nav.trace.symbol_map[p]
        print(f" {p:10} : {symbol}")
    print("-" * 26)


def interpret_command(command: str, context: dict) -> None:
    parts = command.split()
    if not parts:
        return

    cmd = parts[0]
    nav: Optional[TraceNavigator] = context.get("navigator")

    if cmd == "quit":
        raise SystemExit(0)

    if cmd == "help":
        print_help()
        return

    if cmd == "load-trace":
        if len(parts) < 2:
            print("usage: load-trace <path>")
            return

        path = parts[1]
        print(f"Loading {path}...")

        try:
            trace = load_vcd_trace(path)
        except OSError as e:
            print(f"failed to load trace: {e}")
            return

        nav = TraceNavigator(trace)
        context["navigator"] = nav
        print(f"Loaded trace with {len(trace.events)} timestamps.")
        return

    if nav is None:
        print("no trace loaded")
        return

    if cmd == "load-binary":
        if len(parts) < 2:
            print("usage: load-binary <path>")
            return

        path = parts[1]
        print(f"Loading symbols from {path}...")
        sym_map = get_symbol_map(path)
        if sym_map:
            nav.trace = dataclasses.replace(nav.trace, symbol_map=sym_map)
            print(f"Loaded {len(sym_map)} page mappings.")
        else:
            print("No symbols loaded.")
        return

    if cmd == "show-map":
        _print_symbol_map(nav)
        return

    if cmd == "map-page":
        if len(parts) < 2:
            print("usage: map-page <page_name>")
            return

        page = parts[1]
        if not page.startswith("_"):
            page = "_" + page

        symbols = get_symbols_for_page(nav.trace, page)
        if symbols:
            print(f"Functions on page {page}:")
            for s in symbols:
                print(f"  - {s}")
        else:
            print(f"No functions mapped to page {page}.")
        return

    if cmd == "map-symbol":
        if len(parts) < 2:
            print("usage: map-symbol <keyword>")
            return

        keyword = " ".join(parts[1:])
        results = find_pages_for_symbol(nav.trace, keyword)
        if results:
            print(f"Found {len(results)} matches for '{keyword}':")
            for page, symbol in results:
                print(f"  {page:10} : {symbol}")
        else:
            print(f"No symbols found matching '{keyword}'.")
        return

    if cmd == "step":
        count = 1
        if len(parts) == 2:
            try:
                count = int(parts[1])
            except ValueError:
                print("step: argument must be an integer")
                return

        result = nav.step(count)
        _print_step_result(result, nav, page_step=False)
        return

    if cmd == "page-step":
        result = nav.page_step()
        _print_step_result(result, nav, page_step=True)
        return

    if cmd == "active-pages":
        _print_active_pages(nav)
        return

    if cmd == "break-page":
        if len(parts) != 2:
            print("usage: break-page <page_name>")
            return
        normalized = nav.add_breakpoint(parts[1])
        print(f"breakpoint set for page {normalized}")
        return

    if cmd == "unbreak-page":
        if len(parts) != 2:
            print("usage: unbreak-page <page_name>")
            return

        normalized = normalize_page_name(parts[1], nav.trace.page_intervals)
        removed = nav.remove_breakpoint(parts[1])
        if removed:
            print(f"removed breakpoint for page {normalized}")
        else:
            print(f"no breakpoint for page {normalized}")
        return

    if cmd == "breakpoints":
        pages = nav.list_breakpoints()
        if not pages:
            print("no page breakpoints")
        else:
            print("page breakpoints:", ", ".join(pages))
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
        except ValueError:
            print("Error: start_time and end_time must be integers.")
            return

        _print_frequency(page_name, nav, start_t, end_t)
        return

    if cmd == "timeline":
        if len(parts) != 3:
            print("usage: timeline <start_time> <end_time>")
            return
        try:
            t1 = int(parts[1])
            t2 = int(parts[2])
        except ValueError:
            print("Error: timestamps must be integers.")
            return

        _print_timeline(nav, t1, t2)
        return

    if cmd == "access-trace":
        if len(parts) != 3:
            print("usage: access-trace <start_index> <end_index>")
            return
        try:
            s_idx = int(parts[1])
            e_idx = int(parts[2])
        except ValueError:
            print("Error: indices must be integers.")
            return

        _print_access_trace(nav, s_idx, e_idx)
        return

    if cmd == "transitions":
        if len(parts) != 2:
            print("usage: transitions <page_name>")
            return
        _print_transitions(parts[1], nav)
        return

    if cmd == "top-pages":
        if len(parts) != 2:
            print("usage: top-pages <amount>")
            return
        try:
            n = int(parts[1])
        except ValueError:
            print("amount must be a number")
            return

        _print_top_pages(n, nav)
        return

    print("no valid command (type 'help')")


def main() -> None:
    print("-- PYTHON CLI STEPPER --")
    print("Type 'help' for commands.\n")

    context = {
        "navigator": None,
    }

    while True:
        try:
            command = input("cli> ")
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print("\nInterrupted")
            continue

        interpret_command(command, context)


if __name__ == "__main__":
    main()
