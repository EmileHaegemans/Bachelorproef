from vcdvcd import VCDVCD

def print_help():
    print("""
Available commands:
  help
  quit
  load-trace path
  page-step          # do a page step
  step <optional: amount of steps>    # do 1 step or a given amount of 
  break <step>       # set breakpoint on a step index
  unbreak <step>     # remove breakpoint
  breakpoints        # list breakpoints
  registers          # show current 'registers'
""")

def do_single_step(state, count=1):
    trace = state["trace"]

    if not trace:
        print("no trace loaded")
        return

    steps_done = 0

    for _ in range(count):
        idx = state["trace_index"]

        if idx + 1 >= len(trace):
            break  # end of trace

        # advance
        idx += 1
        state["trace_index"] = idx
        steps_done += 1

        # update registers
        event = trace[idx]
        accessed_pages = {sig for sig, val in event.items() if val == "1"}
        state["registers"]["step"] = idx
        state["registers"]["pages"] = accessed_pages

        # stop if breakpoint hit
        if idx in state["breakpoints"]:
            print(f"breakpoint hit at step {idx}")
            break

    # ---- summary printed ONLY ONCE ----
    if steps_done > 0:
        plural = "step" if steps_done == 1 else "steps"
        print(f"performed {steps_done} {plural}")
        print(f"step {state['trace_index']} (of {len(trace) - 1})")
    else:
        print("end of trace")

def page_step_command(state):
    #TODO implment
    pass 


def break_command(step, state):
    try:
        i = int(step)
        state["breakpoints"].add(i)
        print(f"breakpoint set at step {i}")
    except ValueError:
        print("break: step must be an integer")


def unbreak_command(step, state):
    try:
        i = int(step)
        if i in state["breakpoints"]:
            state["breakpoints"].remove(i)
            print(f"removed breakpoint {i}")
        else:
            print("no such breakpoint")
    except ValueError:
        print("unbreak: step must be an integer")


def show_breakpoints(state):
    if not state["breakpoints"]:
        print("no breakpoints")
    else:
        print("breakpoints:", ", ".join(str(x) for x in sorted(state["breakpoints"])))

def registers_command(state):
    regs = state.get("registers", {})
    step = regs.get("step")
    pages = regs.get("pages", set())

    print("step:", step)
    print("accessed_pages:", sorted(list(pages)))


def interpret_command(command, state):
    parts = command.split()
    if not parts:
        return
    cmd = parts[0]

    if cmd == "load-trace":
        if len(parts) < 2:
            print("usage: load-trace <path>")
            return
        events = load_vcd_trace(parts[1])
        state["trace"] = events
        state["trace_index"] = -1
        print(f"Loaded trace with {len(events)} timestamps.")

    if cmd == "quit":
        exit(0)

    if cmd == "help":
        print_help()

    if cmd == "page-step":
        page_step_command(state)


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


    if cmd == "break" and len(parts) == 2:
        break_command(parts[1], state)

    if cmd == "unbreak" and len(parts) == 2:
        unbreak_command(parts[1], state)

    if cmd == "breakpoints":
        show_breakpoints(state)

    if cmd == "registers":
        registers_command(state)

    
   
    VALID_COMMANDS = [
        "load-trace", "quit", "help", "page-step", "step",
        "break", "unbreak", "breakpoints", "registers"
    ]

    if cmd not in VALID_COMMANDS:
        print("no valid command")


def load_vcd_trace(path):
    vcd = VCDVCD(path)   # store_tvs=True is default

    # time -> {signal_name: value}
    time_map = {}

    for sig_name, signal in vcd.data.items():
        # signal.tv is een lijst van (time, value)
        for t, val in signal.tv:
            t = int(t)
            if t not in time_map:
                time_map[t] = {}
            time_map[t][sig_name] = val

    # Maak een geordende lijst van "events" per tijd
    events = []
    for t in sorted(time_map.keys()):
        events.append(time_map[t])


    return events




def main():
    print("-- PYTHON CLI STEPPER --")
    print("Type 'help' for commands.\n")

    state = {
        "trace": [],          # uit je VCD
        "trace_index": -1,
        "breakpoints": set(),
        "registers": {
            "step": None,
            "pages": set(),   # set van page nummers
            }
        }

    while True:
        command = input("cli> ")
        interpret_command(command, state)


if __name__ == "__main__":
    main()