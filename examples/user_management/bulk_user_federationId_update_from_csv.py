import csv
import time
from tqdm import tqdm
import argparse
from five9.utils.common import common_parser_arguments, create_five9_client
from five9 import five9_session
import zeep
from pathlib import Path
from datetime import datetime


def update_user_federation_ids(client, csv_path):
    """
    Updates federation IDs of users in the Five9 domain based on a provided CSV file.

    Parameters:
        client (five9_session.Five9Client): Authenticated Five9 client object.
        csv_path (str): Path to the CSV file containing user data.

    Returns:
        tuple: (updated_users, error_users, skip_users)
    """
    # Read CSV file and populate a dictionary of usernames to lookup federationIds
    user_federation_Ids = {}
    with open(csv_path, mode="r") as csvfile:
        csvreader = csv.DictReader(csvfile)
        for row in csvreader:
            user_federation_Ids[row["userName"]] = row["federationId"]

    users = client.service.getUsersInfo()

    users_to_update = []
    skip_users = []

    for user in users:
        if user_federation_Ids.get(user["generalInfo"]["userName"], "skip") != "skip":
            users_to_update.append(user)
        else:
            skip_users.append(user)

    updated_users = []
    error_users = []

    total_users = len(users_to_update)

    with tqdm(total=total_users, desc="Updating users", mininterval=1) as pbar:
        for user in users_to_update:
            try:
                user_federationId = user_federation_Ids.get(
                    user["generalInfo"]["userName"], "skip"
                )
                if user_federationId != "skip":
                    user.generalInfo.federationId = user_federationId
                    user.generalInfo.EMail = user.generalInfo.EMail.strip()
                    modified_user = client.service.modifyUser(user.generalInfo)
                    updated_users.append(modified_user)
                    time.sleep(0.3)
            except zeep.exceptions.Fault as e:
                user.errorMessage = str(e)
                error_users.append(user)
            finally:
                pbar.update(1)
                pbar.set_postfix(
                    {"Updated": len(updated_users), "Errors": len(error_users)}
                )

    return updated_users, error_users, skip_users


if __name__ == "__main__":
    # Parse arguments using common.py
    additional_args = [
        {
            "name": "--filename",
            "metavar": "CSV File Path",
            "default": "private/users_federation_update.csv",
            "type": str,
            "required": False,
            "help": "Path to the CSV file containing user federation IDs to update",
        },
        {
            "name": "--simulationmode",
            "metavar": "Simulation Mode",
            "default": "false",
            "type": str,
            "required": False,
            "help": "Simulation mode goes through the motions but doesn't update VCC. Defaults to False",
        },
        {
            "name": "--errorlog",
            "metavar": "Error Log File",
            "default": "private/user_federation_update_errors.csv",
            "type": str,
            "required": False,
            "help": "Path to the error log file",
        },
    ]
    args = common_parser_arguments(additional_args)

    # Create Five9 client
    client = create_five9_client(args)

    # Get CSV file path and simulation mode
    csv_path = args.filename
    simulation_mode = args.simulationmode.lower() == "true"

    if simulation_mode:
        print("\nSIMULATION MODE\n")

    # Update federation IDs
    updated_users, error_users, skip_users = update_user_federation_ids(client, csv_path)

    print(f"\nTotal users updated: {len(updated_users)}")
    print(f"Total errors: {len(error_users)}")
    print(f"Total skip users: {len(skip_users)}")

    if error_users:
        print("\nErrors occurred while updating users:")
        for user in error_users:
            print(f"User: {user.generalInfo.userName}\tError: {user.errorMessage}")

        # Ensure the directory for the error log exists
        error_log_path = Path(args.errorlog)
        error_log_path.parent.mkdir(parents=True, exist_ok=True)

        # check if the error log file argument has a file extension
        if error_log_path.suffix:
            error_log_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            error_log_path = error_log_path.with_name(f"{error_log_path.stem}_{error_log_timestamp}{error_log_path.suffix}")
        else:
            error_log_path = error_log_path.with_suffix(f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        print(f"\nWriting error log to {error_log_path}")
        with open(error_log_path, mode="w", newline="") as errorfile:
            fieldnames = [
                "userName",
                "federationId",
                "errorMessage",
            ]
            writer = csv.DictWriter(errorfile, fieldnames=fieldnames, delimiter="|")
            writer.writeheader()
            for user in error_users:
                writer.writerow({
                    "userName": user.generalInfo.userName,
                    "federationId": user.generalInfo.federationId,
                    "errorMessage": user.errorMessage,
                })



