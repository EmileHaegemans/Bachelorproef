from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Zet een PGM of PPM om naar een PNG preview.")
    parser.add_argument("input", help="Pad naar .pgm of .ppm bestand")
    parser.add_argument(
        "--output",
        default=None,
        help="Pad naar output PNG. Default: <input_stem>_preview.png",
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=16,
        help="Upscale-factor voor de preview",
    )
    args = parser.parse_args()

    try:
        from PIL import Image
    except ImportError:
        raise SystemExit("Pillow ontbreekt. Installeer eerst: pip install pillow")

    input_path = Path(args.input)
    output_path = (
        Path(args.output)
        if args.output is not None
        else input_path.with_name(f"{input_path.stem}_preview.png")
    )

    img = Image.open(input_path)
    if args.scale > 1:
        img = img.resize((img.width * args.scale, img.height * args.scale), Image.NEAREST)
    img.save(output_path)

    print(f"Preview geschreven naar: {output_path}")


if __name__ == "__main__":
    main()