"""Helpers for copying campaign profiles and their filters between domains.

The functions here are pure (no API calls) so they can be unit tested offline.
``examples/domain_config/push_campaign_profiles.py`` wires them to a live client.

A domain snapshot (see ``Five9DomainConfig``) stores:

* ``getCampaignProfiles.json`` - a list of campaign profile objects
* ``campaign_profile_filters/<profile name>.json`` - each profile's filter
  (``crmCriteria`` rows plus a ``grouping`` expression)
"""

import copy
import json
from pathlib import Path

from five9.utils.campaign_profile_comprehension import criterion_key

ACTION_CREATE = "create"
ACTION_UPDATE = "update"
ACTION_SKIP_IDENTICAL = "skip (already identical)"
ACTION_SKIP_EXISTS = "skip (exists and differs; use --overwrite-existing)"


def select_profiles(profiles, patterns):
    """Profiles whose name contains any pattern (case-insensitive substring)."""
    lowered = [pattern.lower() for pattern in patterns]
    return [
        profile
        for profile in profiles
        if any(pattern in profile["name"].lower() for pattern in lowered)
    ]


def load_snapshot(snapshot_dir):
    """Returns ``(profiles, filters_by_name)`` from a domain snapshot folder."""
    snapshot_dir = Path(snapshot_dir)
    profiles_path = snapshot_dir / "getCampaignProfiles.json"
    if not profiles_path.is_file():
        raise ValueError(f"{profiles_path} not found; is this a domain snapshot?")
    profiles = json.loads(profiles_path.read_text(encoding="utf-8"))
    filters = {}
    for path in (snapshot_dir / "campaign_profile_filters").glob("*.json"):
        filters[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return profiles, filters


def _drop_none(value):
    if isinstance(value, dict):
        return {k: _drop_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_drop_none(item) for item in value]
    return value


def profile_differences(wanted, actual):
    """Top-level profile fields whose values differ (None values ignored)."""
    wanted, actual = _drop_none(wanted), _drop_none(actual)
    return sorted(
        key for key in set(wanted) | set(actual) if wanted.get(key) != actual.get(key)
    )


def _comparable_criteria(profile_filter):
    return [
        (left, operator, right or None)
        for left, operator, right in (
            criterion_key(criterion)
            for criterion in (profile_filter.get("crmCriteria") or [])
        )
    ]


def filters_match(wanted, actual):
    """True when criteria rows and grouping expression are equivalent."""
    wanted_expression = (wanted.get("grouping") or {}).get("expression") or ""
    actual_expression = (actual.get("grouping") or {}).get("expression") or ""
    return (
        _comparable_criteria(wanted) == _comparable_criteria(actual)
        and wanted_expression.split() == actual_expression.split()
    )


def criteria_for_write(criteria):
    """Copy of criteria with ``None`` right values as ``""`` (what the API wants)."""
    writable = copy.deepcopy(criteria)
    for criterion in writable:
        if criterion.get("rightValue") is None:
            criterion["rightValue"] = ""
    return writable


def plan_profile(
    wanted_profile, wanted_filter, actual_profile, actual_filter, overwrite
):
    """Decides what to do for one profile.

    ``actual_profile``/``actual_filter`` are None when the profile does not
    exist in the target. Returns ``(action, differences)`` where differences is
    a list of human-readable strings explaining an update or conflict.
    """
    if actual_profile is None:
        return ACTION_CREATE, []
    differences = [
        f"profile field {key}"
        for key in profile_differences(wanted_profile, actual_profile)
    ]
    if not filters_match(wanted_filter, actual_filter or {}):
        differences.append("filter")
    if not differences:
        return ACTION_SKIP_IDENTICAL, []
    return (ACTION_UPDATE if overwrite else ACTION_SKIP_EXISTS), differences
