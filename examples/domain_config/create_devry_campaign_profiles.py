"""Create DeVry campaign profiles from demystified filter definitions.

The script clones ``oDEM National Blue Day 0 Weekday``, changes its name and
generated description, then applies the filter from the matching ``.sql``
file. It defaults to one profile and a dry run. Use ``--all`` only after
spot-checking the first profile, and use ``--apply`` to make changes.

Examples:

    python -m examples.domain_config.create_devry_campaign_profiles
    python -m examples.domain_config.create_devry_campaign_profiles --apply
    python -m examples.domain_config.create_devry_campaign_profiles \
        --profile "oDEM National Green Day X Weekday" --apply
    python -m examples.domain_config.create_devry_campaign_profiles \
        --all --apply --overwrite-existing
    python -m examples.domain_config.create_devry_campaign_profiles \
        --definitions-dir "scratch/oDEM Vertical Dialers" \
        --all --apply --overwrite-existing
"""

import argparse
import copy
import getpass
import logging
from datetime import date
from pathlib import Path

import requests
import zeep
from zeep.helpers import serialize_object

from five9.five9_session import Five9Client, Five9ClientCreationError
from five9.utils.campaign_profile_comprehension import (
    criterion_key,
    remystify_filter,
)


BASE_PROFILE_NAME = "oDEM National Blue Day 0 Weekday"
DEFAULT_PROFILE_NAME = "oDEM Business Aged Holiday"
DEFINITIONS_DIR = (
    Path(__file__).resolve().parents[2] / "scratch" / "oDEM Vertical Dialers"
)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE_NAME,
        help=f"Profile definition to create (default: {DEFAULT_PROFILE_NAME})",
    )
    parser.add_argument(
        "--definitions-dir",
        type=Path,
        default=DEFINITIONS_DIR,
        help=f"Folder containing .sql definitions (default: {DEFINITIONS_DIR})",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Create every .sql definition instead of the selected profile",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create profiles and filters; without this flag the run is read-only",
    )
    parser.add_argument(
        "--resume-existing",
        action="store_true",
        help="Apply the filter to an existing profile only when it has no criteria",
    )
    parser.add_argument(
        "--sync-existing",
        action="store_true",
        help="Update descriptions of existing profiles whose filters match exactly",
    )
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Replace differing existing filters; exact matches are skipped",
    )
    parser.add_argument(
        "--hostalias",
        choices=("us", "ca", "eu", "frk", "in"),
        default="us",
        help="Five9 API region (default: us)",
    )
    return parser.parse_args()


def load_definitions(profile_name=None, definitions_dir=DEFINITIONS_DIR):
    definitions_dir = Path(definitions_dir)
    paths = sorted(definitions_dir.glob("*.sql"))
    if not paths:
        raise ValueError(f"no .sql filter definitions found in {definitions_dir}")
    if profile_name is not None:
        paths = [path for path in paths if path.stem == profile_name]
        if not paths:
            raise ValueError(
                f"no filter definition named {profile_name!r} in {definitions_dir}"
            )

    return {
        path.stem: remystify_filter(path.read_text(encoding="utf-8")) for path in paths
    }


def connect(hostalias):
    username = input("Five9 Username: ")
    password = getpass.getpass("Five9 Password: ")
    return Five9Client(
        five9username=username,
        five9password=password,
        api_hostname_alias=hostalias,
    )


def profile_name(profile):
    if isinstance(profile, dict):
        return profile.get("name")
    return getattr(profile, "name", None)


def comparable_criterion_key(criterion):
    left_value, compare_operator, right_value = criterion_key(criterion)
    return left_value, compare_operator, right_value or None


def criteria_for_write(criteria):
    writable_criteria = copy.deepcopy(criteria)
    for criterion in writable_criteria:
        if criterion.get("rightValue") is None:
            criterion["rightValue"] = ""
    return writable_criteria


def generated_description(created_on=None):
    created_on = created_on or date.today()
    return f"Generated from custom expression processor - {created_on.isoformat()}"


