import argparse  # retained for type hints if needed
import csv
from datetime import datetime
import logging
import time
import os
import json

import tqdm


from five9 import five9_session
from five9.utils.common import common_parser_arguments, create_five9_client

# Set up logging
logging.basicConfig(level=logging.INFO)


def compute_fieldnames(
    sample_user, target_generalInfo_fields, target_permissions, include_media_types
):
    """Compute CSV fieldnames deterministically based on provided targets and a sample user."""
    fieldnames = list(target_generalInfo_fields)
    if include_media_types:
        try:
            for media_type in sample_user.generalInfo.mediaTypeConfig.mediaTypes:
                col = f"media_enabled_{media_type.type}"
                if col not in fieldnames:
                    fieldnames.append(col)
        except Exception:
            logging.debug(
                "Sample user missing media types; skipping media columns inference."
            )
    for role_key, perms in target_permissions.items():
        for perm in perms:
            namespaced = f"{role_key}_{perm}"
            if namespaced not in fieldnames:
                fieldnames.append(namespaced)
    return fieldnames


def write_user_chunk(
    users,
    fieldnames,
    target_generalInfo_fields,
    target_permissions,
    include_media_types,
    target_filename,
    append: bool,
):
    """Write a chunk of user records to CSV.

    Ensures directory exists, writes header only when needed, and appends rows.
    """
    if not users:
        return

    dirpath = os.path.dirname(target_filename)
    if dirpath and not os.path.exists(dirpath):
        os.makedirs(dirpath)
        logging.info(f"Created directory: {dirpath}")

    file_exists = os.path.exists(target_filename)
    write_header = not append or (append and not file_exists)
    mode = "a" if append else "w"

    with open(target_filename, mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for user in users:
            row = {fn: "" for fn in fieldnames}
            for attribute in target_generalInfo_fields:
                try:
                    row[attribute] = user.generalInfo[attribute]
                except Exception:
                    row[attribute] = ""
            if include_media_types:
                try:
                    for media_type in user.generalInfo.mediaTypeConfig.mediaTypes:
                        row[f"media_enabled_{media_type.type}"] = media_type.enabled
                except Exception:
                    pass
            for role_key, perms in target_permissions.items():
                role_container = getattr(user, "roles", {})
                if isinstance(role_container, dict):
                    role = role_container.get(role_key)
                else:
                    try:
                        role = role_container[role_key]
                    except Exception:
                        role = None
                if role:
                    if isinstance(role, dict):
                        permissions_list = role.get("permissions", [])
                    else:
                        permissions_list = getattr(role, "permissions", [])
                    for perm in permissions_list:
                        p_type = getattr(perm, "type", None)
                        if p_type is None and isinstance(perm, dict):
                            p_type = perm.get("type")
                        p_value = getattr(perm, "value", None)
                        if p_value is None and isinstance(perm, dict):
                            p_value = perm.get("value")
                        if p_type in perms:
                            col_name = f"{role_key}_{p_type}"
                            if col_name in row:
                                row[col_name] = p_value
            writer.writerow(row)


def capture_user_details(
    client: five9_session.Five9Client,
    target_generalInfo_fields: list = ["userName", "EMail", "fullName", "active"],
    target_permissions: dict = {},
    include_media_types: bool = False,
    target_filename: str = "users.csv",
    target_users: list = [],
    big_domain: bool = False,
    big_domain_characters: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890",
    enumerate_numeric_prefixes: bool = False,
    numeric_prefix_width: int = 3,
    numeric_prefix_start: int = 0,
):
    """Retrieve user details and write to CSV with optional chunked retrieval for large domains."""

    if target_users:
        logging.info(f"Limiting user details capture to targeted users: {target_users}")
        users = []
        for uname in tqdm.tqdm(target_users):
            try:
                users.append(client.service.getUserInfo(uname))
                time.sleep(0.3)
            except Exception as e:
                logging.error(f"Error retrieving info for user {uname}: {e}")
    else:
        if big_domain:
            logging.info("Big domain mode enabled: chunked write.")
            if not target_permissions:
                logging.warning(
                    "Chunked mode requires explicit target_permissions; falling back to single batch."
                )
            else:
                first_chunk = True
                fieldnames = None
                total_users = 0
                if enumerate_numeric_prefixes:
                    upper = 10**numeric_prefix_width
                    if numeric_prefix_start < 0:
                        numeric_prefix_start = 0
                    if numeric_prefix_start >= upper:
                        logging.error("numeric_prefix_start beyond range; aborting.")
                        return
                    logging.info(
                        f"Enumerating numeric prefixes {numeric_prefix_start:0{numeric_prefix_width}d}..{upper-1:0{numeric_prefix_width}d}"
                    )
                    prefix_iter = (
                        f"{i:0{numeric_prefix_width}d}"
                        for i in range(numeric_prefix_start, upper)
                    )
                    total_prefixes = upper - numeric_prefix_start
                else:
                    prefix_iter = big_domain_characters
                    total_prefixes = len(big_domain_characters)

                progress = tqdm.tqdm(
                    prefix_iter, total=total_prefixes, desc="User chunks", unit="chunk"
                )
                for prefix in progress:
                    pattern = (
                        f"{prefix}.*"
                        if not enumerate_numeric_prefixes
                        else f"{prefix}*"
                    )
                    try:
                        chunk_users = client.service.getUsersInfo(pattern)
                        time.sleep(0.3)
                    except Exception as e:
                        logging.error(
                            f"Error retrieving users for pattern {pattern}: {e}"
                        )
                        progress.set_postfix(pattern=pattern, users="ERR")
                        continue
                    if not chunk_users:
                        progress.set_postfix(
                            pattern=pattern, users=0, total=total_users
                        )
                        continue
                    if first_chunk:
                        fieldnames = compute_fieldnames(
                            chunk_users[0],
                            target_generalInfo_fields,
                            target_permissions,
                            include_media_types,
                        )
                        write_user_chunk(
                            chunk_users,
                            fieldnames,
                            target_generalInfo_fields,
                            target_permissions,
                            include_media_types,
                            target_filename,
                            append=False,
                        )
                        first_chunk = False
                    else:
                        write_user_chunk(
                            chunk_users,
                            fieldnames,
                            target_generalInfo_fields,
                            target_permissions,
                            include_media_types,
                            target_filename,
                            append=True,
                        )
                    total_users += len(chunk_users)
                    progress.set_postfix(
                        pattern=pattern, users=len(chunk_users), total=total_users
                    )
                logging.info(f"Completed chunked capture: {total_users} users written")
                return
        logging.info("Retrieving all users (single batch).")
        users = client.service.getUsersInfo()

    logging.info(f"Capturing details for {len(users)} users in single batch mode")
    if not users:
        logging.warning("No users retrieved; aborting.")
        return

    if not target_permissions:
        logging.info(
            "No target permissions specified; auto-discovering agent permissions."
        )
        for user in users:
            role_container = getattr(user, "roles", {})
            if isinstance(role_container, dict):
                role_keys = role_container.keys()
            else:
                try:
                    role_keys = role_container.keys()
                except Exception:
                    continue
            for role_key in role_keys:
                try:
                    role = role_container[role_key]
                except Exception:
                    role = None
                if role_key == "agent" and role is not None:
                    if isinstance(role, dict):
                        permissions_list = role.get("permissions", [])
                    else:
                        permissions_list = getattr(role, "permissions", [])
                    for perm in permissions_list:
                        p_type = getattr(perm, "type", None)
                        if p_type is None and isinstance(perm, dict):
                            p_type = perm.get("type")
                        if not p_type:
                            continue
                        target_permissions.setdefault(role_key, [])
                        if p_type not in target_permissions[role_key]:
                            target_permissions[role_key].append(p_type)

    logging.info(f"Target permissions: {target_permissions}")

    fieldnames = compute_fieldnames(
        users[0], target_generalInfo_fields, target_permissions, include_media_types
    )
    write_user_chunk(
        users,
        fieldnames,
        target_generalInfo_fields,
        target_permissions,
        include_media_types,
        target_filename,
        append=False,
    )


if __name__ == "__main__":
    additional_args = [
        {
            "name": "--filename",
            "default": None,
            "required": False,
            "type": str,
            "help": "Output CSV (default private/users_YYYY-MM-DD.csv)",
        },
        {
            "name": "--config",
            "default": "user_capture_config.sample.json",
            "required": False,
            "type": str,
            "help": "Path to JSON config with generalInfoFields, permissions, includeMediaTypes",
        },
        {
            "name": "--include_media_types",
            "action": "store_true",
            "help": "Include media type enabled flags (adds media_enabled_<type> columns) overrides config",
        },
        {
            "name": "--big_domain",
            "action": "store_true",
            "help": "Enable big domain chunked retrieval",
        },
        {
            "name": "--enumerate_numeric_prefixes",
            "action": "store_true",
            "help": "Enumerate zero-padded numeric prefixes instead of character set",
        },
        {
            "name": "--numeric_prefix_width",
            "type": int,
            "default": 3,
            "help": "Width for numeric enumeration (3 -> 000..999)",
        },
        {
            "name": "--numeric_prefix_start",
            "type": int,
            "default": 0,
            "help": "Starting numeric prefix (e.g. 100 to skip 000-099)",
        },
    ]
    args = common_parser_arguments(additional_args=additional_args)
    client = create_five9_client(args)
    target_filename = (
        args.filename or f"private/users_{datetime.now().strftime('%Y-%m-%d')}.csv"
    )
    target_generalInfo_fields = ["userName", "firstName", "lastName", "EMail", "active"]
    target_permissions = {"agent": ["ReceiveTransfer"]}
    include_media_types_flag = args.include_media_types

    # Load JSON config if present
    if args.config and os.path.exists(args.config):
        try:
            with open(args.config, "r") as cfg_file:
                cfg = json.load(cfg_file)
            if isinstance(cfg.get("generalInfoFields"), list):
                target_generalInfo_fields = cfg["generalInfoFields"]
            if isinstance(cfg.get("permissions"), dict):
                target_permissions = cfg["permissions"]
            if "includeMediaTypes" in cfg and not include_media_types_flag:
                include_media_types_flag = bool(cfg["includeMediaTypes"])
            logging.info(f"Loaded capture config from {args.config}")
        except Exception as e:
            logging.error(f"Failed to load config {args.config}: {e}")
    target_users = []
    capture_user_details(
        client,
        target_permissions=target_permissions,
        target_generalInfo_fields=target_generalInfo_fields,
        target_filename=target_filename,
        target_users=target_users,
        big_domain=args.big_domain,
        enumerate_numeric_prefixes=args.enumerate_numeric_prefixes,
        numeric_prefix_width=args.numeric_prefix_width,
        numeric_prefix_start=args.numeric_prefix_start,
        include_media_types=include_media_types_flag,
    )

    # log the file
    logging.info(f"User details captured to {target_filename}")
