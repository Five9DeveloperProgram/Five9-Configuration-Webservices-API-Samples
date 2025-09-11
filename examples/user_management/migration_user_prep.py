from five9.utils.common import common_parser_arguments, create_five9_client
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)

print("Starting user preparation script...")

if __name__ == "__main__":

    # add an argument for dry-run mode
    additional_args = [
        {
            "name": "--dry_run",
            "default": True,
            "action": "store_true",
            "help": "Run the script in dry-run mode without making changes",
        }
    ]

    args = common_parser_arguments(additional_args=additional_args)
    client = create_five9_client(args)

    users = client.service.getUsersInfo()

    logging.info(
        f"Retrieved {len(users)} users from Five9 account {args.account_alias}."
    )

    users_to_modify = []

    for user in users:
        if user.generalInfo.active == False:
            continue
        # if user.roles.admin.permissions:
        #     for permission in user.roles.admin.permissions:
        #         if
        modify_user_permissions = []
        try:
            for permission in user.roles.supervisor.permissions:
                if permission.type == "CanRunJavaClient" and permission.value == True:
                    logging.debug(
                        f"User {user.generalInfo.userName} has 'CanRunJavaClient' = {permission.value}."
                    )

                    # set permission to False
                    permission.value = False
                    modify_user_permissions.append(permission.type)

                if permission.type == "CanUseSupervisorSoapApi" and permission.value == True:
                    logging.debug(
                        f"User {user.generalInfo.userName} has 'CanUseSupervisorSoapApi' = {permission.value}."
                    )

                    # set permission to False
                    permission.value = False
                    modify_user_permissions.append(permission.type)

        except AttributeError:
            logging.debug(
                f"User {user.generalInfo.userName} does not have supervisor role or permissions."
            )
            continue

        try:
            for permission in user.roles.agent.permissions:
                if permission.type == "CanRunJavaClient" and permission.value == True:
                    logging.debug(
                        f"User {user.generalInfo.userName} has 'CanRunJavaClient' = {permission.value}."
                    )

                    # set permission to False
                    permission.value = False
                    modify_user_permissions.append(permission.type)

        except AttributeError:
            logging.debug(
                f"User {user.generalInfo.userName} does not have agent role or permissions."
            )
            continue

        try:
            for permission in user.roles.admin.permissions:
                if permission.type == "CanUseAdminSoapApi" and permission.value == True:
                    logging.debug(
                        f"User {user.generalInfo.userName} has 'CanUseAdminSoapApi' = {permission.value}."
                    )
                    # set permission to False
                    permission.value = False
                    modify_user_permissions.append(permission.type)

        except AttributeError:
            logging.debug(
                f"User {user.generalInfo.userName} does not have admin role or permissions."
            )
            continue

        if len(modify_user_permissions) > 0:
            logging.info(f"User {user.generalInfo.userName}| {modify_user_permissions}")
            if not args.dry_run:
                client.service.updateUser(user)
            
            # ensure private folder exists and write details to private/users_to_modify.txt
            Path("private").mkdir(exist_ok=True)
            with open(Path("private") / "users_to_modify.txt", "a") as f:
                f.write(
                    f"{client.domain_name}|{user.generalInfo.userName}|{modify_user_permissions}\n"
                )