def find_base_profile(profiles):
    for profile in profiles:
        if profile_name(profile) == BASE_PROFILE_NAME:
            return profile
    raise ValueError(f"base campaign profile not found: {BASE_PROFILE_NAME}")


def confirm_domain(client, profile_names):
    domain_name = client.domain_name
    logging.warning(
        "About to create or update %d campaign profile(s) in domain %s using %s as the base",
        len(profile_names),
        domain_name,
        BASE_PROFILE_NAME,
    )
    typed_name = input(
        "Retype the connected domain name to continue (anything else aborts): "
    )
    if typed_name.strip() != domain_name:
        raise SystemExit("aborted, domain not confirmed")


def filters_match(actual_filter, expected_filter):
    expected_criteria = [
        comparable_criterion_key(criterion)
        for criterion in expected_filter["crmCriteria"]
    ]
    actual_criteria = [
        comparable_criterion_key(criterion)
        for criterion in (actual_filter.get("crmCriteria") or [])
    ]
    expected_expression = expected_filter["grouping"]["expression"].split()
    actual_expression = (actual_filter.get("grouping") or {}).get("expression") or ""
    return (
        actual_criteria == expected_criteria
        and actual_expression.split() == expected_expression
    )


def verify_filter(client, name, expected_filter):
    return filters_match(get_serialized_filter(client, name), expected_filter)


def get_serialized_filter(client, name):
    response = client.throttled_service.getCampaignProfileFilter(profileName=name)
    return serialize_object(response, dict)


def replace_filter(client, name, profile_filter, existing_criteria=None):
    expected_criteria = profile_filter["crmCriteria"]
    existing_criteria = existing_criteria or []
    try:
        request = {
            "profileName": name,
            "grouping": profile_filter["grouping"],
            "addCriteria": criteria_for_write(expected_criteria),
        }
        if existing_criteria:
            request["removeCriteria"] = criteria_for_write(existing_criteria)
        client.throttled_service.modifyCampaignProfileCrmCriteria(**request)
    except Exception:
        logging.exception(
            "Atomic filter replacement failed for profile %s; stopping",
            name,
        )
        raise

    if not verify_filter(client, name, profile_filter):
        raise RuntimeError(
            f"filter verification failed for newly created profile {name}"
        )


def apply_filter(client, name, profile_filter, existing_criteria=None):
    existing_criteria = existing_criteria or []
    existing_keys = [
        comparable_criterion_key(criterion) for criterion in existing_criteria
    ]
    expected_prefix = [
        comparable_criterion_key(criterion)
        for criterion in profile_filter["crmCriteria"][: len(existing_criteria)]
    ]
    if existing_keys != expected_prefix:
        raise ValueError(
            f"existing criteria on {name} do not match the expected filter prefix"
        )
    replace_filter(client, name, profile_filter, existing_criteria)


def create_profile(client, base_profile, name, profile_filter, created_on=None):
    new_profile = copy.deepcopy(serialize_object(base_profile, dict))
    new_profile["name"] = name
    new_profile["description"] = generated_description(created_on)
    client.throttled_service.createCampaignProfile(campaignProfile=new_profile)
    apply_filter(client, name, profile_filter, existing_criteria=[])


def update_profile_description(client, profile, created_on=None):
    updated_profile = copy.deepcopy(serialize_object(profile, dict))
    updated_profile["description"] = generated_description(created_on)
    client.throttled_service.modifyCampaignProfile(updated_profile)


