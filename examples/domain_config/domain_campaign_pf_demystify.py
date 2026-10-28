"""Fetch and demystify selected campaign profile filters from Five9.

The script lists campaign profile summaries once, filters those names locally,
and retrieves full filter definitions only for the matches. It is read-only.
"""

import getpass
import json
import os

from zeep.exceptions import Fault
from zeep.helpers import serialize_object

from five9 import five9_session
from five9.utils.campaign_profile_comprehension import demystify_filter
from five9.utils.common import common_parser_arguments, create_five9_client

DEFAULT_NAME_TERMS = ["Business", "Technology", "Healthcare", "Other"]


def select_profile_names(profiles, terms):
    """Return profile names containing any term, matched case-insensitively."""
    normalized_terms = [term.casefold() for term in terms]
    return sorted(
        profile.name
        for profile in profiles or []
        if any(term in profile.name.casefold() for term in normalized_terms)
    )


def connect(args):
    if args.prompt:
        username = input("Five9 Username: ")
        password = getpass.getpass("Five9 Password: ")
        return five9_session.Five9Client(
            five9username=username,
            five9password=password,
            api_hostname_alias=args.hostalias,
        )
    return create_five9_client(args)


def write_profile(output_dir, profile_name, profile_filter, verbose=False):
    filter_dir = os.path.join(output_dir, "campaign_profile_filters")
    demystified_dir = os.path.join(output_dir, "campaign_profile_filters_demystified")
    os.makedirs(filter_dir, exist_ok=True)
    os.makedirs(demystified_dir, exist_ok=True)

    with open(os.path.join(filter_dir, f"{profile_name}.json"), "w") as handle:
        json.dump(profile_filter, handle, sort_keys=True, indent=4)

    grouping = profile_filter.get("grouping") or {}
    criteria = profile_filter.get("crmCriteria") or []
    if grouping.get("type") == "Custom" and criteria:
        demystified = demystify_filter(profile_filter, verbose=verbose)
        with open(os.path.join(demystified_dir, f"{profile_name}.sql"), "w") as handle:
            handle.write(demystified)


def profile_definition_path(output_dir, profile_name):
    return os.path.join(output_dir, "campaign_profile_filters", f"{profile_name}.json")


def main():
    args = common_parser_arguments(
        additional_args=[
            {
                "name": "--name-contains",
                "action": "append",
                "dest": "name_terms",
                "help": (
                    "case-insensitive profile-name substring; repeat for multiple "
                    "terms (default: Business, Technology, Healthcare, Other)"
                ),
            },
            {
                "name": "--output-dir",
                "default": os.path.join("scratch", "campaign_profile_research"),
                "help": "base output directory",
            },
            {
                "name": "--prompt",
                "action": "store_true",
                "help": "prompt for username and hidden password",
            },
            {
                "name": "--verbose",
                "action": "store_true",
                "help": "show detailed demystification output",
            },
            {
                "name": "--resume",
                "action": "store_true",
                "help": "skip profiles whose JSON definition already exists",
            },
        ]
    )

    terms = args.name_terms or DEFAULT_NAME_TERMS
    client = connect(args)
    domain_name = client.service.getVCCConfiguration().domainName
    profiles = client.service.getCampaignProfiles()
    profile_names = select_profile_names(profiles, terms)

    print(f"Connected domain: {domain_name}")
    print(f"Matched {len(profile_names)} campaign profiles:")
    for profile_name in profile_names:
        print(f"  {profile_name}")

    output_dir = os.path.join(args.output_dir, domain_name)
    fetched = 0
    skipped = 0
    failures = {}
    for index, profile_name in enumerate(profile_names, 1):
        if args.resume and os.path.exists(
            profile_definition_path(output_dir, profile_name)
        ):
            skipped += 1
            print(f"[{index}/{len(profile_names)}] Already fetched: {profile_name}")
            continue

        print(f"[{index}/{len(profile_names)}] Fetching: {profile_name}")
        try:
            response = client.throttled_service.getCampaignProfileFilter(
                profileName=profile_name
            )
        except Fault as error:
            failures[profile_name] = str(error)
            print(f"    Skipped: {error}")
            continue

        profile_filter = serialize_object(response, dict)
        write_profile(output_dir, profile_name, profile_filter, args.verbose)
        fetched += 1

    failure_path = os.path.join(output_dir, "failed_profiles.json")
    if failures:
        with open(failure_path, "w") as handle:
            json.dump(failures, handle, sort_keys=True, indent=4)
    elif os.path.exists(failure_path):
        os.remove(failure_path)

    print(f"\nWrote fresh definitions to {os.path.abspath(output_dir)}")
    print(f"Fetched: {fetched}; already present: {skipped}; failed: {len(failures)}")
    if failures:
        print(f"Failures were saved to {os.path.abspath(failure_path)}")


if __name__ == "__main__":
    main()
