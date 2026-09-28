"""
Bulk updates campaign profile dialing schedule stop times.

By default this script runs in read-only mode and prints the proposed changes.
Use --apply to push the updated campaign profile objects back through
modifyCampaignProfile.

Examples:

    python -m examples.domain_config.bulk_update_campaign_profile_stop_time \
        --account_alias default_account

    python -m examples.domain_config.bulk_update_campaign_profile_stop_time \
        --account_alias default_account --apply

    python -m examples.domain_config.bulk_update_campaign_profile_stop_time \
        --account_alias default_account --name-pattern '^Outbound' --hours 20
"""

import re

from five9.utils.common import common_parser_arguments, create_five9_client


def timer_to_dict(timer_value):
    if timer_value is None:
        return None
    if isinstance(timer_value, dict):
        return {
            "days": timer_value.get("days", 0),
            "hours": timer_value.get("hours", 0),
            "minutes": timer_value.get("minutes", 0),
            "seconds": timer_value.get("seconds", 0),
        }
    return {
        "days": getattr(timer_value, "days", 0),
        "hours": getattr(timer_value, "hours", 0),
        "minutes": getattr(timer_value, "minutes", 0),
        "seconds": getattr(timer_value, "seconds", 0),
    }


def format_timer(timer_value):
    timer_dict = timer_to_dict(timer_value)
    if not timer_dict:
        return "None"
    return (
        f"{timer_dict['days']}d "
        f"{timer_dict['hours']:02d}:"
        f"{timer_dict['minutes']:02d}:"
        f"{timer_dict['seconds']:02d}"
    )


def apply_timer_values(stop_time, target_stop_time):
    if stop_time is None:
        return dict(target_stop_time)

    stop_time.days = target_stop_time["days"]
    stop_time.hours = target_stop_time["hours"]
    stop_time.minutes = target_stop_time["minutes"]
    stop_time.seconds = target_stop_time["seconds"]
    return stop_time


def collect_stop_time_updates(profile, schedule_number, target_stop_time):
    dialing_schedule = getattr(profile, "dialingSchedule", None)
    number_schedules = getattr(dialing_schedule, "dialingSchedules", None) or []
    updates = []

    for schedule in number_schedules:
        if getattr(schedule, "number", None) != schedule_number:
            continue

        existing_stop_time = timer_to_dict(getattr(schedule, "stopTime", None))
        if existing_stop_time != target_stop_time:
            updates.append(
                {
                    "number": getattr(schedule, "number", None),
                    "before": existing_stop_time,
                    "after": dict(target_stop_time),
                }
            )
            schedule.stopTime = apply_timer_values(schedule.stopTime, target_stop_time)

    return updates


def main():
    args = common_parser_arguments(
        [
            {
                "name": "--name-pattern",
                "type": str,
                "default": ".*",
                "help": "Regex used to filter campaign profile names",
            },
            {
                "name": "--apply",
                "action": "store_true",
                "help": "Push changes with modifyCampaignProfile instead of dry-run only",
            },
            {
                "name": "--number",
                "type": str,
                "default": "Primary",
                "help": "Dialing schedule number to update, such as Primary or Alt1",
            },
            {
                "name": "--days",
                "type": int,
                "default": 0,
                "help": "Target stop time day component",
            },
            {
                "name": "--hours",
                "type": int,
                "default": 21,
                "help": "Target stop time hour component",
            },
            {
                "name": "--minutes",
                "type": int,
                "default": 0,
                "help": "Target stop time minute component",
            },
            {
                "name": "--seconds",
                "type": int,
                "default": 0,
                "help": "Target stop time second component",
            },
        ]
    )

    client = create_five9_client(args)
    name_pattern = re.compile(args.name_pattern)
    profiles = client.service.getCampaignProfiles() or []
    if not isinstance(profiles, list):
        profiles = [profiles]
    target_stop_time = {
        "days": args.days,
        "hours": args.hours,
        "minutes": args.minutes,
        "seconds": args.seconds,
    }

    matched_profiles = 0
    changed_profiles = 0
    changed_schedules = 0

    for profile in profiles:
        profile_name = getattr(profile, "name", None) or "<unnamed>"
        if not name_pattern.search(profile_name):
            continue

        matched_profiles += 1
        updates = collect_stop_time_updates(profile, args.number, target_stop_time)
        if not updates:
            continue

        changed_profiles += 1
        changed_schedules += len(updates)

        print(f"{profile_name}")
        for update in updates:
            print(
                f"  {update['number']}: {format_timer(update['before'])} "
                f"-> {format_timer(update['after'])}"
            )

        if args.apply:
            client.service.modifyCampaignProfile(profile)
            print("  applied")
        else:
            print("  dry-run only")

    print(
        f"matched {matched_profiles} profiles, updated {changed_profiles} profiles, "
        f"updated {changed_schedules} dialing schedules"
    )

    if not args.apply:
        print("rerun with --apply to push these updates")


if __name__ == "__main__":
    main()