def main():
    args = parse_args()
    existing_modes = [
        args.resume_existing,
        args.sync_existing,
        args.overwrite_existing,
    ]
    if sum(existing_modes) > 1:
        raise ValueError(
            "use only one of --resume-existing, --sync-existing, or "
            "--overwrite-existing"
        )
    definitions = load_definitions(
        None if args.all else args.profile,
        definitions_dir=args.definitions_dir,
    )
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logging.info(
        "Loaded %d validated filter definition(s): %s",
        len(definitions),
        ", ".join(definitions),
    )

    client = connect(args.hostalias)
    profiles = client.throttled_service.getCampaignProfiles() or []
    if not isinstance(profiles, list):
        profiles = [profiles]
    base_profile = find_base_profile(profiles)
    profiles_by_name = {profile_name(profile): profile for profile in profiles}
    existing_names = set(profiles_by_name)
    collisions = sorted(existing_names.intersection(definitions))
    if collisions and not any(existing_modes):
        raise ValueError(
            "refusing to overwrite existing campaign profile(s): "
            + ", ".join(collisions)
        )
    existing_filters = {}
    matching_existing = set()
    if args.sync_existing or args.overwrite_existing:
        mismatched_profiles = []
        for name in collisions:
            existing_filter = get_serialized_filter(client, name)
            existing_filters[name] = existing_filter
            if filters_match(existing_filter, definitions[name]):
                matching_existing.add(name)
            else:
                mismatched_profiles.append(name)
        if args.sync_existing and mismatched_profiles:
            raise ValueError(
                "refusing to sync existing profiles whose filters do not exactly "
                "match their definitions: " + ", ".join(mismatched_profiles)
            )
    if args.resume_existing:
        missing_profiles = sorted(set(definitions).difference(existing_names))
        if missing_profiles:
            raise ValueError(
                "--resume-existing requires every selected profile to exist: "
                + ", ".join(missing_profiles)
            )
        for name in definitions:
            existing_filter = get_serialized_filter(client, name)
            existing_filters[name] = existing_filter
            existing_criteria = existing_filter.get("crmCriteria") or []
            expected_criteria = definitions[name]["crmCriteria"]
            actual_keys = [
                comparable_criterion_key(criterion) for criterion in existing_criteria
            ]
            expected_keys = [
                comparable_criterion_key(criterion)
                for criterion in expected_criteria[: len(existing_criteria)]
            ]
            if actual_keys != expected_keys:
                raise ValueError(
                    f"refusing to resume {name}: existing criteria do not match "
                    "the expected prefix"
                )

    for name, profile_filter in definitions.items():
        if name in matching_existing and args.overwrite_existing:
            logging.info("%s: existing filter already matches; skip", name)
        elif name in collisions and args.overwrite_existing:
            logging.info(
                "%s: replace existing filter with %d criteria",
                name,
                len(profile_filter["crmCriteria"]),
            )
        elif name in collisions and args.sync_existing:
            logging.info("%s: matching filter; update generated description", name)
        else:
            logging.info(
                "%s: clone base profile and apply %d criteria",
                name,
                len(profile_filter["crmCriteria"]),
            )

    if not args.apply:
        logging.info("Dry run complete; rerun with --apply to create these profiles")
        return

    confirm_domain(client, definitions)
    for name, profile_filter in definitions.items():
        if name in matching_existing and args.overwrite_existing:
            logging.info("Skipped matching profile %s", name)
        elif name in collisions and args.overwrite_existing:
            replace_filter(
                client,
                name,
                profile_filter,
                existing_filters[name].get("crmCriteria") or [],
            )
            update_profile_description(client, profiles_by_name[name])
            logging.info("Updated and verified %s", name)
        elif name in collisions and args.sync_existing:
            update_profile_description(client, profiles_by_name[name])
            logging.info("Updated description for %s", name)
        elif args.resume_existing:
            apply_filter(
                client,
                name,
                profile_filter,
                existing_filters[name].get("crmCriteria") or [],
            )
            logging.info("Updated and verified %s", name)
        else:
            create_profile(client, base_profile, name, profile_filter)
            logging.info("Created and verified %s", name)


if __name__ == "__main__":
    try:
        main()
    except (
        Five9ClientCreationError,
        requests.RequestException,
        zeep.exceptions.Fault,
    ) as error:
        raise SystemExit(f"Five9 request failed: {error}") from error
    except (ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from error
