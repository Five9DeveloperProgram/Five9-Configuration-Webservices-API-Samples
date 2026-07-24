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

from five9.utils.common import common_parser_arguments, create_five9_client
from five9.utils import ivr_diagram

if __name__ == "__main__":
    # Reuse shared Five9 auth/datacenter CLI args and add script-specific
    # output controls on top.
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

    # Standard client bootstrap used throughout the sample repository.
    client = create_five9_client(args)

    summary = ivr_diagram.capture_domain_ivrs(
        client,
        base_dir=args.base_dir,
        name_pattern=args.name_pattern,
    )

    print(f"Retrieved {summary['retrieved']} IVR scripts")
    print(
        f"Wrote diagrams for {summary['generated']} IVR scripts to "
        f"{summary['output_dir']}/"
    )
