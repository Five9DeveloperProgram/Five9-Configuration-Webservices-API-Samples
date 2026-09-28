#!/usr/bin/env python3
"""Export campaign profile names from a getCampaignProfiles.json file to CSV.

Usage:
  python scripts/campaign_profiles_to_csv.py \
      --input "domain_snapshots/Devry University/ivr-documentation/20260724_131056/getCampaignProfiles.json" \
      --output campaign_profile_names.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export campaign profile names from getCampaignProfiles.json to CSV"
    )
    parser.add_argument(
        "--input",
        "-i",
        default=(
            "domain_snapshots/Devry University/ivr-documentation/"
            "20260724_131056/getCampaignProfiles.json"
        ),
        help="Path to getCampaignProfiles.json",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="campaign_profile_names.csv",
        help="Output CSV path",
    )
    return parser.parse_args()


def _iter_profiles(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                yield item
        return

    if isinstance(payload, dict):
        # Handle alternate wrapped payloads some exports use.
        for key in ("campaignProfiles", "profiles", "items", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        yield item
                return


def extract_names(payload: Any) -> list[str]:
    names = []
    for profile in _iter_profiles(payload):
        name = profile.get("name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return names


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    with input_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    names = extract_names(payload)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["campaign_profile_name"])
        for name in names:
            writer.writerow([name])

    print(f"Wrote {len(names)} campaign profile names to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
