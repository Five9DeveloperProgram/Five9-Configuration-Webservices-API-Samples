"""
Audits and heals campaign profile filters that contain duplicate criteria rows.

Duplicate rows were once accepted without complaint. The Admin UI now collapses
them on open, which leaves the saved grouping expression referencing more rows
than the UI recognizes, so the filter throws on save even though it still dials
correctly. This script finds those filters, computes the corrected criteria array
and grouping expression, and can push the correction back through the API.

Auditing is offline and read-only. Pushing requires --apply.

    # audit a captured snapshot
    python -m examples.domain_config.cpf_heal_duplicate_criteria \
        --snapshot "domain_snapshots/Devry University/ivr-documentation/20260724_131056"

    # confirm the API applies a combined remove/add atomically (creates and
    # deletes a scratch profile)
    python -m examples.domain_config.cpf_heal_duplicate_criteria \
        --account_alias devry --probe

    # heal one profile, verifying by read-back
    python -m examples.domain_config.cpf_heal_duplicate_criteria \
        --account_alias devry --profile "oDEM Central Green Day X Friday" --apply
"""

import getpass
import json
import os

import zeep

from five9 import five9_session
from five9.utils.common import common_parser_arguments, create_five9_client
from five9.utils.campaign_profile_comprehension import (
    criterion_key,
    find_duplicate_criteria,
    repair_duplicate_criteria,
)

PROBE_PROFILE_NAME = "zz_probe_duplicate_criteria_healer"


def connect(args):
    """
    Builds a client, preferring an explicit prompt when asked.

    Five9Client silently falls back to ACCOUNTS["default_account"] when it gets
    no username and no alias, which would point a write run at whichever domain
    happens to be configured. --prompt avoids that guessing entirely.
    """
    if args.prompt:
        username = input("Five9 Username: ")
        password = getpass.getpass("Five9 Password: ")
        return five9_session.Five9Client(
            five9username=username,
            five9password=password,
            api_hostname_alias=args.hostalias,
        )
    return create_five9_client(args)


def confirm_domain(client, action):
    """
    Names the connected domain and requires the operator to retype it.

    Writing criteria to the wrong domain would be difficult to notice and
    unpleasant to undo, so this gate stands in front of every write.
    """
    domain_name = client.service.getVCCConfiguration().domainName
    print(f"\n*** about to {action} in domain: {domain_name}")
    typed = input(f"    retype the domain name to continue (or anything else to abort): ")
    if typed.strip() != domain_name:
        raise SystemExit("aborted, domain not confirmed")
    return domain_name


def load_snapshot_filters(snapshot_path):
    folder = os.path.join(snapshot_path, "campaign_profile_filters")
    if not os.path.isdir(folder):
        folder = snapshot_path
    filters = {}
    for filename in sorted(os.listdir(folder)):
        if filename.endswith(".json"):
            with open(os.path.join(folder, filename)) as handle:
                filters[filename[: -len(".json")]] = json.load(handle)
    return filters


def load_live_filters(client, profile_names=None):
    if profile_names is None:
        profile_names = [
            profile["name"] for profile in client.service.getCampaignProfiles()
        ]
    filters = {}
    for name in profile_names:
        response = client.service.getCampaignProfileFilter(profileName=name)
        filters[name] = zeep.helpers.serialize_object(response, dict)
    return filters


def audit(filters):
    """Returns [(profile_name, repair)] for every filter needing a fix."""
    findings = []
    for name in sorted(filters):
        repair = repair_duplicate_criteria(filters[name])
        if repair["changed"]:
            findings.append((name, repair))
    return findings


def describe(name, repair):
    lines = [
        f"{name}",
        f"    rows {repair['rows_before']} -> {repair['rows_after']}"
        f"   equivalent={repair['equivalent']}",
    ]
    for duplicate in repair["duplicates"]:
        left, operator, right = duplicate["key"]
        lines.append(
            f"    duplicate rows {duplicate['drop']} collapse into row "
            f"{duplicate['keep']}:  {left} {operator} {right!r}"
        )
    if repair["renumbered"]:
        shifted = {
            old: new
            for old, new in repair["renumbered"].items()
            if old not in [d for dup in repair["duplicates"] for d in dup["drop"]]
        }
        lines.append(
            f"    rows renumbered by removal: {shifted or 'none (duplicates were trailing)'}"
        )
    lines.append(f"    was: {repair['original_expression']}")
    lines.append(f"    now: {repair['grouping']['expression']}")
    return "\n".join(lines)


