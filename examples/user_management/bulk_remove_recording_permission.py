"""
Bulk Remove Recording Permission from Agents

This script removes the 'MakeRecordings' permission from agents specified in a CSV file.
The CSV should contain a 'userName' column with the usernames of agents to modify.

Usage:
    python bulk_remove_recording_permission.py --account_alias my_account --users_csv users.csv
    python bulk_remove_recording_permission.py --username user@domain --password pass --users_csv users.csv --dry_run
    python bulk_remove_recording_permission.py --account_alias my_account --users_csv users.csv --real_run

The script operates in dry-run mode by default. Use --real_run to actually apply changes.

API Method Used:
    - getUserInfo: Retrieve user details including current permissions
    - modifyUser: Update user with modified permissions

Recording-Related Permissions:
    - MakeRecordings: Agent permission that allows making recordings
    - CanAccessRecordingsColumn: Reporting permission for accessing recordings column in reports
"""

from five9.utils.common import common_parser_arguments, create_five9_client
import logging
import csv
from pathlib import Path
from typing import List, Set
from datetime import datetime


def parse_args():
    """Parse CLI arguments for bulk recording permission removal."""
    additional_args = [
        {
            "name": "--users_csv",
            "required": True,
            "type": str,
            "help": "CSV file with 'userName' column listing users to remove recording permission from.",
        },
        {
            "name": "--dry_run",
            "dest": "dry_run",
            "default": True,
            "action": "store_true",
            "help": "Dry-run mode (default). Use --real_run to apply changes.",
        },
        {
            "name": "--real_run",
            "dest": "dry_run",
            "action": "store_false",
            "help": "Disable dry-run; apply changes to users.",
        },
        {
            "name": "--log_level",
            "default": "INFO",
            "type": str,
            "choices": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            "help": "Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
        },
    ]
    return common_parser_arguments(additional_args)


def load_usernames_from_csv(csv_path: str) -> Set[str]:
    """Load usernames from CSV file. Expects a 'userName' column."""
    usernames = set()
    csv_file = Path(csv_path)
    
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    with csv_file.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "userName" not in reader.fieldnames:
            raise ValueError(
                f"CSV file must contain a 'userName' column. Found columns: {reader.fieldnames}"
            )
        
        for row in reader:
            username = row.get("userName", "").strip()
            if username:
                usernames.add(username)
    
    logging.info(f"Loaded {len(usernames)} usernames from {csv_path}")
    return usernames


def remove_recording_permission(user) -> List[str]:
    """
    Remove MakeRecordings permission from agent role.
    Returns list of changes made.
    """
    changes = []
    
    # Check if user has agent role
    try:
        agent_role = user.roles.agent
        if not agent_role:
            logging.debug(f"User {user.generalInfo.userName} does not have agent role")
            return changes
        
        agent_permissions = getattr(agent_role, "permissions", None)
        if not agent_permissions:
            logging.debug(f"User {user.generalInfo.userName} has no agent permissions")
            return changes
        
        # Find and disable MakeRecordings permission
        for permission in agent_permissions:
            if permission.type == "MakeRecordings":
                if permission.value:
                    logging.debug(
                        f"User {user.generalInfo.userName}: Removing 'MakeRecordings' permission"
                    )
                    permission.value = False
                    changes.append("MakeRecordings")
                else:
                    logging.debug(
                        f"User {user.generalInfo.userName}: 'MakeRecordings' already disabled"
                    )
    except AttributeError as e:
        logging.warning(
            f"User {user.generalInfo.userName}: Unable to access agent permissions - {e}"
        )
    
    return changes


def write_audit_log(domain_name: str, username: str, changes: List[str], dry_run: bool):
    """Write audit log of changes to a file."""
    audit_dir = Path("private")
    audit_dir.mkdir(exist_ok=True)
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    audit_subdir = audit_dir / date_str
    audit_subdir.mkdir(exist_ok=True)
    
    mode = "DRY_RUN" if dry_run else "APPLIED"
    audit_file = audit_subdir / f"recording_permission_removal_{domain_name}_{date_str}.txt"
    
    with audit_file.open("a") as f:
        f.write(f"{datetime.now().isoformat()}|{mode}|{username}|{','.join(changes)}\n")


def main():
    args = parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    
    # Create Five9 client
    logging.info("Connecting to Five9...")
    client = create_five9_client(args)
    logging.info(f"Connected to domain: {client.domain_name}")
    
    # Display mode
    if args.dry_run:
        logging.warning("=" * 70)
        logging.warning("DRY-RUN MODE: No changes will be applied")
        logging.warning("Use --real_run to actually modify users")
        logging.warning("=" * 70)
    else:
        logging.warning("=" * 70)
        logging.warning("REAL RUN MODE: Changes will be applied to users!")
        logging.warning("=" * 70)
    
    # Load usernames from CSV
    try:
        target_usernames = load_usernames_from_csv(args.users_csv)
    except Exception as e:
        logging.error(f"Failed to load CSV file: {e}")
        return
    
    if not target_usernames:
        logging.error("No usernames found in CSV file")
        return
    
    # Process each user
    total_processed = 0
    total_modified = 0
    total_errors = 0
    
    for username in target_usernames:
        try:
            logging.info(f"Processing user: {username}")
            
            # Get user info
            user_info = client.service.getUserInfo(username)
            
            # Check if user is active
            if not user_info.generalInfo.active:
                logging.warning(f"Skipping inactive user: {username}")
                continue
            
            total_processed += 1
            
            # Remove recording permission
            changes = remove_recording_permission(user_info)
            
            if changes:
                total_modified += 1
                
                if args.dry_run:
                    logging.info(f"(Dry-run) Would remove permissions from {username}: {changes}")
                else:
                    # Apply changes
                    try:
                        client.service.modifyUser(
                            user_info.generalInfo,
                            rolesToSet=user_info.roles
                        )
                        logging.info(f"✓ Removed permissions from {username}: {changes}")
                    except Exception as e:
                        if "is already locked" in str(e):
                            logging.warning(f"User {username} is already locked, skipping: {e}")
                        else:
                            logging.error(f"Failed to modify user {username}: {e}")
                            total_errors += 1
                        continue
                
                # Write audit log
                write_audit_log(client.domain_name, username, changes, args.dry_run)
            else:
                logging.info(f"No changes needed for {username}")
        
        except Exception as e:
            logging.error(f"Error processing user {username}: {e}")
            total_errors += 1
            continue
    
    # Summary
    logging.info("=" * 70)
    logging.info("Summary:")
    logging.info(f"  Total usernames in CSV: {len(target_usernames)}")
    logging.info(f"  Active users processed: {total_processed}")
    logging.info(f"  Users modified: {total_modified}")
    logging.info(f"  Errors: {total_errors}")
    logging.info(f"  Mode: {'DRY-RUN' if args.dry_run else 'REAL RUN'}")
    logging.info("=" * 70)
    
    if args.dry_run and total_modified > 0:
        logging.info("Run with --real_run to apply these changes")


if __name__ == "__main__":
    main()
