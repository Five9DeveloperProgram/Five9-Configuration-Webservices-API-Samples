"""
Generate styled SVG call-flow diagrams (and Markdown prompt summaries) for the
IVR scripts in a Five9 domain.

This pulls IVR scripts with ``getIVRScripts`` and renders each one's
``xmlDefinition`` into:
  - ``<name>.svg`` -- a styled call-flow diagram. Pass the SVG verbatim to
    Lucidchart via the Lucid connector's ``lucid_convert_svg_to_diagram`` tool.
  - ``<name>.md``  -- a human-readable, diff-friendly summary of each module's
    decoded TTS prompts and its branch transitions.

Output is written to ``<base-dir>/<Five9 domain name>/ivr-documentation/<timestamp>/`` (base dir
defaults to ``private``, which is git-ignored).

Usage:
    python examples/ivr_generate_diagrams.py --account_alias default_account
    python examples/ivr_generate_diagrams.py --account_alias default_account \\
        --base-dir private --name-pattern "^Main"
"""

import os
import re
from datetime import datetime

from five9.utils.common import common_parser_arguments, create_five9_client
from five9.utils import ivr_diagram

if __name__ == "__main__":
    args = common_parser_arguments(
        additional_args=[
            {
                "name": "--base-dir",
                "type": str,
                "default": "private",
                "help": "Base directory for output; a subfolder named for the "
                        "Five9 domain is created inside it (default: private)",
            },
            {
                "name": "--name-pattern",
                "type": str,
                "default": ".*",
                "help": "Regex to filter IVR script names (default: all scripts)",
            },
        ]
    )

    client = create_five9_client(args)

    domain_name = client.service.getVCCConfiguration().domainName
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(args.base_dir, domain_name, "ivr-documentation", timestamp)

    name_pattern = re.compile(args.name_pattern)
    os.makedirs(output_dir, exist_ok=True)

    ivrs = client.service.getIVRScripts()
    print(f"Retrieved {len(ivrs)} IVR scripts")

    generated = 0
    for ivr in ivrs:
        if not name_pattern.search(ivr.name):
            continue
        target = os.path.join(output_dir, ivr.name)
        try:
            with open(f"{target}.svg", "w") as svg_file:
                svg_file.write(ivr_diagram.ivr_to_svg(ivr.xmlDefinition, name=ivr.name))
            with open(f"{target}.md", "w") as md_file:
                md_file.write(ivr_diagram.ivr_to_text(ivr.xmlDefinition, name=ivr.name))
            generated += 1
            print(f"\t{ivr.name}")
        except Exception as e:
            print(f"\tskipped {ivr.name}: {e}")

    print(f"\nWrote diagrams for {generated} IVR scripts to {output_dir}/")