def push_repair(client, name, original_filter, repair, verify=True):
    """
    Replaces a profile's criteria and grouping in a single call.

    campaignFilterCriterion has no id, so removeCriteria matches by value and
    cannot single out one of two identical rows. Replacing the whole set in one
    request sidesteps that ambiguity and avoids ever leaving a running campaign
    with an empty criteria set.
    """
    if not repair["equivalent"]:
        raise ValueError(
            f"refusing to push {name}: corrected expression is not provably "
            f"equivalent to the original"
        )

    client.service.modifyCampaignProfileCrmCriteria(
        profileName=name,
        grouping=repair["grouping"],
        removeCriteria=original_filter["crmCriteria"],
        addCriteria=repair["crmCriteria"],
    )

    if not verify:
        return True

    after = zeep.helpers.serialize_object(
        client.service.getCampaignProfileFilter(profileName=name), dict
    )
    expected = [criterion_key(c) for c in repair["crmCriteria"]]
    actual = [criterion_key(c) for c in (after.get("crmCriteria") or [])]
    problems = []
    if actual != expected:
        problems.append(f"criteria mismatch: expected {expected}, got {actual}")
    live_expression = (after.get("grouping") or {}).get("expression") or ""
    if live_expression.split() != repair["grouping"]["expression"].split():
        problems.append(
            f"expression mismatch:\n      expected {repair['grouping']['expression']}"
            f"\n      got      {live_expression}"
        )
    if find_duplicate_criteria(after):
        problems.append("duplicate rows still present after push")

    for problem in problems:
        print(f"    VERIFY FAILED - {problem}")
    return not problems


def probe(client, keep=False):
    """
    Determines whether a combined remove/add call is applied atomically and
    whether addCriteria order becomes row order. Uses a scratch profile so no
    real configuration is touched.
    """
    criteria = [
        {"compareOperator": "Equals", "leftValue": "number1", "rightValue": "111"},
        {"compareOperator": "Equals", "leftValue": "number2", "rightValue": "222"},
        {"compareOperator": "Equals", "leftValue": "number3", "rightValue": "333"},
        {"compareOperator": "NotEqual", "leftValue": "number1", "rightValue": "444"},
    ]
    print(f"creating scratch profile {PROBE_PROFILE_NAME}")
    client.service.createCampaignProfile(
        campaignProfile={
            "name": PROBE_PROFILE_NAME,
            "description": "temporary probe profile, safe to delete",
        }
    )
    try:
        client.service.modifyCampaignProfileCrmCriteria(
            profileName=PROBE_PROFILE_NAME,
            grouping={"expression": "(1 OR 2) AND 3 AND 4", "type": "Custom"},
            addCriteria=criteria,
        )
        seeded = zeep.helpers.serialize_object(
            client.service.getCampaignProfileFilter(profileName=PROBE_PROFILE_NAME),
            dict,
        )
        seeded_order = [criterion_key(c) for c in seeded["crmCriteria"]]
        print(f"  seeded row order matches addCriteria order: "
              f"{seeded_order == [criterion_key(c) for c in criteria]}")

        reordered = [criteria[1], criteria[3], criteria[0]]
        expression = "1 AND (2 OR 3)"
        print("  issuing combined removeCriteria(all) + addCriteria(subset) call")
        client.service.modifyCampaignProfileCrmCriteria(
            profileName=PROBE_PROFILE_NAME,
            grouping={"expression": expression, "type": "Custom"},
            removeCriteria=seeded["crmCriteria"],
            addCriteria=reordered,
        )
        after = zeep.helpers.serialize_object(
            client.service.getCampaignProfileFilter(profileName=PROBE_PROFILE_NAME),
            dict,
        )
        actual = [criterion_key(c) for c in (after.get("crmCriteria") or [])]
        expected = [criterion_key(c) for c in reordered]
        live_expression = (after.get("grouping") or {}).get("expression") or ""
        print(f"  rows after combined call: {actual}")
        print(f"  expected:                 {expected}")
        print(f"  expression after: {live_expression!r} (expected {expression!r})")
        atomic = actual == expected and live_expression.split() == expression.split()
        print(f"\n  PROBE {'PASSED' if atomic else 'FAILED'} - single-call replace "
              f"{'is safe to use' if atomic else 'cannot be trusted; do not --apply'}")
        return atomic
    finally:
        if keep:
            print(f"leaving {PROBE_PROFILE_NAME} in place (--keep_probe)")
        else:
            client.service.deleteCampaignProfile(profileName=PROBE_PROFILE_NAME)
            print(f"deleted scratch profile {PROBE_PROFILE_NAME}")


