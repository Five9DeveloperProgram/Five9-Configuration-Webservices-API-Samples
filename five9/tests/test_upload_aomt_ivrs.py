import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from examples.ivrs.upload_aomt_ivrs import (
    SOURCE_DIR,
    confirm_destination,
    dependency_order,
    load_migration_set,
    prepare_script,
    target_names,
)


class TestUploadAomtIvrs(unittest.TestCase):
    def test_orders_referenced_scripts_before_parents(self):
        migration_set = load_migration_set(SOURCE_DIR)

        order = dependency_order(migration_set)

        self.assertLess(
            order.index("fs Location Metro Region Mapper"),
            order.index("fs Get Caller Location"),
        )
        self.assertLess(
            order.index("fs Get Caller Location"),
            order.index("fs Get Location By Department"),
        )
        self.assertLess(
            order.index("fs Get Location By Department"), order.index("DEM")
        )
        self.assertLess(order.index("DEMBestAgentRouting"), order.index("DEM"))

    def test_interactively_confirms_detected_destination(self):
        client = type("Client", (), {"domain_name": "Destination Domain"})()

        with patch("builtins.input", return_value="Destination Domain") as prompt:
            confirmed_domain = confirm_destination(client)

        self.assertEqual(confirmed_domain, "Destination Domain")
        prompt.assert_called_once()

    def test_rejects_incorrect_destination_confirmation(self):
        client = type("Client", (), {"domain_name": "Destination Domain"})()

        with self.assertRaises(ValueError):
            confirm_destination(client, "Wrong Domain")

    def test_discovers_expected_modified_counterparts(self):
        migration_set = load_migration_set(SOURCE_DIR)

        self.assertEqual(
            set(migration_set),
            {
                "DEM",
                "DEM Returned Calls",
                "DEM Specialty Transfer",
                "DEMBestAgentRouting",
                "Meera  Returned Calls",
                "fs Get Caller Location",
                "fs Get Location By Department",
                "fs Location Metro Region Mapper",
                "fs Salesforce Query Prospect",
            },
        )

    def test_prepares_destination_domain_and_cross_ivr_references(self):
        migration_set = load_migration_set(SOURCE_DIR)
        name_map = target_names(migration_set)

        script, references = prepare_script(
            migration_set["DEM"], name_map, destination_domain_id=987654
        )
        root = ET.fromstring(script["xmlDefinition"])

        self.assertEqual(script["name"], "DEM - AOMT")
        self.assertEqual(root.findtext("domainId"), "987654")
        self.assertIn(("DEMBestAgentRouting", "DEMBestAgentRouting - AOMT"), references)
        self.assertIn(
            (
                "fs Get Location By Department",
                "fs Get Location By Department - AOMT",
            ),
            references,
        )

        string_values = {
            element.text for element in root.findall(".//stringValue/value")
        }
        self.assertIn("DEM", string_values)


if __name__ == "__main__":
    unittest.main()
