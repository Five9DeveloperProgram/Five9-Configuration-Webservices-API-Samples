import argparse
from five9 import five9_session


def common_parser_arguments(additional_args=None):
    parser = argparse.ArgumentParser(
        description="Common argument parser for Five9 examples"
    )

    parser.add_argument(
        "--username",
        metavar="Five9 Username",
        default=None,
        type=str,
        required=False,
        help="Username for Five9 account with the admin/api role",
    )

    parser.add_argument(
        "--password",
        metavar="Five9 Password",
        default=None,
        type=str,
        required=False,
        help="Password for the Five9 account",
    )

    parser.add_argument(
        "--account_alias",
        metavar="Stored credential alias",
        default=None,
        type=str,
        required=False,
        help="Alias for a stored credential object in private/credentials.py",
    )

    parser.add_argument(
        "--hostalias",
        type=str,
        default="us",
        help="Five9 host alias (us, ca, eu, frk, in)",
    )

    if additional_args:
        for arg in additional_args:
            parser.add_argument(arg.pop("name"), **arg)

    return parser.parse_args()


def create_five9_client(args):
    return five9_session.Five9Client(
        five9username=args.username,
        five9password=args.password,
        account=args.account_alias,
        api_hostname_alias=args.hostalias,
    )
