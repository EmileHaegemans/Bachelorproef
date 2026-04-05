from sgxtrace import load_vcd_trace, AttackRunner

TRACE = "traces/trace_rsa.vcd"

# Define the interesting pages for RSA Montgomery multiplication
MODPOW_PAGE = "_17"  # The main modular exponentiation function
SQUARE_PAGE = "_20"  # Square operation (A)
MULTIPLY_PAGE = "_22"  # Multiply operation (B)
END_PAGE = "_31"  # End of operation marker

def run_clean_rsa_attack():
    """
    Clean RSA attack using AttackRunner with declarative callbacks.
    This demonstrates the TA's suggested approach.
    """
    trace = load_vcd_trace(TRACE)
    print(f"Loaded trace with {len(trace.times)} timestamps")

    runner = AttackRunner(trace)
    runner.verbose = False  # Set to True for debugging

    # State for reconstructing the key
    runner.state["current_symbols"] = []
    runner.state["reconstructed_bits"] = []

    def on_square_operation(runner):
        """Called when square operation is detected (modpow -> square)"""
        runner.state["current_symbols"].append("A")  # Square

    def on_multiply_operation(runner):
        """Called when multiply operation is detected (modpow -> multiply)"""
        runner.state["current_symbols"].append("B")  # Multiply

    def on_modpow_start(runner):
        """Called when modpow operation starts - this is the initial square"""
        if not runner.state["current_symbols"]:  # Only add if this is the start
            runner.state["current_symbols"].append("S")  # Initial square

    def on_operation_end(runner):
        """Called when an RSA operation completes"""
        symbols = "".join(runner.state["current_symbols"])

        if symbols:
            # Decode the Montgomery ladder pattern
            bits = decode_montgomery_ladder(symbols)
            if bits:
                runner.state["reconstructed_bits"].append(bits)

        # Reset for next operation
        runner.state["current_symbols"] = []

    # Register callbacks for state transitions
    runner.on_page(MODPOW_PAGE, on_modpow_start)
    runner.on_transition(MODPOW_PAGE, SQUARE_PAGE, on_square_operation)
    runner.on_transition(MODPOW_PAGE, MULTIPLY_PAGE, on_multiply_operation)
    runner.on_page(END_PAGE, on_operation_end)

    print("Running RSA attack with AttackRunner...")
    runner.run()

    # Output results
    print(f"\nReconstructed {len(runner.state['reconstructed_bits'])} key bits:")
    for i, bits in enumerate(runner.state["reconstructed_bits"]):
        value = int(bits, 2)
        print(f"[{i}] bits='{bits}' value={value}")

    # For RSA, typically the first two values are e and d
    if len(runner.state["reconstructed_bits"]) >= 2:
        e_bits, d_bits = runner.state["reconstructed_bits"][:2]
        e = int(e_bits, 2)
        d = int(d_bits, 2)
        print(f"\nRSA parameters: e={e}, d={d}")

def decode_montgomery_ladder(symbols: str) -> str | None:
    """
    Decode Montgomery ladder pattern from symbols.
    A = Square, B = Multiply
    Based on the original example_attack.py logic
    """
    if not symbols:
        return None

    # Strip leading A's and decode
    tail = symbols.lstrip("A")
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
    return bitstring if bitstring else None

if __name__ == "__main__":
    run_clean_rsa_attack()