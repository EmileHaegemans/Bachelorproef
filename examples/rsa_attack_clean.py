from __future__ import annotations

"""Clean RSA page-trace attack example.

This script reconstructs RSA exponent bitstrings from a VCD page-access trace.
It uses :class:`sgxtrace.AttackRunner` to declaratively react to a small set of
interesting page transitions:

- ``modpow -> square``   emits symbol ``A``
- ``modpow -> multiply`` emits symbol ``B``
- ``rsa_n``             terminates one exponent reconstruction

The symbol stream is then decoded with the Montgomery-ladder heuristic that was
already used in the earlier prototype scripts.
"""

from sgxtrace import AttackRunner, load_vcd_trace

TRACE_PATH = "traces/trace_rsa.vcd"

# Hardcoded page mapping for the provided RSA demo trace.
MODPOW_PAGE = "_17"
SQUARE_PAGE = "_20"
MULTIPLY_PAGE = "_22"
END_PAGE = "_31"


def decode_montgomery_ladder(symbols: str) -> str | None:
    """Decode a Montgomery-ladder symbol sequence into a bitstring.

    The decoding rule matches the logic from the earlier attack prototype:

    - leading ``A`` symbols are ignored
    - ``B`` decodes to bit ``1``
    - ``AA`` decodes to bit ``0``

    Args:
        symbols: Sequence of ``A`` and ``B`` symbols extracted from the trace.

    Returns:
        The reconstructed bitstring, or ``None`` when no valid bits were found.
    """
    if not symbols:
        return None

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
    return bitstring or None


def run_clean_rsa_attack(trace_path: str = TRACE_PATH, *, verbose: bool = False) -> list[tuple[str, int]]:
    """Run the RSA reconstruction attack on a VCD trace.

    Args:
        trace_path: Path to the RSA VCD trace.
        verbose: Whether to enable verbose navigator/debug output.

    Returns:
        A list of ``(bitstring, integer_value)`` tuples for each decoded segment.
    """
    trace = load_vcd_trace(trace_path)
    print(f"Loaded trace with {len(trace.times)} timestamps and {len(trace.access_history)} page activations.")

    runner = AttackRunner(trace)
    runner.verbose = verbose
    runner.state["current_symbols"] = []
    runner.state["decoded_segments"] = []

    def on_modpow_start(r: AttackRunner) -> None:
        """Mark the start of a new modular exponentiation segment."""
        if not r.state["current_symbols"]:
            r.state["current_symbols"].append("S")

    def on_square_operation(r: AttackRunner) -> None:
        """Record a square step as symbol ``A``."""
        r.state["current_symbols"].append("A")

    def on_multiply_operation(r: AttackRunner) -> None:
        """Record a multiply step as symbol ``B``."""
        r.state["current_symbols"].append("B")

    def on_operation_end(r: AttackRunner) -> None:
        """Decode and store one completed RSA operation."""
        symbols = "".join(r.state["current_symbols"])
        bitstring = decode_montgomery_ladder(symbols)

        if bitstring is not None:
            r.state["decoded_segments"].append((bitstring, int(bitstring, 2)))

        r.state["current_symbols"] = []

    runner.on_page(MODPOW_PAGE, on_modpow_start)
    runner.on_transition(MODPOW_PAGE, SQUARE_PAGE, on_square_operation)
    runner.on_transition(MODPOW_PAGE, MULTIPLY_PAGE, on_multiply_operation)
    runner.on_page(END_PAGE, on_operation_end)

    print("Running RSA attack with AttackRunner...")
    runner.run()

    decoded_segments: list[tuple[str, int]] = runner.state["decoded_segments"]
    print(f"\nDecoded {len(decoded_segments)} RSA segments:")
    for index, (bits, value) in enumerate(decoded_segments):
        print(f"[{index}] bits={bits!r} value={value}")

    if len(decoded_segments) >= 2:
        public_exponent = decoded_segments[0][1]
        private_exponent = decoded_segments[1][1]
        print(f"\nRecovered RSA parameters:")
        print(f"  e = {public_exponent}")
        print(f"  d = {private_exponent}")

    return decoded_segments


if __name__ == "__main__":
    run_clean_rsa_attack()