"""Export campaigns whose names contain selected business categories.

The script is read-only. It signs in using the repository's standard credential
options and writes matching campaign summaries to a CSV file.

Example:

    python examples/domain_config/export_campaigns_by_category.py \
        --account_alias default_account
"""

import csv
import logging
from pathlib import Path

from five9.utils.common import common_parser_arguments, create_five9_client


CATEGORIES = ("Healthcare", "Business", "Technology", "Other")
DEFAULT_OUTPUT = Path("private/campaigns_by_category.csv")
FIELDNAMES = (
    "matched_categories",
    "name",
    "type",
    "state",
    "mode",
    "profile_name",
    "description",
    "training_mode",
)


def matching_categories(campaign_name):
    """Return requested categories found in a campaign name, ignoring case."""
    normalized_name = (campaign_name or "").casefold()
    return [
        category for category in CATEGORIES if category.casefold() in normalized_name
    ]


def campaign_row(campaign, categories):
    """Convert a Five9 campaign summary to a CSV row."""
    return {
        "matched_categories": "; ".join(categories),
        "name": getattr(campaign, "name", "") or "",
        "type": getattr(campaign, "type", "") or "",
        "state": getattr(campaign, "state", "") or "",
        "mode": getattr(campaign, "mode", "") or "",
        "profile_name": getattr(campaign, "profileName", "") or "",
        "description": getattr(campaign, "description", "") or "",
        "training_mode": getattr(campaign, "trainingMode", ""),
    }


def export_matching_campaigns(campaigns, output_path):
    """Write matching campaign summaries and return the number exported."""
    rows = []
    for campaign in campaigns or []:
        categories = matching_categories(getattr(campaign, "name", ""))
        if categories:
            rows.append(campaign_row(campaign, categories))

    rows.sort(key=lambda row: row["name"].casefold())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main():
    args = common_parser_arguments(
        [
            {
                "name": "--output",
                "type": Path,
                "default": DEFAULT_OUTPUT,
                "help": f"CSV output path (default: {DEFAULT_OUTPUT})",
            }
        ]
    )
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    client = create_five9_client(args)
    campaigns = client.service.getCampaigns()
    exported_count = export_matching_campaigns(campaigns, args.output)
    logging.info(
        "Exported %d matching campaign(s) from %s to %s",
        exported_count,
        client.domain_name,
        args.output,
    )


if __name__ == "__main__":
    main()