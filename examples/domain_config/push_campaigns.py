"""Push outbound campaigns from a domain snapshot to another domain.

Works with any snapshot produced by ``domain_config_capture.py``. Campaigns are
selected by name: a campaign is included when its name contains ANY of the
``--match`` words (case-insensitive). Only OUTBOUND campaigns are supported.

Push the campaign profiles first (``push_campaign_profiles.py``): each
campaign points at a profile by name, and the dry run reports any campaign whose
profile does not exist in the target.

The run is a DRY RUN unless ``--apply`` is given. A dry run still logs in to the
target domain, but only reads from it. You are always prompted for the target
username and password (never taken from stored aliases), and before anything is
written you must retype the connected domain's name.

New campaigns are created without a run state, so they are NOT started; start
them in the Five9 Admin UI when you are ready. Existing campaigns are never
modified. The snapshot does not capture a campaign's dispositions, skills, lists
or schedules; attach those in the target separately.

Examples:

    # dry run
    python -m examples.domain_config.push_campaigns \
        --snapshot "domain_snapshots/My Domain" \
        --match Business Technology Healthcare Other

    # do it for real after reviewing the dry run
    python -m examples.domain_config.push_campaigns \
        --snapshot "domain_snapshots/My Domain" \
        --match Business Technology Healthcare Other --apply
"""

import argparse
import getpass
import json
import logging
from pathlib import Path

import requests
import zeep
from zeep.helpers import serialize_object

from five9.five9_session import Five9Client, Five9ClientCreationError
from five9.utils.campaign_profile_sync import select_profiles

READ_ONLY_FIELDS = ("state",)


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--snapshot", required=True, help="Snapshot folder")
    parser.add_argument(
        "--match",
        nargs="+",
        required=True,
        metavar="WORD",
        help="Include campaigns whose name contains any of these words",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Write to the target (default: read-only)"
    )
    parser.add_argument(
        "--hostalias",
        choices=("us", "ca", "eu", "frk", "in"),
        default="us",
        help="Five9 API region of the target domain (default: us)",
    )
    return parser.parse_args()


def load_campaigns(snapshot_dir):
    """Returns the full outbound campaign definitions stored in the snapshot."""
    folder = Path(snapshot_dir) / "campaigns_outbound"
    if not folder.is_dir():
        raise ValueError(f"{folder} not found; is this a domain snapshot?")
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(folder.glob("*.json"))
    ]


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


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    campaigns = load_campaigns(args.snapshot)
    selected = select_profiles(campaigns, args.match)
    if not selected:
        raise ValueError(f"no outbound campaigns in the snapshot match {args.match}")
    logging.info("%d of %d outbound campaigns selected", len(selected), len(campaigns))

    client = connect(args.hostalias)
    domain = client.domain_name
    logging.info("Connected to target domain: %s", domain)
    service = client.throttled_service
    existing = {
        serialize_object(c, dict)["name"]
        for c in as_list(service.getCampaigns(campaignType="OUTBOUND"))
    }
    profiles = {
        serialize_object(p, dict)["name"]
        for p in as_list(service.getCampaignProfiles())
    }

    to_create = []
    for campaign in selected:
        name, profile = campaign["name"], campaign.get("profileName")
        if name in existing:
            logging.info("%-45s skip (already exists; never modified)", name)
        elif profile and profile not in profiles:
            logging.error("%-45s skip (profile %r missing in target)", name, profile)
        else:
            logging.info("%-45s create (profile: %s)", name, profile)
            to_create.append(campaign)
    logging.info("%d campaign(s) would be created in %s", len(to_create), domain)

    if not args.apply:
        logging.info("Dry run complete; nothing was written. Rerun with --apply.")
        return
    if not to_create:
        logging.info("Nothing to write.")
        return

    logging.warning(
        "About to create %d campaign(s) in domain %s", len(to_create), domain
    )
    if input("Retype the connected domain name to continue: ").strip() != domain:
        raise SystemExit("aborted, domain not confirmed")

    for campaign in to_create:
        payload = {k: v for k, v in campaign.items() if k not in READ_ONLY_FIELDS}
        try:
            service.createOutboundCampaign(campaign=payload)
        except Exception as error:
            # Stop on the first failure so one bad payload isn't repeated 16 times.
            raise SystemExit(f"{campaign['name']}: create failed: {error}") from error
        logging.info("%s: created", campaign["name"])


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
