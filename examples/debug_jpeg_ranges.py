from __future__ import annotations

import argparse
from collections import Counter

from sgxtrace import load_vcd_trace


def page_name_to_number(page_name: str) -> int:
    if page_name.startswith("_"):
        return int(page_name[1:])
    return int(page_name)


def iter_v1_page_events(trace):
    for t, changes in zip(trace.times, trace.events):
        for signal_name, value in changes.items():
            if value != "1":
                continue
            try:
                page_number = page_name_to_number(signal_name)
            except ValueError:
                continue
            yield t, signal_name, page_number


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug libjpeg page ranges in a VCD trace")
    parser.add_argument("trace", help="Pad naar de VCD trace")
    parser.add_argument("--top", type=int, default=30, help="Aantal top pages om te tonen")
    parser.add_argument(
        "--data-min",
        type=int,
        default=150,
        help="Ondergrens voor candidate data pages",
    )
    parser.add_argument(
        "--data-max",
        type=int,
        default=4340,
        help="Bovengrens voor candidate data pages (exclusive)",
    )
    args = parser.parse_args()

    trace = load_vcd_trace(args.trace)

    page_counter = Counter()
    total_v1_events = 0

    start_hits = []
    next_row_hits = []
    start_row_hits = []
    pre_idct_hits = []
    idct_hits = []
    data_hits = []

    for t, page_name, page_number in iter_v1_page_events(trace):
        total_v1_events += 1
        page_counter[page_number] += 1

        if 54 <= page_number < 55:
            start_hits.append((t, page_name, page_number))
        if 44 <= page_number < 46:
            next_row_hits.append((t, page_name, page_number))
        if 58 <= page_number < 59:
            start_row_hits.append((t, page_name, page_number))
        if 59 <= page_number < 60:
            pre_idct_hits.append((t, page_name, page_number))
        if 63 <= page_number < 65:
            idct_hits.append((t, page_name, page_number))
        if args.data_min <= page_number < args.data_max:
            data_hits.append((t, page_name, page_number))

    print(f"Total V1 page events: {total_v1_events}")
    print()
    print("Hardcoded JPEG ranges hit counts:")
    print(f"  Start (54..55):        {len(start_hits)}")
    print(f"  NextRow (44..46):      {len(next_row_hits)}")
    print(f"  StartRow (58..59):     {len(start_row_hits)}")
    print(f"  PreIdctSlow (59..60):  {len(pre_idct_hits)}")
    print(f"  IdctSlow (63..65):     {len(idct_hits)}")
    print(f"  DataCount ({args.data_min}..{args.data_max}): {len(data_hits)}")
    print()

    print(f"Top {args.top} pages by V1 hits:")
    for page, count in page_counter.most_common(args.top):
        print(f"  {page:6d} -> {count}")

    print()
    data_only = [
        (page, count)
        for page, count in page_counter.most_common()
        if args.data_min <= page < args.data_max
    ]
    print("Top candidate data pages in configured data range:")
    for page, count in data_only[:20]:
        print(f"  {page:6d} -> {count}")

    print()
    if start_hits:
        print("First 10 Start hits:")
        for item in start_hits[:10]:
            print(" ", item)

    if start_row_hits:
        print("\nFirst 10 StartRow hits:")
        for item in start_row_hits[:10]:
            print(" ", item)

    if idct_hits:
        print("\nFirst 10 IdctSlow hits:")
        for item in idct_hits[:10]:
            print(" ", item)

    if next_row_hits:
        print("\nFirst 10 NextRow hits:")
        for item in next_row_hits[:10]:
            print(" ", item)


if __name__ == "__main__":
    main()