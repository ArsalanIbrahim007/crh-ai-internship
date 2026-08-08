"""Calendar scheduling.

Writes a real iCalendar (.ics) file, which imports into Google Calendar, Outlook or Apple
Calendar by double-clicking. Nothing is booked on a live calendar - same reasoning as the
email tool, an agent that writes to a real calendar unsupervised is a bad idea.

Hand-written rather than pulling in a dependency: the RFC 5545 subset needed for a single
timed event is small, and the escaping rules are the only fiddly part.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

CALENDAR_DIR = Path(__file__).resolve().parent.parent / "outputs" / "calendar"
MAX_DURATION_MINUTES = 8 * 60


@dataclass
class EventResult:
    ok: bool
    path: str = ""
    title: str = ""
    starts: str = ""
    ends: str = ""
    error: str = ""

    def to_text(self) -> str:
        if not self.ok:
            return f"CALENDAR ERROR: {self.error}"
        return (f"Event file saved to {self.path}\n"
                f"{self.title}\n{self.starts} to {self.ends}\n"
                f"Nothing was booked - import the file to add it to a calendar.")


def _escape(text: str) -> str:
    """RFC 5545 escaping. Order matters - backslash first, or it double-escapes."""
    return (text.replace("\\", "\\\\")
                .replace(";", "\\;")
                .replace(",", "\\,")
                .replace("\n", "\\n"))


def _fold(line: str) -> str:
    """Lines must not exceed 75 octets; continuations start with a space."""
    if len(line) <= 75:
        return line
    out = [line[:75]]
    rest = line[75:]
    while rest:
        out.append(" " + rest[:74])
        rest = rest[74:]
    return "\r\n".join(out)


def _safe_filename(title: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").lower()[:50] or "event"
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{slug}.ics"


def schedule_event(
    title: str,
    start: str,
    duration_minutes: int = 30,
    attendees: str = "",
    description: str = "",
) -> EventResult:
    """Create a calendar event file.

    start must be 'YYYY-MM-DD HH:MM'.
    attendees is a comma-separated list of email addresses.
    """
    title = (title or "").strip()
    if not title:
        return EventResult(ok=False, error="Event title is required.")

    try:
        begins = datetime.strptime((start or "").strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        return EventResult(
            ok=False,
            error=f"Could not read start time '{start}'. Use YYYY-MM-DD HH:MM, "
                  f"for example 2026-08-12 14:30.",
        )

    try:
        minutes = int(duration_minutes)
    except (TypeError, ValueError):
        return EventResult(ok=False, error="duration_minutes must be a whole number.")
    if not 1 <= minutes <= MAX_DURATION_MINUTES:
        return EventResult(
            ok=False,
            error=f"Duration must be between 1 and {MAX_DURATION_MINUTES} minutes.",
        )

    ends = begins + timedelta(minutes=minutes)
    fmt = "%Y%m%dT%H%M%S"

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Code Room Hub//BI Copilot//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uuid4()}@example.com",
        f"DTSTAMP:{datetime.now(timezone.utc).strftime(fmt)}Z",
        f"DTSTART:{begins.strftime(fmt)}",
        f"DTEND:{ends.strftime(fmt)}",
        f"SUMMARY:{_escape(title)}",
    ]

    if description:
        lines.append(f"DESCRIPTION:{_escape(description)}")

    for addr in [a.strip() for a in (attendees or "").split(",") if a.strip()]:
        lines.append(f"ATTENDEE;RSVP=TRUE:mailto:{addr}")

    lines += ["STATUS:CONFIRMED", "END:VEVENT", "END:VCALENDAR"]

    CALENDAR_DIR.mkdir(parents=True, exist_ok=True)
    path = CALENDAR_DIR / _safe_filename(title)
    path.write_text("\r\n".join(_fold(ln) for ln in lines) + "\r\n", encoding="utf-8")

    return EventResult(
        ok=True, path=str(path), title=title,
        starts=begins.strftime("%Y-%m-%d %H:%M"),
        ends=ends.strftime("%Y-%m-%d %H:%M"),
    )


if __name__ == "__main__":
    good = schedule_event(
        title="Renewal review: Northwind Systems",
        start="2026-08-12 14:30",
        duration_minutes=45,
        attendees="contact@northwindsystems.com, ae@example.com",
        description="Review usage; discuss Enterprise tier renewal, options and pricing.",
    )
    print(good.to_text())
    print()

    for bad in [
        schedule_event("", "2026-08-12 14:30"),
        schedule_event("Meeting", "next tuesday"),
        schedule_event("Meeting", "2026-08-12 14:30", duration_minutes=9999),
    ]:
        print(bad.to_text())

    print("\nfile contents:")
    print("-" * 60)
    print(Path(good.path).read_text().replace("\r\n", "\n"))
