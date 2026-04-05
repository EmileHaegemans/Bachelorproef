# Bachelorproef: Interactive Exploitation of Intel SGX Enclaves with SGX-Step

This project provides a Python library for analyzing Intel SGX enclave execution traces captured with SGX-Step. The library enables side-channel attacks to reconstruct sensitive data from page access patterns.

## Features

- **Trace Analysis**: Parse and navigate VCD (Value Change Dump) traces from SGX-Step
- **Symbol Mapping**: Map ELF binary symbols to memory pages for targeted attacks
- **Attack Frameworks**:
  - `AttackRunner`: Declarative framework for building side-channel attacks with callbacks
  - `TraceNavigator`: Efficient trace navigation with breakpoints
- **Built-in Attacks**:
  - RSA key reconstruction from Montgomery multiplication patterns
  - JPEG image reconstruction from decompression access patterns

## Project Structure

```
Bachelorproef/
├── sgxtrace/          # Core library package
│   ├── core.py        # Centralized library exports and shared API
│   ├── interactive.py # Interactive CLI implementation
│   ├── attack.py      # AttackRunner framework
│   ├── navigator.py   # TraceNavigator for efficient navigation
│   ├── parser.py      # VCD trace parsing
│   ├── model.py       # Data models (TraceData, etc.)
│   ├── symbols.py     # ELF symbol mapping
│   ├── jpeg.py        # JPEG reconstruction logic
│   ├── analysis.py    # Analysis utilities
│   └── __init__.py    # Package initialization
├── examples/          # Example scripts and helpers
│   ├── example_attack.py
│   ├── rsa_attack_clean.py
│   ├── run_jpeg_attack.py
│   ├── jpeg_attack_navigator.py
│   ├── example_script.py
│   ├── example_symbols.py
│   ├── debug_jpeg_ranges.py
│   └── preview_pgm.py
├── output/            # Generated outputs (images, JSON, etc.)
├── traces/            # Input trace data files
├── CLI.py             # Main interactive CLI launcher
├── README.md          # This file
└── .gitattributes     # Git file handling rules
```

## Quick Start

### Basic Usage

```python
from sgxtrace import load_vcd_trace, AttackRunner

# Load a trace
trace = load_vcd_trace("traces/trace_rsa.vcd")

# Create an attack runner
runner = AttackRunner(trace)

# Define callbacks for interesting transitions
def on_square_operation(runner):
    print("Square operation detected")

def on_multiply_operation(runner):
    print("Multiply operation detected")

# Register callbacks
runner.on_transition("modpow_page", "square_page", on_square_operation)
runner.on_transition("modpow_page", "multiply_page", on_multiply_operation)

# Run the attack
runner.run()
```

### RSA Attack Example

```python
from sgxtrace import load_vcd_trace, AttackRunner

# Clean, declarative RSA attack
def run_rsa_attack():
    trace = load_vcd_trace("traces/trace_rsa.vcd")
    runner = AttackRunner(trace)

    runner.state["symbols"] = []

    def on_square(runner):
        runner.state["symbols"].append("S")

    def on_multiply(runner):
        runner.state["symbols"].append("M")

    runner.on_transition("_17", "_20", on_square)      # modpow -> square
    runner.on_transition("_17", "_22", on_multiply)    # modpow -> multiply
    runner.on_page("_31", lambda r: print(f"Operation: {''.join(r.state['symbols'])}"))

    runner.run()
```

### JPEG Reconstruction

```python
from sgxtrace import attack_jpeg_vcd, save_attack_outputs
from sgxtrace.jpeg import JpegAttackConfig

# Configure and run JPEG attack
config = JpegAttackConfig(num_colors=1)  # Grayscale
result = attack_jpeg_vcd("traces/trace_libjpeg.vcd", config)

# Save results (outputs go to output/ folder)
save_attack_outputs(
    result,
    image_path="output/reconstructed.pgm",
    preview_path="output/preview.png"
)
```

## Architecture

### Core Library

The main library is centered in `sgxtrace.core`, which exposes the trace engine and reusable attack primitives.

- **`sgxtrace.core.TraceData`**: Parsed VCD trace with events, timings, and page intervals
- **`sgxtrace.core.TraceNavigator`**: Efficient navigation with breakpoints and page stepping
- **`sgxtrace.core.AttackRunner`**: Declarative attack framework with callbacks
- **`sgxtrace.jpeg.JpegReconstruction`**: Image reconstruction from page access patterns

### Interactive CLI

The interactive command-line interface lives in `sgxtrace.interactive` and uses the library core to provide trace exploration commands. The main launcher is `CLI.py` in the project root.

### Attack Patterns

The library supports two main approaches for implementing attacks:

1. **Declarative Callbacks** (`AttackRunner`): Define interesting pages and transitions, register callbacks
2. **Breakpoint Navigation** (`TraceNavigator`): Set breakpoints and jump between interesting events

## Examples

Run examples with `PYTHONPATH=. python examples/<script>.py`:

- `examples/rsa_attack_runner.py`: Clean RSA attack using AttackRunner
- `examples/rsa_attack_clean.py`: Improved RSA attack with better symbol decoding
- `examples/jpeg_attack_reconstruction.py`: JPEG reconstruction using built-in functions
- `examples/jpeg_attack_navigator.py`: JPEG attack using TraceNavigator
- `examples/rsa_attack_legacy.py`: Legacy complex RSA attack (for comparison)
- `examples/example_symbols.py`: Symbol mapping helper for page/function analysis
- `examples/debug_jpeg_ranges.py`: Debug helper for JPEG page ranges
- `examples/preview_pgm.py`: PGM image preview utility

## CLI Interface

Interactive exploration of traces:

```bash
python CLI.py
```

Available commands:

- `load-trace <path>`: Load a VCD trace
- `load-binary <path>`: Load ELF symbols for page mapping
- `break-page <name>`: Set breakpoint on page activation
- `step`: Navigate through trace
- `timeline <start> <end>`: Show page access timeline

## Installation

```bash
pip install -e .
```

## Dependencies

- Python 3.8+
- PIL/Pillow (for PNG output)
- pyelftools (for symbol mapping)
