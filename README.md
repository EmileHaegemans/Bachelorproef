# Bachelorproef: SGX-Step Trace Analysis & Side-Channel Attacks

<p align="center">
  <img src="./logo_SGXTraces_library.png" alt="SGXTrace logo" width="560">
</p>

This project provides a Python library and example scripts for analyzing Intel SGX enclave execution traces captured with SGX-Step. It enables page-based side-channel attacks that reconstruct sensitive information from page access patterns, with a focus on modular, reusable attack logic and practical demonstrations.

## Features

- **Trace analysis**: Parse and inspect VCD (Value Change Dump) traces from SGX-Step
- **Symbol mapping**: Map ELF symbols to enclave pages for targeted analysis
- **Reusable attack framework**:
  - `AttackRunner` for declarative attacks based on page hits and transitions
  - `TraceNavigator` for breakpoint-driven trace exploration
- **Built-in example attacks**:
  - RSA exponent reconstruction from Montgomery multiplication patterns
  - JPEG image reconstruction from decompression access patterns

## Project Structure

```text
sgxtrace/          # Core library package
  core.py         # Centralized library exports and shared API
  attack.py       # AttackRunner framework
  navigator.py    # TraceNavigator for efficient navigation
  parser.py       # VCD trace parsing
  model.py        # Data models (TraceData, StepResult, ...)
  symbols.py      # ELF symbol mapping helpers
  jpeg.py         # JPEG reconstruction state machine and exporters
  analysis.py     # Analysis utilities on parsed traces
  __init__.py     # Public package exports
examples/         # Example scripts and helpers
  rsa_attack_runner.py
  rsa_attack_legacy.py
  jpeg_attack_reconstruction.py
  jpeg_attack_navigator.py
  debug_jpeg_ranges.py
  preview_pgm.py
  rsa_attack_symbols.py
output/           # Generated outputs (images, JSON, previews)
traces/           # Input trace data
setup.py          # Project installer for editable mode
README.md         # This file
```

## Quick Start

### Installation

```bash
pip install -e .
```

### Basic trace loading

```python
from sgxtrace import load_vcd_trace

trace = load_vcd_trace("traces/trace_rsa.vcd")
print(len(trace.times), len(trace.access_history))
```

## Example Attacks

### RSA Exponent Reconstruction

The RSA attack scripts extract secret exponent bits from page access patterns in modular exponentiation traces. They work by:

1. Observing transitions between key pages (modpow, square, multiply, end) in the trace.
2. Decoding the resulting symbol stream (A/B) into exponent bits using the Montgomery ladder heuristic.

**Run the attack:**

```bash
python examples/rsa_attack_runner.py
```

The legacy and symbols variants provide alternative decoding or symbol mapping strategies.

### JPEG Image Reconstruction

The JPEG attacks reconstruct a grayscale or color image from a libjpeg decompression trace by modeling the decompression as a state machine and counting page hits in key phases.

- **Automated pipeline:**

  ```bash
  python examples/jpeg_attack_reconstruction.py
  ```

  Outputs a reconstructed image (PGM/PPM/PNG), a JSON dump, and a PNG preview.

- **Navigator (stepwise/interactive):**

  ```bash
  python examples/jpeg_attack_navigator.py
  ```

  Lets you inspect state transitions and outputs a PGM and PNG preview.

- **Configurable CLI:**

  ```bash
  python examples/example_jpeg.py --help
  ```

  Allows full control over page ranges, color mode, and output files.

## Library Building Blocks

### `TraceData`

The parsed representation of a VCD trace, with:

- `events`: changed signals per timestamp
- `times`: sorted timestamps
- `page_intervals`: active intervals per page
- `access_history`: chronological page activations
- `transition_map`: precomputed page-to-page transitions

### `TraceNavigator`

Step through the parsed trace, track the current state, and set breakpoints on page activations.

### `AttackRunner`

High-level API for declarative attacks:

- `on_page(page, callback)`: triggers when a page becomes active
- `on_transition(from_page, to_page, callback)`: triggers on a specific page transition

## Utilities

- `examples/debug_jpeg_ranges.py`: Inspect which candidate pages are active in a JPEG trace
- `examples/preview_pgm.py`: Convert a PGM/PPM reconstruction into a PNG preview

## Dependencies

- Python 3.8+
- Pillow (for PNG output)
- pyelftools (for ELF symbol mapping)

## Interactive Command-Line Interface (CLI)

The project includes an interactive command-line interface for exploring traces and prototyping attacks.

**Launch the CLI:**

```bash
python CLI.py
```

**Key Features and Commands:**

- `help` — Show all available commands
- `quit` — Exit the CLI
- `load-trace <path>` — Load a VCD trace for analysis
- `load-binary <path>` — Load ELF symbols for page mapping
- `show-map` — Print the page-to-symbol mapping
- `map-page <page>` — Show all functions on a specific page
- `map-symbol <name>` — Find which page a function belongs to
- `step [n]` — Step forward n events (default 1)
- `page-step` — Jump to the next moment pages change
- `active-pages` — Show currently active pages
- `frequency <page> [start] [end]` — Show access intervals for a page (optionally filtered by time)
- `timeline <start_t> <end_t>` — Show chronological order of page accesses by time
- `access-trace <s_idx> <e_idx>` — Show chronological order of page accesses by index
- `transitions <page>` — Show which pages follow a given page
- `top-pages <amount>` — Show the most accessed pages and their counts
- `breakpoints` — List all breakpoints
- `break-page <name>` — Set a breakpoint for page activation
- `unbreak-page <name>` — Remove a page breakpoint

The CLI is ideal for:

- Quick exploration and inspection of traces
- Debugging and learning how the trace analysis tools work
- Prototyping and testing attack logic before automating in scripts

---

## How to Use This Library

1. Install in editable mode:

   ```bash
   pip install -e .
   ```

2. Place your VCD traces in the `traces/` directory.
3. Run or adapt the example scripts in `examples/` to analyze traces or build your own attacks.

For more details, see the docstrings in each example script and the sgxtrace package modules.
