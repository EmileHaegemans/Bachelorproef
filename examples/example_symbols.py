from sgxtrace import load_vcd_trace, get_page_intervals, get_timeline_by_time
from sgxtrace.symbols import get_symbol_map, find_page_by_exact_symbol

#setup
TRACE_PATH = "traces/trace_rsa.vcd"
ELF_PATH = "traces/s-encl-rsa.so"

trace = load_vcd_trace(TRACE_PATH)
trace.symbol_map = get_symbol_map(ELF_PATH)

#find pages
anchor_page = find_page_by_exact_symbol(trace, "modpow")
square_page = find_page_by_exact_symbol(trace, "square")
multiply_page = find_page_by_exact_symbol(trace, "multiply")
end_page = find_page_by_exact_symbol(trace, "rsa_n")

print(f"Discovered pages:")
print(f"  ANCHOR (modpow):   {anchor_page}")
print(f"  SQUARE (A):        {square_page}")
print(f"  MULTIPLY (B):      {multiply_page}")
print(f"  END (data):        {end_page}\n")

PAGES = {anchor_page, square_page, multiply_page, end_page}

def to_symbols(events):
    seq = [p for _, p in events if p in PAGES]
    out = []
    for p1, p2 in zip(seq, seq[1:]):
        if p1 == anchor_page and p2 == square_page:
            out.append("A")
        elif p1 == anchor_page and p2 == multiply_page:
            out.append("B")
        elif p1 == anchor_page and p2 == end_page:
            break
    return "".join(out)

def decode(sym):
    tail = sym.lstrip("A")
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
    return bitstring, int(bitstring, 2) if bitstring else None


cuts = [start for start, _ in get_page_intervals(trace, end_page, start_filter=1)]
decoded = []
start = 1
for stop in cuts:
    timeline = get_timeline_by_time(trace, start, stop)
    sym = to_symbols(timeline)
    bits, value = decode(sym)
    if value is not None:
        decoded.append((sym, bits, value))
    start = stop + 1

for i, (sym, bits, value) in enumerate(decoded):
    print(f"[{i}] symbols={sym[:40]}... bits={bits} value={value}")

if len(decoded) >= 2:
    print(f"\nRecovered Public Exponent (e):  {decoded[0][2]}")
    print(f"Recovered Private Exponent (d): {decoded[1][2]}")
