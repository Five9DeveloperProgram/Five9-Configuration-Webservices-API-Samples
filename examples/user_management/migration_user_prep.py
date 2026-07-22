"""Prepare users for migration by adjusting selected role permissions.

Usage examples:
    # Dry-run (default): shows what would change, writes audit records.
    python examples/user_management/migration_user_prep.py --account_alias default_account

    # Dry-run against a subset of users from CSV/plain-text list.
    python examples/user_management/migration_user_prep.py --account_alias default_account --users_csv private/target_users.csv

    # Apply changes for agent-role updates only.
    python examples/user_management/migration_user_prep.py --account_alias default_account --real_run

    # Apply changes across agent, supervisor, and admin roles.
    python examples/user_management/migration_user_prep.py --account_alias default_account --all_user_roles --real_run
"""

from five9.utils.common import common_parser_arguments, create_five9_client
import logging
from pathlib import Path
import csv
import datetime
from typing import Iterable, List, Optional, Set


def parse_args():
    """Parse CLI arguments, adding dry-run and optional CSV filter."""
    additional_args = [
        {
            "name": "--dry_run",
            "dest": "dry_run",
            "default": True,
            "action": "store_true",
            "help": "Dry-run mode (default). Use --no_dry_run to apply changes.",
        },
        {
            "name": "--real_run",
            "dest": "dry_run",
            "action": "store_false",
            "help": "Disable dry-run; apply changes.",
        },
        {
            "name": "--users_csv",
            "default": None,
            "type": str,
            "help": "Optional CSV of target users to modify (expects a 'userName' column)",
        },
        {
            "name": "--log_level",
            "default": "INFO",
            "type": str,
            "choices": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            "help": "Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
        },
        {
            "name": "--all_user_roles",
            "dest": "all_user_roles",
            "default": False,
            "action": "store_true",
            "help": "Process all user roles (default is agent role only).",
        },
        {
            "name": "--load_all_threshold",
            "default": 20,
            "type": int,
            "help": "Threshold for loading all users; if exceeded, loading is skipped.",
        }
    ]
    return common_parser_arguments(additional_args=additional_args)


def load_target_usernames(csv_file: Optional[str]) -> Optional[Set[str]]:
    """Load a set of usernames from a CSV file if provided; otherwise None."""
    if not csv_file:
        return None

    csv_path = Path(csv_file)
    if not csv_path.is_file():
        logging.warning(f"CSV file {csv_path} not found; proceeding without filter")
        return None

    try:
        with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            # Preferred path: CSV with a 'userName' header
            if reader.fieldnames and "userName" in reader.fieldnames:
                usernames = {
                    (row.get("userName") or "").strip()
                    for row in reader
                    if row.get("userName")
                }
                logging.info(
                    f"Loaded {len(usernames)} target usernames from {csv_path}"
                )
                return usernames

            # Fallback: treat file as a plain newline-delimited list of usernames (no header)
            f.seek(0)
            lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]
            if lines and all(
                "," not in ln and ";" not in ln for ln in lines
            ):
                usernames = set(lines)
                logging.info(
                    f"Loaded {len(usernames)} target usernames (plain text list) from {csv_path}"
                )
                return usernames

            logging.warning(
                f"File {csv_path} not recognized as CSV with 'userName' column or plain text list; proceeding without filter"
            )
            return None
    except Exception as e:
        logging.warning(
            f"Failed to read CSV {csv_path} ({e}); proceeding without filter"
        )
        return None


def _set_permission(
    permissions: Optional[Iterable],
    perm_type: str,
    desired_value: bool,
    modified: List[str],
    user_name: str,
):
    """Ensure the given permission is set to desired_value; record if changed.

    - No-op if permissions iterable is None or target permission not present.
    - Appends perm_type to `modified` when a change is applied.
    """
    if not permissions:
        return
    for permission in permissions:
        try:
            if permission.type == perm_type and getattr(permission, "value", None) is not desired_value:
                logging.debug(
                    f"\tUser {user_name}: setting '{perm_type}' from {permission.value} to {desired_value}."
                )
                permission.value = desired_value
                modified.append(permission.type)
        except AttributeError:
            # Skip any unexpected permission objects
            continue


