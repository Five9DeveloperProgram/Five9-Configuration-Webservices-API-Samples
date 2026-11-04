import io
import json
from pathlib import Path
import runpy
import tempfile
from types import SimpleNamespace
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import Mock, patch

from examples.ivrs.upload_ivr_snapshots import (
    apply_migration,
    confirm_destination,
    dependency_order,
    load_migration_set,
    prepare_script,
    target_names,
)


class TestUploadIvrSnapshots(unittest.TestCase):
    def setUp(self):
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_dir.cleanup)
        self.source_dir = Path(self.temporary_dir.name)
        self.snapshots = {
            "Main": {
                "name": "Main",
                "description": "Example entry point",
                "xmlDefinition": (
                    "<ivr><domainId>123</domainId>"
                    "<ivrScript><name>Child</name></ivrScript>"
                    "<ivrScript><name>External</name></ivrScript>"
                    "<stringValue><value>Child</value></stringValue></ivr>"
                ),
            },
            "Child": {
                "name": "Child",
                "xmlDefinition": "<ivr><domainId>123</domainId></ivr>",
            },
        }
        for name, snapshot in self.snapshots.items():
            self.write_snapshot(name, snapshot)
        self.client = Mock(domain_name="Destination Domain", domain_id=456)
        self.client.throttled_service.getIVRScripts.return_value = []

    def write_snapshot(self, name, snapshot):
        with (self.source_dir / f"{name}.json").open("w", encoding="utf-8") as output:
            json.dump(snapshot, output)

    def test_loads_snapshots_without_companion_files(self):
        self.assertEqual(load_migration_set(self.source_dir), self.snapshots)

    def test_filters_snapshot_filenames(self):
        self.assertEqual(
            set(load_migration_set(self.source_dir, "Main*.json")), {"Main"}
        )

    def test_rejects_empty_selection(self):
        with self.assertRaisesRegex(ValueError, "No snapshots matching"):
            load_migration_set(self.source_dir, "Missing*.json")

    def test_validates_snapshot_contents(self):
        invalid_snapshots = [
            ([], ValueError),
            ({"name": "Wrong"}, ValueError),
            ({"name": "Main"}, ValueError),
            ({"name": "Main", "xmlDefinition": "<broken>"}, ET.ParseError),
        ]
        for snapshot, exception in invalid_snapshots:
            with self.subTest(snapshot=snapshot):
                self.write_snapshot("Main", snapshot)
                with self.assertRaises(exception):
                    load_migration_set(self.source_dir)

    def test_preserves_names_by_default(self):
        self.assertEqual(
            target_names(self.snapshots), {"Main": "Main", "Child": "Child"}
        )

    def test_orders_referenced_scripts_before_parents(self):
        self.assertEqual(dependency_order(self.snapshots), ["Child", "Main"])

    def test_prepares_destination_and_selected_references_only(self):
        name_map = target_names(self.snapshots, " - Copy")
        script, references = prepare_script(self.snapshots["Main"], name_map, 456)
        root = ET.fromstring(script["xmlDefinition"])

        self.assertEqual(script["name"], "Main - Copy")
        self.assertEqual(script["description"], "Example entry point")
        self.assertEqual(root.findtext("domainId"), "456")
        self.assertEqual(references, [("Child", "Child - Copy")])
        self.assertEqual(
            [element.text for element in root.findall("ivrScript/name")],
            ["Child - Copy", "External"],
        )
        self.assertEqual(root.findtext("stringValue/value"), "Child")

    def test_interactively_confirms_detected_destination(self):
        with patch("builtins.input", return_value="Destination Domain") as prompt:
            confirmed_domain = confirm_destination(self.client)
        self.assertEqual(confirmed_domain, "Destination Domain")
        prompt.assert_called_once()

    def test_rejects_incorrect_destination_confirmation(self):
        with self.assertRaises(ValueError):
            confirm_destination(self.client, "Wrong Domain")
        with self.assertRaises(ValueError):
            apply_migration(self.client, self.snapshots, "Wrong Domain")
        self.assertEqual(self.client.throttled_service.mock_calls, [])

    def test_refuses_existing_targets_without_resume(self):
        self.client.throttled_service.getIVRScripts.return_value = [
            SimpleNamespace(name="Main - Copy")
        ]
        with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
            apply_migration(
                self.client,
                self.snapshots,
                "Destination Domain",
                target_suffix=" - Copy",
            )
        self.client.throttled_service.createIVRScript.assert_not_called()
        self.client.throttled_service.modifyIVRScript.assert_not_called()

    def test_upload_and_resume_use_throttled_calls_and_custom_suffix(self):
        for resume in (False, True):
            with self.subTest(resume=resume):
                self.client.reset_mock()
                self.client.throttled_service.getIVRScripts.return_value = (
                    [SimpleNamespace(name="Main - Copy")] if resume else []
                )
                apply_migration(
                    self.client,
                    self.snapshots,
                    "Destination Domain",
                    resume=resume,
                    target_suffix=" - Copy",
                )
                service = self.client.throttled_service
                self.assertEqual(service.createIVRScript.call_count, 1 if resume else 2)
                uploaded = [
                    invocation.kwargs["scriptDef"]
                    for invocation in service.modifyIVRScript.call_args_list
                ]
                self.assertEqual(
                    [script["name"] for script in uploaded],
                    ["Child - Copy", "Main - Copy"],
                )
                self.assertEqual(
                    ET.fromstring(uploaded[1]["xmlDefinition"]).findtext(
                        "ivrScript/name"
                    ),
                    "Child - Copy",
                )
                self.assertEqual(self.client.service.mock_calls, [])

    def test_rejects_cycles_before_api_calls(self):
        self.snapshots["Child"]["xmlDefinition"] = (
            "<ivr><domainId>123</domainId>"
            "<ivrScript><name>Main</name></ivrScript></ivr>"
        )
        with self.assertRaisesRegex(ValueError, "Circular IVR dependency"):
            apply_migration(self.client, self.snapshots, "Destination Domain")
        self.assertEqual(self.client.throttled_service.mock_calls, [])

    def test_cli_preview_uses_selected_directory_without_connection(self):
        with patch(
            "sys.argv",
            [
                "upload_ivr_snapshots.py",
                "--source-dir",
                str(self.source_dir),
                "--file-pattern",
                "Main*.json",
                "--target-suffix",
                " - Copy",
            ],
        ), patch("five9.utils.common.create_five9_client") as create_client, patch(
            "sys.stdout", new_callable=io.StringIO
        ) as output:
            runpy.run_path(
                str(
                    Path(__file__).resolve().parents[2]
                    / "examples/ivrs/upload_ivr_snapshots.py"
                ),
                run_name="__main__",
            )
        create_client.assert_not_called()
        self.assertIn(f"Source directory: {self.source_dir}", output.getvalue())
        self.assertIn("Scripts selected: 1", output.getvalue())
        self.assertIn("Main -> Main - Copy", output.getvalue())
        self.assertIn("Dry run only", output.getvalue())


if __name__ == "__main__":
    unittest.main()
