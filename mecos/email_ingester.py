"""
MECOS Email Ingestion
======================
Reads an IMAP mailbox (Gmail, Outlook, etc.) and extracts text from
emails and PDF/text attachments into the knowledge pipeline.
"""

import email
import imaplib
import logging
import os
from dataclasses import dataclass
from email.header import decode_header
from io import BytesIO

logger = logging.getLogger(__name__)


@dataclass
class EmailDocument:
    subject: str
    sender: str
    date: str
    body: str
    attachments: list[str]
    uid: str


class EmailIngester:
    """
    Connects to an IMAP server and pulls unread emails as text documents
    ready for the knowledge extraction pipeline.
    """

    def __init__(
        self,
        email_address: str | None = None,
        password: str | None = None,
        imap_host: str = "imap.gmail.com",
        mailbox: str = "INBOX",
    ):
        self.email_address = email_address or os.environ.get("MECOS_EMAIL", "")
        self.password = password or os.environ.get("MECOS_EMAIL_APP_PASSWORD", "")
        self.imap_host = imap_host
        self.mailbox = mailbox

    def fetch_unread(self, max_emails: int = 20) -> list[EmailDocument]:
        """Fetch unread emails from the inbox."""
        if not self.email_address or not self.password:
            logger.warning("Email credentials not set. Set MECOS_EMAIL and MECOS_EMAIL_APP_PASSWORD.")
            return []

        docs = []
        try:
            with imaplib.IMAP4_SSL(self.imap_host) as imap:
                imap.login(self.email_address, self.password)
                imap.select(self.mailbox)

                _, uids = imap.search(None, "UNSEEN")
                uid_list = uids[0].split()[-max_emails:]

                for uid in uid_list:
                    try:
                        _, data = imap.fetch(uid, "(RFC822)")
                        raw = data[0][1]
                        message = email.message_from_bytes(raw)
                        doc = self._parse_message(message, uid.decode())
                        if doc:
                            docs.append(doc)
                    except Exception as exc:
                        logger.warning("Failed to parse email %s: %s", uid, exc)

        except Exception as exc:
            logger.error("IMAP connection failed: %s", exc)

        logger.info("Fetched %d emails from %s", len(docs), self.email_address)
        return docs

    def _parse_message(self, message, uid: str) -> EmailDocument | None:
        subject = self._decode_header(message.get("Subject", "(no subject)"))
        sender = self._decode_header(message.get("From", ""))
        date = message.get("Date", "")

        body = ""
        attachments = []

        if message.is_multipart():
            for part in message.walk():
                content_type = part.get_content_type()
                disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in disposition:
                    attach_text = self._extract_attachment(part)
                    if attach_text:
                        attachments.append(attach_text)
                elif content_type == "text/plain" and not body:
                    body = self._decode_payload(part)
                elif content_type == "text/html" and not body:
                    html = self._decode_payload(part)
                    body = self._strip_html(html)
        else:
            body = self._decode_payload(message)

        if not body and not attachments:
            return None

        return EmailDocument(
            subject=subject,
            sender=sender,
            date=date,
            body=body,
            attachments=attachments,
            uid=uid,
        )

    def _extract_attachment(self, part) -> str:
        """Extract text from PDF or plain text attachments."""
        filename = part.get_filename() or ""
        payload = part.get_payload(decode=True)
        if not payload:
            return ""

        if filename.lower().endswith(".pdf"):
            return self._extract_pdf_text(payload)
        if filename.lower().endswith((".txt", ".md")):
            try:
                return payload.decode("utf-8", errors="ignore")
            except Exception:
                return ""
        return ""

    def _extract_pdf_text(self, data: bytes) -> str:
        try:
            import pypdf

            reader = pypdf.PdfReader(BytesIO(data))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError:
            logger.warning("pypdf not installed. Run: pip install pypdf")
            return ""
        except Exception as exc:
            logger.warning("PDF extraction failed: %s", exc)
            return ""

    @staticmethod
    def _decode_header(value: str) -> str:
        parts = decode_header(value)
        decoded = []
        for part, encoding in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(encoding or "utf-8", errors="ignore"))
            else:
                decoded.append(part)
        return " ".join(decoded)

    @staticmethod
    def _decode_payload(part) -> str:
        payload = part.get_payload(decode=True)
        if not payload:
            return ""
        charset = part.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="ignore")

    @staticmethod
    def _strip_html(html: str) -> str:
        try:
            from bs4 import BeautifulSoup

            return BeautifulSoup(html, "html.parser").get_text(separator="\n", strip=True)
        except ImportError:
            import re

            return re.sub(r"<[^>]+>", " ", html)
