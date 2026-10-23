"""Create private production configuration without replacing existing files."""

import argparse
import ipaddress
import os
import re
import secrets
from pathlib import Path


def validate_domain(value: str) -> str:
    """Accept a canonical DNS hostname; DNS ownership is verified separately."""
    labels = value.split(".")
    invalid = (
        len(value) > 253
        or len(labels) < 2
        or any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in labels
        )
        or not re.fullmatch(r"[a-z][a-z0-9-]*", labels[-1])
        or labels[-1]
        in {"localhost", "local", "internal", "test", "invalid", "example", "onion"}
    )
    try:
        ipaddress.ip_address(value)
        invalid = True
    except ValueError:
        pass
    if invalid:
        raise ValueError(
            "Use a lowercase public DNS hostname, without a scheme, port, path, or trailing dot."
        )
    return value


def create_configuration(root: Path, domain: str) -> bool:
    domain = validate_domain(domain)
    content = (root / "deploy" / "production.env.example").read_text(encoding="utf-8")
    content = content.replace("DOMAIN=\n", f"DOMAIN={domain}\n").replace(
        "POSTGRES_PASSWORD=\n", f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n"
    )
    try:
        descriptor = os.open(
            root / ".env.production", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(content)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--domain",
        required=True,
        help="Your public DNS hostname, for example studio.example.com",
    )
    args = parser.parse_args()
    try:
        created = create_configuration(Path(__file__).resolve().parents[1], args.domain)
    except ValueError as exc:
        parser.error(str(exc))
    except OSError:
        print(
            "Could not create production configuration. Check directory access and the template."
        )
        return 1
    if created:
        print(
            "Created private .env.production with a generated database password. Add your provider settings there."
        )
    else:
        print(
            "Existing .env.production preserved. Edit it to change production configuration."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
