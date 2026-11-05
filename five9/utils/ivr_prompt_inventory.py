"""Build a local, prompt-only inventory from getPrompts and getIVRScripts."""

import csv
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .ivr_diagram import decode_tts


COLUMNS = (
    "Domain",
    "IVR script",
    "Module type",
    "Module name",
    "Languages",
    "Prompt name",
    "Prompt source",
    "Domain prompt TTS",
    "TTS text",
    "Variables",
    "Announcement",
)


def _value(obj, key, default=None):
    return (
        obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)
    )


def _languages(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value
    if not isinstance(value, (list, tuple)):
        raise ValueError("Unexpected getPrompts languages value")
    if not all(isinstance(item, str) for item in value):
        raise ValueError("Unexpected getPrompts language entry")
    return ", ".join(value)


def _csv_cell(value):
    """Prevent spreadsheet formula execution when opening the CSV in Excel."""
    text = str(value)
    if re.match(r"^\s*[=+\-@\t\r]", text):
        return "'" + text
    return text


def inventory_rows(domain, prompts, ivrs, exclude_announcements=False):
    """Return one row per file or TTS prompt occurrence in an IVR module.

    Only the prompt subtree is read; other IVR settings and script variables
    are not exported. A missing domain match is reported, not assumed deleted.
    """
    prompt_by_name = {}
    for prompt in prompts:
        name = _value(prompt, "name")
        if not name:
            raise ValueError("getPrompts returned a prompt without a name")
        if name in prompt_by_name:
            raise ValueError("getPrompts returned duplicate prompt names")
        prompt_by_name[name] = prompt

    rows = []
    for ivr in ivrs:
        script_name = _value(ivr, "name")
        xml_definition = _value(ivr, "xmlDefinition")
        if not script_name or not xml_definition:
            raise ValueError(
                "getIVRScripts returned a script without a name or xmlDefinition"
            )
        root = ET.fromstring(xml_definition)
        for container_name in ("modules", "modulesOnHangup"):
            container = root.find(container_name)
            if container is None:
                continue
            for module in container:
                data = module.find("data")
                if data is None:
                    continue
                for compound in data.findall(".//prompts/prompt") + data.findall(
                    "prompt"
                ):
                    for part in compound:
                        if part.tag not in ("filePrompt", "ttsPrompt"):
                            continue
                        announcement = (
                            module.tag == "announcement"
                            or (part.findtext(".//isAnnouncement") or "").lower()
                            == "true"
                        )
                        if exclude_announcements and announcement:
                            continue
                        row = {
                            "Domain": domain,
                            "IVR script": script_name,
                            "Module type": module.tag,
                            "Module name": module.findtext("moduleName") or module.tag,
                            "Languages": "",
                            "Prompt name": "",
                            "Prompt source": "",
                            "Domain prompt TTS": "",
                            "TTS text": "",
                            "Variables": "",
                            "Announcement": "Yes" if announcement else "No",
                        }
                        if part.tag == "filePrompt":
                            if (
                                part.findtext(".//promptSelected") or "true"
                            ).lower() == "false":
                                continue
                            name = part.findtext(".//name")
                            if not name:
                                raise ValueError(
                                    "File prompt has no name in IVR {!r}, module {!r}".format(
                                        script_name, row["Module name"]
                                    )
                                )
                            prompt = prompt_by_name.get(name)
                            row["Prompt name"] = name
                            row["Prompt source"] = (
                                "Domain prompt"
                                if prompt is not None
                                else "Not in getPrompts"
                            )
                            if prompt is not None:
                                row["Languages"] = _languages(
                                    _value(prompt, "languages")
                                )
                                prompt_type = _value(prompt, "promptType") or _value(
                                    prompt, "type"
                                )
                                if isinstance(prompt_type, str):
                                    if prompt_type.upper() in (
                                        "TTSGENERATED",
                                        "TTS",
                                        "TEXT_TO_SPEECH",
                                    ):
                                        row["Domain prompt TTS"] = "Yes"
                                    elif prompt_type.upper() in (
                                        "PRERECORDED",
                                        "WAV",
                                        "FILE",
                                        "AUDIO",
                                    ):
                                        row["Domain prompt TTS"] = "No"
                                tts_text = _value(prompt, "ttsText")
                                if tts_text:
                                    if not isinstance(tts_text, str):
                                        raise ValueError(
                                            "Unexpected getPrompts ttsText value"
                                        )
                                    row["TTS text"] = tts_text
                                    row["Domain prompt TTS"] = "Yes"
                        else:
                            encoded = part.findtext("xml")
                            if not encoded:
                                raise ValueError(
                                    "TTS prompt has no XML in IVR {!r}, module {!r}".format(
                                        script_name, row["Module name"]
                                    )
                                )
                            fragments = decode_tts(encoded)
                            if not fragments:
                                raise ValueError(
                                    "Cannot decode TTS in IVR {!r}, module {!r}".format(
                                        script_name, row["Module name"]
                                    )
                                )
                            row["Prompt source"] = "IVR-only TTS"
                            row["TTS text"] = " ".join(fragments)
                            row["Variables"] = ", ".join(
                                fragment[1:-1]
                                for fragment in fragments
                                if fragment.startswith("{") and fragment.endswith("}")
                            )
                            row["Languages"] = part.findtext("language") or ""
                        rows.append(row)
    return rows


def write_inventory(path, rows):
    """Write a private CSV, refusing to replace an existing report."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(prefix=".ivr-prompts-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(
                {key: _csv_cell(row[key]) for key in COLUMNS} for row in rows
            )
        os.link(temporary_path, path)
    finally:
        os.unlink(temporary_path)


def capture_inventory(client, output_path, exclude_announcements=False):
    """Retrieve the two read-only API datasets and write a local report."""
    if Path(output_path).exists():
        raise FileExistsError("Report already exists: {}".format(output_path))
    prompts = client.service.getPrompts()
    ivrs = client.service.getIVRScripts()
    if prompts is None or ivrs is None:
        raise ValueError("getPrompts or getIVRScripts returned no response")
    rows = inventory_rows(
        client.domain_name,
        prompts,
        ivrs,
        exclude_announcements=exclude_announcements,
    )
    write_inventory(output_path, rows)
    return len(rows)
