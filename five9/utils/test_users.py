"""Utilities for discovering and exporting test users."""

import csv
from pathlib import Path

from five9.utils.common import common_parser_arguments, create_five9_client


DEFAULT_TEST_USERNAME_PATTERN = r".*[Tt][Ee][Ss][Tt].*"
DEFAULT_TEST_USERS_CSV_PATH = (
    "examples/user_management/private/test_users_recording.csv"
)


def find_test_users(client, user_name_pattern=DEFAULT_TEST_USERNAME_PATTERN):
    """Return users whose usernames match the provided regex pattern."""
    users = client.service.getUsersGeneralInfo(userNamePattern=user_name_pattern)
    return list(users) if users else []


def active_users(users):
    """Return only active users from a user collection."""
    return [user for user in users if getattr(user, "active", False)]


def export_usernames_to_csv(users, csv_path):
    """Write usernames to CSV and return number of records written."""
    output_path = Path(csv_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["userName"])
        for user in users:
            writer.writerow([user.userName])

    return len(users)


def build_client_from_cli():
    """Create a Five9 client from standard CLI auth arguments."""
    args = common_parser_arguments()
    return create_five9_client(args)


def run_find_and_export(client, csv_path=DEFAULT_TEST_USERS_CSV_PATH):
    """Find test users, export active ones, and return summary information."""
    users = find_test_users(client)
    active = active_users(users)
    saved_count = export_usernames_to_csv(active, csv_path)
    return {
        "users": users,
        "active_users": active,
        "saved_count": saved_count,
        "csv_path": str(Path(csv_path)),
    }


def main():
    """CLI entrypoint for discovering and exporting test users."""
    client = build_client_from_cli()
    result = run_find_and_export(client)

    print(f"\n=== Found {len(result['users'])} users with \"test\" in username ===")
    for user in result["users"]:
        active_status = "ACTIVE" if user.active else "INACTIVE"
        print(f"{user.userName} - {active_status}")

    print(
        f"\nSaved {result['saved_count']} active test users to "
        f"{result['csv_path']}"
    )


if __name__ == "__main__":
    main()