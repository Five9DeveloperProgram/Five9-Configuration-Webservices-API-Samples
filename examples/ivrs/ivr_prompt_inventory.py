"""Export an IVR prompt/TTS inventory as a local, Excel-readable CSV.

Uses read-only getPrompts and getIVRScripts; does not write raw IVR XML.
Run from the repository root, for example:

    python examples/ivrs/ivr_prompt_inventory.py --account_alias default_account

The report defaults to private/ivr_prompt_inventory.csv. An existing report
is never overwritten; use --output with a new filename for another capture.
"""

import logging

from five9.utils.common import common_parser_arguments, create_five9_client
from five9.utils.ivr_prompt_inventory import capture_inventory


if __name__ == "__main__":
    args = common_parser_arguments(
        additional_args=[
            {
                "name": "--output",
                "default": "private/ivr_prompt_inventory.csv",
                "help": "Local CSV path (default: private/ivr_prompt_inventory.csv)",
            },
            {
                "name": "--exclude-announcements",
                "action": "store_true",
                "help": "Omit modules or prompt nodes marked as announcements",
            },
        ]
    )
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    client = create_five9_client(args)
    count = capture_inventory(client, args.output, args.exclude_announcements)
    logging.info("Wrote %d prompt occurrences to %s", count, args.output)
