from vcdvcd import VCDVCD

def print_help():
    print("""
Available commands:
  help
  quit
  load-trace path
  page-step          # do a page step
  step               # do 1 step 
  break <step>       # set breakpoint on a step index
  unbreak <step>     # remove breakpoint
  breakpoints        # list breakpoints
  registers          # show current 'registers'
""")


def do_single_step(state):
    trace = state["trace"]
    idx = state["trace_index"]

    if not trace:
        print("no trace loaded")
        return

    if idx + 1 >= len(trace):
        print("end of trace")
        return

    # move one step forward
    idx += 1
    state["trace_index"] = idx

    # update "registers"
    event = trace[idx]  # dictionary {signal : value}
    accessed_pages = {sig for sig, val in event.items() if val == "1"}

    state["registers"]["step"] = idx
    state["registers"]["pages"] = accessed_pages

    # print output
    print(f"step {idx} (of {len(trace) - 1})")

    #breakpoint?
    if idx in state["breakpoints"]:
        print(f" breakpoint hit at step {idx} ")


def page_step_command(state):
    #TODO implment
    pass 


def break_command(step, state):
    #TODO implment
    pass


def unbreak_command(step, state):
   #TODO implment
   pass


def show_breakpoints(state):
    #TODO implement
    pass

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
        do_single_step(state)

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