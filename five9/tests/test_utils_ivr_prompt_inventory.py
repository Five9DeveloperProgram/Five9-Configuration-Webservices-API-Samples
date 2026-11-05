import base64
import csv
import gzip
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from five9.utils.ivr_prompt_inventory import (
    COLUMNS,
    capture_inventory,
    inventory_rows,
    write_inventory,
)


def _tts():
    xml = (
        "<speakElement><textElement><body>Welcome</body></textElement>"
        "<variableElement><variableName>instance.name</variableName>"
        "</variableElement></speakElement>"
    )
    return base64.b64encode(gzip.compress(xml.encode("utf-8"))).decode("ascii")


IVR_XML = """<ivrScript>
  <functions><entry><value><functionBody>PRIVATE_FUNCTION</functionBody></value></entry></functions>
  <modules>
    <play><moduleName>Greeting</moduleName><data><prompts>
      <prompt><filePrompt><promptSelected>true</promptSelected>
        <prompt><name>Recorded</name></prompt></filePrompt>
        <ttsPrompt><xml>{}</xml><language>en-US</language></ttsPrompt>
      </prompt>
      <prompt><filePrompt><prompt><name>Generated</name></prompt></filePrompt></prompt>
      <prompt><filePrompt><prompt><name>Deleted</name></prompt></filePrompt></prompt>
      <prompt><filePrompt><promptSelected>false</promptSelected>
        <prompt><name>Inactive</name></prompt></filePrompt></prompt>
    </prompts></data></play>
  </modules>
  <modulesOnHangup>
    <announcement><moduleName>Notice</moduleName><data><prompts>
      <prompt><filePrompt><prompt><name>Recorded</name></prompt></filePrompt></prompt>
    </prompts></data></announcement>
  </modulesOnHangup>
</ivrScript>""".format(
    _tts()
)


class TestIvrPromptInventory(unittest.TestCase):
    def setUp(self):
        self.prompts = [
            SimpleNamespace(
                name="Recorded", languages=["en-US", "es-MX"], type="PreRecorded"
            ),
            {
                "name": "Generated",
                "languages": ["en-US"],
                "type": "TTSGenerated",
            },
        ]
        self.ivrs = [SimpleNamespace(name="Main", xmlDefinition=IVR_XML)]

    def test_inventory_joins_prompts_and_preserves_module_location(self):
        rows = inventory_rows("Example domain", self.prompts, self.ivrs)
        self.assertEqual(len(rows), 5)
        self.assertEqual(
            [row["Prompt source"] for row in rows],
            [
                "Domain prompt",
                "IVR-only TTS",
                "Domain prompt",
                "Not in getPrompts",
                "Domain prompt",
            ],
        )
        self.assertEqual(rows[0]["Languages"], "en-US, es-MX")
        self.assertEqual(rows[0]["Domain prompt TTS"], "No")
        self.assertEqual(rows[1]["Prompt name"], "")
        self.assertEqual(rows[1]["TTS text"], "Welcome {instance.name}")
        self.assertEqual(rows[1]["Variables"], "instance.name")
        self.assertEqual(rows[1]["Languages"], "en-US")
        self.assertEqual(rows[2]["TTS text"], "")
        self.assertEqual(rows[2]["Domain prompt TTS"], "Yes")
        self.assertEqual(rows[4]["Module type"], "announcement")
        self.assertEqual(rows[4]["Module name"], "Notice")
        self.assertEqual(rows[4]["Announcement"], "Yes")
        self.assertNotIn("PRIVATE_FUNCTION", str(rows))

    def test_domain_tts_text_only_when_explicitly_returned(self):
        self.prompts[1]["ttsText"] = "Hello there"
        row = inventory_rows("Domain", self.prompts, self.ivrs)[2]
        self.assertEqual(row["TTS text"], "Hello there")
        self.assertEqual(row["Domain prompt TTS"], "Yes")

    def test_excludes_announcements_only_when_requested(self):
        rows = inventory_rows("Domain", self.prompts, self.ivrs, True)
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["Announcement"] == "No" for row in rows))

    def test_invalid_source_is_not_silently_reported_as_empty(self):
        with self.assertRaises(ValueError):
            inventory_rows("Domain", [{"languages": []}], self.ivrs)
        with self.assertRaises(ValueError):
            inventory_rows("Domain", self.prompts, [{"name": "Broken"}])
        broken = [SimpleNamespace(name="Broken", xmlDefinition="<ivrScript>")]
        with self.assertRaises(ET.ParseError):
            inventory_rows("Domain", self.prompts, broken)
        broken_tts = IVR_XML.replace(_tts(), "invalid-data")
        with self.assertRaisesRegex(ValueError, "Cannot decode TTS"):
            inventory_rows(
                "Domain",
                self.prompts,
                [SimpleNamespace(name="Broken TTS", xmlDefinition=broken_tts)],
            )
        with self.assertRaisesRegex(ValueError, "duplicate prompt"):
            inventory_rows("Domain", self.prompts + [self.prompts[0]], self.ivrs)

    def test_capture_uses_two_read_only_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            client = Mock(domain_name="Example domain")
            client.service.getPrompts.return_value = self.prompts
            client.service.getIVRScripts.return_value = self.ivrs
            output = Path(directory) / "inventory.csv"
            self.assertEqual(capture_inventory(client, output), 5)
            self.assertEqual(
                client.service.mock_calls,
                [
                    unittest.mock.call.getPrompts(),
                    unittest.mock.call.getIVRScripts(),
                ],
            )
            with output.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                self.assertEqual(reader.fieldnames, list(COLUMNS))
                self.assertEqual(len(list(reader)), 5)
            client.service.reset_mock()
            with self.assertRaises(FileExistsError):
                capture_inventory(client, output)
            client.service.assert_not_called()
            output.unlink()
            client.service.getPrompts.return_value = None
            with self.assertRaisesRegex(ValueError, "no response"):
                capture_inventory(client, output)
            self.assertFalse(output.exists())

    def test_csv_is_private_and_spreadsheet_safe_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.csv"
            rows = inventory_rows("=RISK", self.prompts, self.ivrs)
            write_inventory(path, rows)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with path.open(encoding="utf-8-sig", newline="") as stream:
                result = list(csv.DictReader(stream))
            self.assertEqual(result[0]["Domain"], "'=RISK")
            with self.assertRaises(FileExistsError):
                write_inventory(path, rows)
