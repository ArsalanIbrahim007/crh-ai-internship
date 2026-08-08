"""Email drafting.

Writes a real RFC 5322 message to disk as a .eml file, which opens directly in Outlook,
Thunderbird or Apple Mail. Nothing is sent - drafting and sending are different problems,
and an agent that can send email unsupervised is a bad idea.

Using the stdlib email module rather than writing the headers by hand means encoding,
line folding and non-ASCII subjects are handled correctly.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from pathlib import Path

OUTBOX = Path(__file__).resolve().parent.parent / "outputs" / "drafts"
SENDER = "bi-copilot@example.com"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_BODY_CHARS = 8000


@dataclass
class DraftResult:
    ok: bool
    path: str = ""
    to: str = ""
    subject: str = ""
    error: str = ""

    def to_text(self) -> str:
        if not self.ok:
            return f"EMAIL ERROR: {self.error}"
        return (f"Draft saved to {self.path}\n"
                f"To: {self.to}\nSubject: {self.subject}\n"
                f"Nothing was sent - this is a draft file.")


def _safe_filename(subject: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", subject).strip("-").lower()[:50] or "draft"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{slug}.eml"


def draft_email(to: str, subject: str, body: str) -> DraftResult:
    """Write an email draft to disk. Does not send."""
    to = (to or "").strip()
    subject = (subject or "").strip()
    body = (body or "").strip()

    if not EMAIL_RE.match(to):
        return DraftResult(ok=False, error=f"'{to}' is not a valid email address.")
    if not subject:
        return DraftResult(ok=False, error="Subject is required.")
    if not body:
        return DraftResult(ok=False, error="Body is required.")
    if len(body) > MAX_BODY_CHARS:
        return DraftResult(ok=False,
                           error=f"Body exceeds {MAX_BODY_CHARS} characters.")

    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = format_datetime(datetime.now(timezone.utc))
    msg["Message-ID"] = make_msgid(domain="example.com")
    # Marks the file as a draft rather than a received message.
    msg["X-Unsent"] = "1"
    msg.set_content(body)

    OUTBOX.mkdir(parents=True, exist_ok=True)
    path = OUTBOX / _safe_filename(subject)
    path.write_bytes(bytes(msg))

    return DraftResult(ok=True, path=str(path), to=to, subject=subject)


if __name__ == "__main__":
    good = draft_email(
        to="contact@northwindsystems.com",
        subject="Renewal discussion for your analytics platform licence",
        body=("Hi,\n\nYour Analytics Platform - Enterprise licence comes up for renewal "
              "next quarter. Could we find 30 minutes to review your usage and discuss "
              "options?\n\nBest regards,\nAccount Team"),
    )
    print(good.to_text())
    print()

    for bad in [
        draft_email("not-an-email", "Test", "Body"),
        draft_email("a@b.com", "", "Body"),
        draft_email("a@b.com", "Subject", ""),
    ]:
        print(bad.to_text())

    # confirm the file is a parseable message, not just text on disk
    import email
    saved = email.message_from_bytes(Path(good.path).read_bytes())
    print("\nparsed back:")
    print("  To:     ", saved["To"])
    print("  Subject:", saved["Subject"])
    print("  Draft:  ", saved["X-Unsent"] == "1")
