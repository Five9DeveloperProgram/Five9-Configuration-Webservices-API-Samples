import argparse
import logging
from getpass import getpass

from requests.exceptions import RequestException
from zeep.exceptions import Fault

from five9.five9_session import Five9ClientCreationError
from five9.utils import domain_capture


class _CaptureConsoleFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)
        if record.levelno == logging.INFO:
            return message
        return f"{record.levelname}: {message}"


def main():
    parser = argparse.ArgumentParser(
        description="Captures domain configuration options in the domain_config domain_snapshots folder"
    )

    parser.add_argument(
        "--username",
        metavar="Five9 Username",
        type=str,
        required=False,
        help="Username for Five9 account with the admin/api role",
    )

    parser.add_argument(
        "--password",
        metavar="Five9 Password",
        type=str,
        required=False,
        help="Password for the Five9 account",
    )

    parser.add_argument(
        "--account_alias",
        metavar="Stored credential alias",
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

    parser.add_argument(
        "--skip-ivr-documentation",
        action="store_true",
        help="Skip generating IVR diagram/documentation files during capture",
    )

    parser.add_argument(
        "--call-delay",
        type=float,
        default=0.5,
        help="Total capture pause per attempt in seconds (default: 0.5, minimum: 0.3)",
    )
    parser.add_argument(
        "--rate-limit-retries",
        type=int,
        default=3,
        help="Retries per read on a query-limit fault (default: 3, range: 0-10)",
    )
    parser.add_argument(
        "--counter-check-interval",
        type=int,
        default=30,
        help="Read attempts between API usage checks (default: 30, minimum: 1)",
    )

    args = parser.parse_args()
    console = logging.StreamHandler()
    console.setFormatter(_CaptureConsoleFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[console])

    password = args.password

    if args.username and not args.password:
        password = getpass("Password: ")

    try:
        domain = domain_capture.Five9DomainConfig(
            username=args.username,
            password=password,
            account=args.account_alias,
            api_hostname_alias=args.hostalias,
            generate_ivr_diagrams=not args.skip_ivr_documentation,
            call_delay=args.call_delay,
            rate_limit_retries=args.rate_limit_retries,
            counter_check_interval=args.counter_check_interval,
        )
        domain.get_domain_objects()
    except (domain_capture.DomainCaptureError, ValueError) as error:
        logging.error("%s", error)
        return 1
    except (Five9ClientCreationError, Fault, RequestException, OSError) as error:
        logging.error(
            "Capture could not complete (%s). Check connection, permissions, "
            "rate limits, and the snapshot folder before retrying.",
            type(error).__name__,
        )
        return 1
    logging.info("\nCapture complete. Snapshot saved successfully.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
