from __future__ import annotations

"""Minimal RSA attack example built on top of :class:`sgxtrace.AttackRunner`.

Compared to ``rsa_attack_clean.py``, this version intentionally stays compact,
but it still uses the same helper functions and output format so that the two
examples remain easy to compare.
"""

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
