import argparse
import csv
from datetime import datetime
import logging
import time
import os

import tqdm


from five9 import five9_session

# Set up logging
logging.basicConfig(level=logging.INFO)


def capture_user_details(
    client: five9_session.Five9Client,
    target_generalInfo_fields: list = ["userName", "EMail", "fullName", "active"],
    target_permissions: dict = {},
    include_media_types: bool = False,
    target_filename: str = "users.csv",
    target_users: list = [],
):
    """Retrieve user details from a Five9 client object and save them to a CSV file.

    Args:
        client (five9_session.Five9Client): A Five9 client object that is authenticated and connected.
        target_generalInfo_fields (list, optional): A list of strings specifying the general information fields to include in the CSV file. Defaults to ["userName", "EMail", "fullName", "active"].
        target_permissions (dict, optional): A dictionary specifying the role keys and permission types to include in the CSV file. Defaults to {}.
        target_filename (str, optional): A string specifying the name of the CSV file to save the user details to. Defaults to "users.csv".
        target_users (list, optional): A list of usernames to limit the retrieval to specific users. Defaults to [].

    Returns:
        None: This function does not return anything, but it writes the user details to a CSV file.
    """

    if target_users:
        logging.info(f"Limiting user details capture to targeted users: {target_users}")
        users = []
        for user in tqdm.tqdm(target_users):
            try:
                user_info = client.service.getUserInfo(user)
                users.append(user_info)
                time.sleep(0.3)  # Delay between API calls to avoid rate limits
            except Exception as e:
                logging.error(f"Error retrieving info for user {user}: {e}")
    else:
        logging.info(f"Retrieving all users' details.")
        users = client.service.getUsersInfo()

    logging.info(f"Capturing details for {len(users)} users")

    if not users:
        logging.warning("No users retrieved. Exiting without creating CSV.")
        return  # Exit the function if no users were retrieved

    # Add logic for target permissions as before...
    if not target_permissions:
        logging.info(
            "No target permissions specified. Capturing all permissions for each user."
        )
        for user in users:
            for role_key in user.roles:
                if user.roles[role_key] is not None and role_key == "agent":
                    for perm in user.roles[role_key]["permissions"]:
                        if role_key not in target_permissions:
                            target_permissions[role_key] = []
                        if perm.type not in target_permissions[role_key]:
                            target_permissions[role_key].append(perm.type)

    logging.info(f"Target permissions: {target_permissions}")

    # Create an empty list to store the user information
    ap = []

    for user in users:
        user_output = {}
        for attribute in target_generalInfo_fields:
            user_output[attribute] = user.generalInfo[attribute]

        # Add media types configuration to the output
        if include_media_types:
            media_types = user.generalInfo.mediaTypeConfig.mediaTypes
            for media_type in media_types:
                media_type_name = media_type.type
                user_output[f"media_enabled_{media_type_name}"] = media_type.enabled

        # Add permissions if specified
        for role_key in target_permissions.keys():
            if user.roles[role_key] is not None:
                for perm in user.roles[role_key]["permissions"]:
                    if perm.type in target_permissions[role_key]:
                        user_output[perm.type] = perm.value

        # Append the user dictionary to the ap list
        ap.append(user_output)

    if not ap:
        logging.warning("No user details captured. Exiting without creating CSV.")
        return

    # Ensure that the target directory exists
    if not os.path.exists(os.path.dirname(target_filename)):
        os.makedirs(os.path.dirname(target_filename))
        logging.info(f"Created directory: {os.path.dirname(target_filename)}")
    else:
        logging.info(f"Directory already exists: {os.path.dirname(target_filename)}")

    # Write the list of user information to a CSV file
    with open(target_filename, "w", newline="") as file:
        # Create a CSV writer object
        writer = csv.DictWriter(file, fieldnames=ap[0].keys())

        # Write the header row
        writer.writeheader()

        # Write each dictionary as a row in the CSV file
        for row in ap:
            writer.writerow(row)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="captures specified user details and permissions and writes the output to a csv"
    )
    parser.add_argument(
        "-u", "--username", help="Five9 Username for authentication", required=False
    )
    parser.add_argument(
        "-p", "--password", help="Five9 Password for authentication", required=False
    )
    parser.add_argument(
        "-a",
        "--account",
        help="Alias for credential stored in private/credentials",
        required=False,
    )
    parser.add_argument(
        "-fn", "--filename", help="Target Five9 Report Folder", required=False
    )

    parser.add_argument(
        "--hostalias",
        type=str,
        default="us",
        help="Five9 host alias (us, ca, eu, frk, in)",
    )

    args = vars(parser.parse_args())

    five9_username = args["username"] or None
    five9_password = args["password"] or None
    five9_account = args["account"] or None

    # Set the target filename to private/users_{yyyy-mm-dd}.csv
    target_filename = (
        args["filename"] or f"private/users_{datetime.now().strftime('%Y-%m-%d')}.csv"
    )

    # Get the Five9 API client
    client = five9_session.Five9Client(
        five9username=five9_username,
        five9password=five9_password,
        account=five9_account,
        api_hostname_alias=args["hostalias"],
    )

    # Specify the general user fields to include in the CSV file
    target_generalInfo_fields = ["userName", "firstName", "lastName", "EMail", "active"]

    # Specify any role keys and permission types to include in the CSV file
    # target_permissions = {"agent": ["ManageAvailabilityBySkill", "CallForwarding"]}
    target_permissions = {"agent": ["ReceiveTransfer"]}
    # target_permissions = {}
    target_users = []

    capture_user_details(
        client,
        target_permissions=target_permissions,
        target_generalInfo_fields=target_generalInfo_fields,
        target_filename=target_filename,
        target_users=target_users,
    )