if __name__ == "__main__":
    args = common_parser_arguments(
        [
            {
                "name": "--snapshot",
                "type": str,
                "default": None,
                "help": "Audit a captured snapshot folder offline instead of a live domain",
            },
            {
                "name": "--profile",
                "type": str,
                "default": None,
                "help": "Limit to a single campaign profile by name",
            },
            {
                "name": "--report",
                "type": str,
                "default": None,
                "help": "Write the audit findings to this JSON path",
            },
            {
                "name": "--apply",
                "action": "store_true",
                "help": "Push corrections. Without this the run is read-only.",
            },
            {
                "name": "--probe",
                "action": "store_true",
                "help": "Test combined remove/add behavior on a scratch profile, then exit",
            },
            {
                "name": "--keep_probe",
                "action": "store_true",
                "help": "Do not delete the scratch profile created by --probe",
            },
            {
                "name": "--prompt",
                "action": "store_true",
                "help": "Always ask for username and password instead of using a "
                        "stored credential. Recommended for domains you do not "
                        "have an alias for.",
            },
        ]
    )

    client = None
    if args.probe:
        client = connect(args)
        confirm_domain(client, f"create and delete the scratch profile {PROBE_PROFILE_NAME}")
        raise SystemExit(0 if probe(client, keep=args.keep_probe) else 1)

    if args.snapshot:
        filters = load_snapshot_filters(args.snapshot)
        if args.profile:
            filters = {k: v for k, v in filters.items() if k == args.profile}
    else:
        client = connect(args)
        filters = load_live_filters(
            client, [args.profile] if args.profile else None
        )

    print(f"\nexamined {len(filters)} campaign profile filter(s)")
    findings = audit(filters)
    print(f"found {len(findings)} needing repair\n")
    for name, repair in findings:
        print(describe(name, repair))
        print()

    unsafe = [name for name, repair in findings if not repair["equivalent"]]
    if unsafe:
        print(f"WARNING - not provably equivalent, will not be pushed: {unsafe}\n")

    if args.report:
        with open(args.report, "w") as handle:
            json.dump(
                {
                    name: {
                        "rows_before": repair["rows_before"],
                        "rows_after": repair["rows_after"],
                        "equivalent": repair["equivalent"],
                        "duplicates": [
                            {
                                "condition": list(d["key"]),
                                "keep": d["keep"],
                                "drop": d["drop"],
                            }
                            for d in repair["duplicates"]
                        ],
                        "original_expression": repair["original_expression"],
                        "corrected_expression": repair["grouping"]["expression"],
                        "corrected_crmCriteria": repair["crmCriteria"],
                        "orderByFields": repair["orderByFields"],
                    }
                    for name, repair in findings
                },
                handle,
                indent=4,
            )
        print(f"report written to {args.report}")

    if not args.apply:
        print("read-only run, nothing pushed. re-run with --apply to push.")
        raise SystemExit(0)

    if args.snapshot:
        raise SystemExit(
            "--apply needs a live connection; re-run without --snapshot so the "
            "current criteria are read from the domain before being replaced."
        )

    pushable = [name for name, repair in findings if repair["equivalent"]]
    if not pushable:
        print("nothing safe to push.")
        raise SystemExit(0)
    confirm_domain(client, f"rewrite criteria for {len(pushable)} profile(s): {pushable}")

    for name, repair in findings:
        if not repair["equivalent"]:
            print(f"SKIPPED {name} (not provably equivalent)")
            continue
        print(f"pushing {name}")
        if push_repair(client, name, filters[name], repair):
            print(f"    verified {name}")
        else:
            raise SystemExit(f"stopping: {name} did not verify after push")
