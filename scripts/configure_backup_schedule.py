"""Generate reviewable systemd user units; never install or enable a timer."""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def quoted_path(path):
    value = str(Path(path).absolute())
    if value.endswith(" ") or any(
        ord(char) < 32 or ord(char) == 127 or char in '\\"%$' for char in value
    ):
        raise ValueError(
            "Use paths without trailing spaces, control characters, backslashes, quotes, percent signs, or dollar signs."
        )
    return '"' + value + '"'


def generate(output, backup_directory, production=False, hour_utc=2, root=ROOT):
    if not 0 <= hour_utc <= 23:
        raise ValueError("UTC hour must be between 0 and 23.")
    project = "contentforge-production" if production else "contentforge"
    unit = project + "-backup"
    # WorkingDirectory accepts the whole value, including internal spaces,
    # but unlike ExecStart it does not remove surrounding quotes.
    working = quoted_path(root)[1:-1]
    interpreter = quoted_path(Path(sys.executable).resolve())
    runner = quoted_path(root / "scripts/scheduled_backup.py")
    destination = quoted_path(backup_directory)
    flag = " --production" if production else ""
    service = f"""[Unit]
Description=ContentForge PostgreSQL backup ({project})

[Service]
Type=oneshot
WorkingDirectory={working}
ExecStart={interpreter} {runner}{flag} --directory {destination}
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
UMask=0077
NoNewPrivileges=true
TimeoutStartSec=20min
"""
    timer = f"""[Unit]
Description=Daily ContentForge PostgreSQL backup ({project})

[Timer]
OnCalendar=*-*-* {hour_utc:02d}:00:00 UTC
RandomizedDelaySec=10min
Persistent=true
Unit={unit}.service

[Install]
WantedBy=timers.target
"""
    # A new directory prevents partial replacement of an existing reviewed pair.
    output = Path(output)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    created = []
    try:
        for suffix, content in [("service", service), ("timer", timer)]:
            target = output / f"{unit}.{suffix}"
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created.append(target)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
        return unit
    except BaseException:
        for target in created:
            target.unlink(missing_ok=True)
        output.rmdir()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-directory",
        required=True,
        type=Path,
        help="New directory for generated units",
    )
    parser.add_argument(
        "--backup-directory",
        required=True,
        type=Path,
        help="Private backup destination on this server",
    )
    parser.add_argument(
        "--production", action="store_true", help="Target the production Compose stack"
    )
    parser.add_argument(
        "--hour-utc",
        type=int,
        default=2,
        help="Daily UTC hour (default: 2, with up to 10 minutes jitter)",
    )
    args = parser.parse_args(argv)
    try:
        unit = generate(
            args.output_directory, args.backup_directory, args.production, args.hour_utc
        )
    except ValueError as error:
        parser.error(str(error))
    except OSError:
        print(
            "Could not generate units. Use a new writable output directory; existing files are preserved."
        )
        return 1
    print(
        f"Generated {unit}.service and {unit}.timer. Review and install them on the deployment server; no timer was enabled."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
