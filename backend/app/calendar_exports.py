"""RFC 5545 calendar snapshots for individual editorial reminders."""

from datetime import datetime, timezone


def text_value(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = "".join(char for char in value if char in "\n\t" or (ord(char) >= 32 and ord(char) != 127))
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")


def folded_line(value: str) -> str:
    # Content lines are limited to 75 octets, including the continuation space.
    # Split on Unicode characters so no UTF-8 sequence is divided across lines.
    lines, current, size = [], "", 0
    for char in value:
        width = len(char.encode("utf-8"))
        if size + width > 75:
            lines.append(current)
            current, size = " ", 1
        current += char
        size += width
    lines.append(current)
    return "\r\n".join(lines)


def utc_date(value: str) -> str:
    date = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    return f"{date.year:04d}{date.month:02d}{date.day:02d}T{date.hour:02d}{date.minute:02d}{date.second:02d}Z"


def reminder_calendar(job, artifact, version, mode: str) -> bytes:
    demo = "[DEMO] " if mode == "demo" else ""
    description = (
        f"Editorial reminder for {artifact.platform}. No content is published automatically.\n"
        f"Approved content version: {version.number} ({version.id}).\n"
        "This file is a snapshot. Update or remove previously imported events manually after changes."
    )
    if mode == "demo":
        description += "\nDEMO: curated sample content, not live AI research."
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ContentForge AI//Editorial Reminders//EN",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{job.id}@contentforge.local",
        f"DTSTAMP:{utc_date(datetime.now(timezone.utc).isoformat())}",
        f"CREATED:{utc_date(job.created_at)}",
        f"DTSTART:{utc_date(job.scheduled_at)}",
        "SUMMARY:" + text_value(f"{demo}Editorial reminder — {artifact.platform.title()}: {artifact.title}"),
        "DESCRIPTION:" + text_value(description),
        "CLASS:PRIVATE",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return ("\r\n".join(folded_line(line) for line in lines) + "\r\n").encode("utf-8")
