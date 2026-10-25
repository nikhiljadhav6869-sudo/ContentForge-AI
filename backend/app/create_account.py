"""Provision a regular account from a trusted server terminal, even when sign-up is closed."""

import argparse
import getpass
import sys
import warnings

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .auth import create_account
from .schemas import Credentials


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Email address for the new account")
    parser.add_argument("--name", default="Creator", help="Display name, up to 80 characters")
    args = parser.parse_args(argv)
    if not sys.stdin.isatty():
        print("An interactive terminal is required. Passwords are never accepted as command arguments or piped input.")
        return 1
    try:
        # Refuse getpass's echoing fallback if the terminal cannot hide input.
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("New password (10–128 characters): ")
            confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            print("Passwords do not match. No account was created.")
            return 1
        credentials = Credentials(email=args.email, name=args.name, password=password)
        create_account(credentials)
    except ValidationError:
        print("Use a valid email address, a 1–80 character name, and a 10–128 character password.")
        return 1
    except IntegrityError:
        print("Account creation conflicted with existing data. Existing accounts were preserved.")
        return 1
    except (EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        print("Account creation cancelled; secure password input is required.")
        return 1
    except (SQLAlchemyError, OSError):
        print("Account creation failed. Check database access and migrations; connection details are omitted.")
        return 1
    print(
        "Account and private workspace created. Sign in through the website; email verification is still required to verify ownership."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
