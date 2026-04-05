from __future__ import annotations

import argparse

from sgxtrace import JpegAttackConfig, attack_jpeg_vcd, save_attack_outputs


def _parse_pages(value: str) -> frozenset[int] | None:
    value = value.strip()
    if not value:
        return None
    if value.lower() in {"none", "all", "*"}:
        return None
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return frozenset(int(p) for p in parts)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconstrueer een JPEG-beeld uit een VCD page-access trace."
    )
    parser.add_argument("trace", help="Pad naar de VCD trace")

    parser.add_argument(
        "--output",
        default="jpeg_reconstruction.pgm",
        help="Output image (PGM voor grayscale, PPM voor kleur, of PNG)",
    )
    parser.add_argument(
        "--raw-output",
        default="jpeg_reconstruction.json",
        help="Output van ruwe block-tellingen als JSON",
    )
    parser.add_argument(
        "--preview-output",
        default="jpeg_reconstruction_preview.png",
        help="PNG preview van de reconstructie",
    )
    parser.add_argument(
        "--preview-scale",
        type=int,
        default=16,
        help="Upscale-factor voor de preview PNG",
    )
    parser.add_argument(
        "--color",
        action="store_true",
        help="Gebruik 3 kleurkanalen in plaats van 1 grayscale kanaal",
    )
    parser.add_argument(
        "--aexnotify",
        action="store_true",
        help="Gebruik de AEX-notify data-count range",
    )

    parser.add_argument("--start-min", type=int, default=54)
    parser.add_argument("--start-max", type=int, default=55)

    parser.add_argument("--next-row-min", type=int, default=44)
    parser.add_argument("--next-row-max", type=int, default=45)

    parser.add_argument("--start-row-min", type=int, default=58)
    parser.add_argument("--start-row-max", type=int, default=59)

    parser.add_argument("--pre-idct-min", type=int, default=56)
    parser.add_argument("--pre-idct-max", type=int, default=57)

    parser.add_argument("--idct-min", type=int, default=62)
    parser.add_argument("--idct-max", type=int, default=64)

    parser.add_argument(
        "--data-min",
        type=int,
        default=154,
        help="Ondergrens data-count range",
    )
    parser.add_argument(
        "--data-max",
        type=int,
        default=157,
        help="Bovengrens data-count range (exclusive)",
    )

    parser.add_argument(
        "--data-pages",
        default="154,155,156",
        help="Komma-gescheiden lijst met data pages. Gebruik 'all' om enkel data-range te gebruiken.",
    )

    args = parser.parse_args()

    config = JpegAttackConfig(
        start_range=range(args.start_min, args.start_max),
        next_row_range=range(args.next_row_min, args.next_row_max),
        start_row_range=range(args.start_row_min, args.start_row_max),
        pre_idct_slow_range=range(args.pre_idct_min, args.pre_idct_max),
        idct_slow_range=range(args.idct_min, args.idct_max),
        data_count_pages=_parse_pages(args.data_pages),
        data_count_range_no_aexnotify=range(args.data_min, args.data_max),
        data_count_range_aexnotify=range(args.data_min, args.data_max),
        num_colors=3 if args.color else 1,
        aexnotify=args.aexnotify,
    )

    result = attack_jpeg_vcd(args.trace, config)

    save_attack_outputs(
        result,
        image_path=args.output,
        raw_json_path=args.raw_output,
        preview_path=args.preview_output,
        preview_scale=args.preview_scale,
    )

    width, height = result.reconstruction.reconstructed_size()
    print(f"Processed pages: {result.processed_pages}")
    print(f"Final state:     {result.final_state.value}")
    print(f"Image size:      {width} x {height} blocks")
    print(f"Channels:        {config.num_colors}")
    print(f"Image written:   {args.output}")
    print(f"Preview written: {args.preview_output}")
    print(f"Raw JSON:        {args.raw_output}")
    print(f"Min data count:  {result.reconstruction.min_data}")
    print(f"Max data count:  {result.reconstruction.max_data}")
    print()
    print("Effective config:")
    print(f"  start_range      = [{args.start_min}, {args.start_max})")
    print(f"  next_row_range   = [{args.next_row_min}, {args.next_row_max})")
    print(f"  start_row_range  = [{args.start_row_min}, {args.start_row_max})")
    print(f"  pre_idct_range   = [{args.pre_idct_min}, {args.pre_idct_max})")
    print(f"  idct_range       = [{args.idct_min}, {args.idct_max})")
    print(f"  data_range       = [{args.data_min}, {args.data_max})")
    print(f"  data_pages       = {sorted(config.data_count_pages) if config.data_count_pages else 'ALL'}")


if __name__ == "__main__":
    main()
