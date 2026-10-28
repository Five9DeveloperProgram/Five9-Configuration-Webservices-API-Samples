"""Push campaign profiles and their filters from a domain snapshot to a domain.

Works with any snapshot produced by ``domain_config_capture.py``. Profiles are
selected by name: a profile is included when its name contains ANY of the
``--match`` words (case-insensitive).

The run is a DRY RUN unless ``--apply`` is given. A dry run still logs in to the
target domain, but only reads from it, and prints what would be created,
updated or skipped. You are always prompted for the target username and
password (never taken from stored aliases) so you cannot push to the wrong
domain by accident. Before anything is written you must retype the connected
domain's name.

By default existing profiles are never modified. Add ``--overwrite-existing`` to
update profiles that already exist in the target but differ from the snapshot.

Examples:

    # dry run
    python -m examples.domain_config.push_campaign_profiles \
        --snapshot "domain_snapshots/My Domain" \
        --match Business Technology Healthcare Other

    # do it for real after reviewing the dry run
    python -m examples.domain_config.push_campaign_profiles \
        --snapshot "domain_snapshots/My Domain" \
        --match Business Technology Healthcare Other --apply
"""

import argparse
import getpass
import logging
from collections import Counter

import requests
import zeep
from zeep.helpers import serialize_object

from five9.five9_session import Five9Client, Five9ClientCreationError
from five9.utils.campaign_profile_sync import (
    ACTION_CREATE,
    ACTION_UPDATE,
    criteria_for_write,
    filters_match,
    load_snapshot,
    plan_profile,
    select_profiles,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--snapshot",
        required=True,
        help="Snapshot folder, e.g. domain_snapshots/<domain>",
    )
    parser.add_argument(
        "--match",
        nargs="+",
        required=True,
        metavar="WORD",
        help="Include profiles whose name contains any of these words",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write to the target domain (without this the run is read-only)",
    )
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Update existing profiles whose settings or filter differ",
    )
    parser.add_argument(
        "--hostalias",
        choices=("us", "ca", "eu", "frk", "in"),
        default="us",
        help="Five9 API region of the target domain (default: us)",
    )
    return parser.parse_args()


def connect(hostalias):
    username = input("Target Five9 Username: ")
    password = getpass.getpass("Target Five9 Password: ")
    return Five9Client(
        five9username=username, five9password=password, api_hostname_alias=hostalias
    )


def as_list(response):
    if not response:
        return []
    return response if isinstance(response, list) else [response]


def get_filter(client, name):
    response = client.throttled_service.getCampaignProfileFilter(profileName=name)
    return serialize_object(response, dict) or {}


def replace_filter(client, name, wanted_filter, existing_filter):
    """Replace the filter in one call, then read it back to verify."""
    request = {
        "profileName": name,
        "grouping": wanted_filter["grouping"],
        "addCriteria": criteria_for_write(wanted_filter["crmCriteria"]),
    }
    existing_criteria = existing_filter.get("crmCriteria") or []
    if existing_criteria:
        request["removeCriteria"] = criteria_for_write(existing_criteria)
    client.throttled_service.modifyCampaignProfileCrmCriteria(**request)
    if not filters_match(wanted_filter, get_filter(client, name)):
        raise RuntimeError(f"filter read-back did not match for {name}")


def push_profile(client, action, profile, profile_filter, existing_filter):
    if action == ACTION_CREATE:
        client.throttled_service.createCampaignProfile(campaignProfile=profile)
    else:
        client.throttled_service.modifyCampaignProfile(profile)
    if profile_filter.get("crmCriteria"):
        replace_filter(client, profile["name"], profile_filter, existing_filter)


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    profiles, filters = load_snapshot(args.snapshot)
    selected = select_profiles(profiles, args.match)
    if not selected:
        raise ValueError(f"no profiles in the snapshot match {args.match}")
    missing = [p["name"] for p in selected if p["name"] not in filters]
    if missing:
        raise ValueError(
            f"{len(missing)} selected profile(s) have no filter file in the snapshot, "
            f"e.g. {missing[0]!r}; recapture the snapshot first"
        )
    logging.info("%d of %d snapshot profiles selected", len(selected), len(profiles))

    client = connect(args.hostalias)
    logging.info("Connected to target domain: %s", client.domain_name)
    target = {
        serialize_object(p, dict)["name"]: serialize_object(p, dict)
        for p in as_list(client.throttled_service.getCampaignProfiles())
    }

    plan = []
    for profile in selected:
        name = profile["name"]
        actual = target.get(name)
        actual_filter = get_filter(client, name) if actual else None
        action, differences = plan_profile(
            profile, filters[name], actual, actual_filter, args.overwrite_existing
        )
        plan.append((profile, action, actual_filter))
        suffix = f" [{', '.join(differences)}]" if differences else ""
        logging.info("%-60s %s%s", name, action, suffix)

    counts = Counter(action for _, action, _ in plan)
    logging.info("Summary for %s: %s", client.domain_name, dict(counts))

    if not args.apply:
        logging.info("Dry run complete; nothing was written. Rerun with --apply.")
        return

    to_write = [item for item in plan if item[1] in (ACTION_CREATE, ACTION_UPDATE)]
    if not to_write:
        logging.info("Nothing to write.")
        return
    logging.warning(
        "About to write %d campaign profile(s) to domain %s",
        len(to_write),
        client.domain_name,
    )
    if (
        input("Retype the connected domain name to continue: ").strip()
        != client.domain_name
    ):
        raise SystemExit("aborted, domain not confirmed")

    failures = []
    for profile, action, actual_filter in to_write:
        name = profile["name"]
        try:
            push_profile(client, action, profile, filters[name], actual_filter or {})
            logging.info("%s: %s done and verified", name, action)
        except Exception as error:  # keep going; report at the end
            logging.error("%s: %s failed: %s", name, action, error)
            failures.append(name)
    if failures:
        raise SystemExit(f"{len(failures)} profile(s) failed: {', '.join(failures)}")


if __name__ == "__main__":
    try:
        main()
    except (
        Five9ClientCreationError,
        requests.RequestException,
        zeep.exceptions.Fault,
    ) as error:
        raise SystemExit(f"Five9 request failed: {error}") from error
    except ValueError as error:
        raise SystemExit(str(error)) from error
