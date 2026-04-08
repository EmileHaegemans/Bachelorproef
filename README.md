# Bachelorproef: Interactive Exploitation of Intel SGX Enclaves with SGX-Step

This project provides a Python library for analyzing Intel SGX enclave execution traces captured with SGX-Step. The library enables page-based side-channel attacks that reconstruct sensitive information from page access patterns.

## Features

- **Trace analysis**: parse and inspect VCD (Value Change Dump) traces from SGX-Step
- **Symbol mapping**: map ELF symbols to enclave pages for targeted analysis
- **Reusable attack framework**:
  - `AttackRunner` for declarative attacks based on page hits and transitions
  - `TraceNavigator` for breakpoint-driven trace exploration
- **Built-in example attacks**:
  - RSA exponent reconstruction from Montgomery multiplication patterns
  - JPEG image reconstruction from decompression access patterns

## Project Structure

```text
Bachelorproef/
├── sgxtrace/          # Core library package
│   ├── core.py        # Centralized library exports and shared API
│   ├── interactive.py # Interactive CLI implementation
│   ├── attack.py      # AttackRunner framework
│   ├── navigator.py   # TraceNavigator for efficient navigation
│   ├── parser.py      # VCD trace parsing
│   ├── model.py       # Data models (TraceData, StepResult, ...)
│   ├── symbols.py     # ELF symbol mapping helpers
│   ├── jpeg.py        # JPEG reconstruction state machine and exporters
│   ├── analysis.py    # Analysis utilities on parsed traces
│   └── __init__.py    # Public package exports
├── examples/          # Example scripts and helpers
│   ├── rsa_attack_runner.py
│   ├── rsa_attack_clean.py
│   ├── rsa_attack_legacy.py
│   ├── jpeg_attack_reconstruction.py
│   ├── jpeg_attack_navigator.py
│   ├── debug_jpeg_ranges.py
│   ├── example_symbols.py
│   └── preview_pgm.py
├── output/            # Generated outputs (images, JSON, previews)
├── traces/            # Input trace data
├── CLI.py             # Interactive CLI launcher
└── README.md
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
print(len(trace.times))
print(len(trace.access_history))
```

## Attack Overview

### 1. RSA attack

The RSA example scripts assume four pages of interest in the bundled trace:

- `_17`: modular exponentiation anchor (`modpow`)
- `_20`: square operation
- `_22`: multiply operation
- `_31`: end marker for one reconstructed exponent segment

The attack works in two phases:

1. observe transitions from `modpow` to `square` or `multiply`
2. decode the resulting `A/B` symbol stream into exponent bits

Use the clean version when you want the clearest implementation:

```bash
PYTHONPATH=. python examples/rsa_attack_clean.py
```

Use the runner version when you want a shorter example built on the same primitives:

```bash
PYTHONPATH=. python examples/rsa_attack_runner.py
```

### 2. JPEG reconstruction attack

The JPEG attack models libjpeg decompression as a small state machine:

- start of image processing
- next row / start row transitions
- IDCT phase
- data-count phase

The number of observed page hits in the data-count phase is used as a proxy for the reconstructed block intensity.

Run the standard reconstruction pipeline:

```bash
PYTHONPATH=. python examples/jpeg_attack_reconstruction.py
```

This writes:

- a reconstructed image (`.pgm`, `.ppm`, or `.png`)
- a raw JSON dump of per-block counters
- a scaled preview image for quick inspection

Run the navigator-based variant when you want more control over the stepping logic:

```bash
PYTHONPATH=. python examples/jpeg_attack_navigator.py
```

## Library Building Blocks

### `TraceData`

`TraceData` is the parsed representation of a VCD trace. It stores, among other things:

- `events`: changed signals per timestamp
- `times`: sorted timestamps
- `page_intervals`: active intervals per page
- `access_history`: chronological page activations
- `transition_map`: precomputed page-to-page transitions

### `TraceNavigator`

`TraceNavigator` lets you step through the parsed trace while keeping track of:

- the current timestamp and event index
- currently active pages
- breakpoints on page activations
- the last added and removed pages

### `AttackRunner`

`AttackRunner` wraps `TraceNavigator` and adds a callback API:

- `on_page(page, callback)` triggers when a page becomes active
- `on_transition(from_page, to_page, callback)` triggers on a specific page transition

This is the main high-level API for clean attack implementations.

## Other Utilities

- `examples/debug_jpeg_ranges.py`: inspect which candidate pages are active in a JPEG trace
- `examples/example_symbols.py`: map pages to ELF symbols and resolve pages by symbol name
- `examples/preview_pgm.py`: convert a PGM/PPM reconstruction into a PNG preview
- `CLI.py`: interactive trace exploration shell

## Dependencies

- Python 3.8+
- Pillow (for PNG output)
- pyelftools (for ELF symbol mapping)
