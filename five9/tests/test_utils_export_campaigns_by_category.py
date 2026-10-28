import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from examples.domain_config.export_campaigns_by_category import (
    export_matching_campaigns,
    matching_categories,
)


class TestExportCampaignsByCategory(unittest.TestCase):
    def test_matching_categories_is_case_insensitive(self):
        self.assertEqual(
            matching_categories("Inbound healthcare TECHNOLOGY"),
            ["Healthcare", "Technology"],
        )
        self.assertEqual(matching_categories("Retail"), [])

    def test_export_writes_only_matches_in_name_order(self):
        campaigns = [
            SimpleNamespace(name="Technology West", type="INBOUND", state="RUNNING"),
            SimpleNamespace(name="Retail", type="OUTBOUND", state="STOPPED"),
            SimpleNamespace(
                name="business healthcare",
                type="OUTBOUND",
                state="STOPPED",
                mode="BASIC",
                profileName="Business Profile",
                description="Two categories",
                trainingMode=False,
            ),
        ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "campaigns.csv"
            exported_count = export_matching_campaigns(campaigns, output_path)
            with output_path.open(newline="", encoding="utf-8") as csv_file:
                rows = list(csv.DictReader(csv_file))

        self.assertEqual(exported_count, 2)
        self.assertEqual(
            [row["name"] for row in rows],
            ["business healthcare", "Technology West"],
        )
        self.assertEqual(rows[0]["matched_categories"], "Healthcare; Business")
        self.assertEqual(rows[0]["profile_name"], "Business Profile")
        self.assertEqual(rows[1]["profile_name"], "")


if __name__ == "__main__":
    unittest.main()