def collect_permission_changes(user, all_user_roles=False) -> List[str]:
    """Mutate user's permissions as needed and return a list of changed permission types."""
    modified: List[str] = []

    # Agent role
    try:
        logging.debug(f"Processing AGENT permissions: {user.generalInfo.userName}")
        agent_perms = getattr(user.roles.agent, "permissions", None)
        _set_permission(agent_perms, "CanRunJavaClient", False, modified, user.generalInfo.userName)
        # Ensure agent can run web client
        _set_permission(agent_perms, "CanRunWebClient", True, modified, user.generalInfo.userName)
    except AttributeError:
        logging.debug(
            f"\tUser {user.generalInfo.userName} does not have agent role or permissions."
        )

    if all_user_roles is False:
        return modified

    # Supervisor role
    try:
        logging.debug(f"Processing SUPERVISOR permissions: {user.generalInfo.userName}")
        sup_perms = getattr(user.roles.supervisor, "permissions", None)
        _set_permission(sup_perms, "CanRunJavaClient", False, modified, user.generalInfo.userName)
        _set_permission(sup_perms, "CanUseSupervisorSoapApi", False, modified, user.generalInfo.userName)
        # Ensure supervisor can run web client
        _set_permission(sup_perms, "CanRunWebClient", True, modified, user.generalInfo.userName)
    except AttributeError:
        logging.debug(
            f"\tUser {user.generalInfo.userName} does not have supervisor role or permissions."
        )

    # Admin role
    try:
        logging.debug(f"Processing ADMIN permissions: {user.generalInfo.userName}")
        admin_perms = getattr(user.roles.admin, "permissions", None)
        _set_permission(admin_perms, "CanUseAdminSoapApi", False, modified, user.generalInfo.userName)
    except AttributeError:
        logging.debug(
            f"\tUser {user.generalInfo.userName} does not have admin role or permissions."
        )

    try:
        # check if the user has the 'crmManager' role.  If so, set it to None and track the change with the modified list.
        if getattr(user.roles, 'crmManager', None) is not None:
            user.roles.crmManager = None
            modified.append('crmManager role removed')
            logging.debug(
                f"\tUser {user.generalInfo.userName} had 'crmManager' role removed."
            )
    except AttributeError:
        logging.debug(
            f"\tUser {user.generalInfo.userName} does not have crmManager role or permissions."
        )
    return modified


def should_process_user(user, target_usernames: Optional[Set[str]]) -> bool:
    """Return True if user is active and matches optional CSV filter."""
    if getattr(user.generalInfo, "active", False) is False:
        return False
    if target_usernames is None:
        return True
    if user.generalInfo.userName in target_usernames:
        logging.debug(f"User {user.generalInfo.userName} is in target list.")
        return True
    return False


def write_audit(
    domain_name: str,
    username: str,
    modified: List[str],
    audit_dir: Path = Path("private"),
) -> None:
    """Append an audit record of modified permissions for a user to a file."""
    audit_dir.mkdir(exist_ok=True)
    # get yyyy-mm-dd format
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    audit_subdir = audit_dir / date_str
    audit_subdir.mkdir(exist_ok=True)
    audit_dir = audit_subdir

    with (audit_dir / f"modified_users_{domain_name}_{date_str}.txt").open("a") as f:
        f.write(f"{domain_name}|{username}|{modified}\n")


def main():
    args = parse_args()
    # Configure logging using CLI level
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    print("Starting user preparation script...")

    client = create_five9_client(args)

    target_usernames = load_target_usernames(getattr(args, "users_csv", None))

    # summarize arguments in the log
    logging.info(f"Arguments: dry_run={args.dry_run}, users_csv={args.users_csv}, all_user_roles={args.all_user_roles}")

    # if the length of the target_usernames is less than the load_all_threshold, load users individually
    if target_usernames and len(target_usernames) < args.load_all_threshold:
        logging.info(
            f"Retrieving {len(target_usernames)} target users individually from Five9 domain: {client.domain_name}."
        )

        users = []
        for username in target_usernames:
            try:
                user_info = client.service.getUsersInfo(username)[0]
                users.append(user_info)
            except Exception as e:
                logging.warning(f"Failed to retrieve user {username}: {e}")
    else:
        logging.info(
            f"Retrieving all users from Five9 domain: {client.domain_name}."
        )
        users = client.service.getUsersInfo()
    
    logging.info(
        f"Retrieved {len(users)} users from Five9 domain: {client.domain_name}."
    )

    total_examined = 0
    total_modified = 0
    for user in users:
        if not should_process_user(user, target_usernames):
            continue

        total_examined += 1
        modified_perms = collect_permission_changes(user, all_user_roles=args.all_user_roles)
        if modified_perms:
            total_modified += 1
            if not args.dry_run:
                try:
                    client.service.modifyUser(user.generalInfo, rolesToSet=user.roles)
                    logging.info(f"User {user.generalInfo.userName}| {modified_perms}")
                except Exception as e:
                    if "is already locked" in str(e):
                        logging.warning(f"User {user.generalInfo.userName} is already locked, skipping modification: {e}")
                    else:
                        logging.error(f"Failed to modify user {user.generalInfo.userName}: {e}")
            
            else:
                logging.info(f"(Dry-run) User {user.generalInfo.userName}| {modified_perms}")
            # Always write audit log, even in dry-run mode
            write_audit(client.domain_name, user.generalInfo.userName, modified_perms)

    logging.info(
        f"Done. Examined {total_examined} active users, modified {total_modified}. Dry-run={args.dry_run}"
    )


if __name__ == "__main__":
    main()
