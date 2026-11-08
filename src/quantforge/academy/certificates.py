r"""Verifiable completion certificates.

Certificate IDs are signed with HMAC-SHA256 using a server secret
(``QUANTFORGE_CERT_SECRET``). The ID encodes the chapter and the date; the
signature binds them to the holder's name. Anyone can verify an ID + name on the
app's verification page, and nobody without the secret can forge one.

Format: ``QF-CC-YYYYMMDD-XXXXXXXXXX`` (CC = chapter, ``00`` = full program).

Without a secret configured, a fixed development key is used and certificates are
marked *development* — they verify only on deployments using the same default and
must not be presented as official.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

__all__ = ["make_certificate_id", "verify_certificate", "certificate_pdf", "CertificateInfo",
           "is_development_mode", "sign_progress", "verify_progress"]

_DEV_SECRET = "quantforge-development-secret-do-not-use-in-production"
_ID_RE = re.compile(r"^QF-(\d{2})-(\d{8})-([0-9A-F]{10})$")


def _secret() -> bytes:
    secret = os.environ.get("QUANTFORGE_CERT_SECRET", "").strip()
    return (secret or _DEV_SECRET).encode()      # an empty value means "not configured"


def is_development_mode() -> bool:
    return not os.environ.get("QUANTFORGE_CERT_SECRET", "").strip()


def _normalize(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _signature(name: str, chapter: int, day: date) -> str:
    msg = f"{_normalize(name)}|{chapter:02d}|{day:%Y%m%d}".encode()
    return hmac.new(_secret(), msg, hashlib.sha256).hexdigest()[:10].upper()


def make_certificate_id(name: str, chapter: int, day: date | None = None) -> str:
    if not name.strip():
        raise ValueError("a name is required")
    day = day or date.today()
    return f"QF-{chapter:02d}-{day:%Y%m%d}-{_signature(name, chapter, day)}"


def sign_progress(progress: dict) -> dict:
    """Return a copy of an Academy progress record with an HMAC seal.

    The seal stops anyone from editing a saved progress file to unlock certificates for
    quizzes they never passed."""
    body = {"passed": progress.get("passed", {}), "read": sorted(progress.get("read", [])),
            "exercises": sorted(progress.get("exercises", [])),
            "name": str(progress.get("name", ""))}
    msg = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return {**body, "seal": hmac.new(_secret(), msg, hashlib.sha256).hexdigest()}


def verify_progress(data: dict) -> dict | None:
    """Return the progress record if its seal is intact, else ``None``."""
    if not isinstance(data, dict) or "seal" not in data:
        return None
    try:
        expected = sign_progress(data)["seal"]
    except (TypeError, ValueError):
        return None
    if not hmac.compare_digest(str(data["seal"]), expected):
        return None
    return {"passed": dict(data["passed"]), "read": list(data["read"]),
            "exercises": list(data.get("exercises", [])), "name": str(data.get("name", ""))}


@dataclass(frozen=True)
class CertificateInfo:
    valid: bool
    chapter: int | None = None
    issued: date | None = None
    reason: str = ""


def verify_certificate(cert_id: str, name: str) -> CertificateInfo:
    m = _ID_RE.match(cert_id.strip().upper())
    if not m:
        return CertificateInfo(False, reason="Malformed certificate ID.")
    chapter, ds, sig = int(m.group(1)), m.group(2), m.group(3)
    try:
        day = date(int(ds[:4]), int(ds[4:6]), int(ds[6:]))
    except ValueError:
        return CertificateInfo(False, reason="Invalid date in certificate ID.")
    if not hmac.compare_digest(sig, _signature(name, chapter, day)):
        return CertificateInfo(False, chapter, day, "The ID does not match this name.")
    return CertificateInfo(True, chapter, day, "Valid certificate.")


def certificate_pdf(name: str, title: str, subtitle: str, cert_id: str, score: float | None,
                    day: date, logo_path: str | Path | None = None,
                    issuer: str = "quantforge Academy", signatory: str = "",
                    verify_url: str = "", pass_mark: float = 0.8) -> bytes:
    """Landscape A4 PDF certificate (reportlab). Returns the PDF bytes."""
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas

    red, ink, grey = HexColor("#E4141D"), HexColor("#0B0B0C"), HexColor("#5E5E66")
    white, soft = HexColor("#FFFFFF"), HexColor("#B9B9C0")
    buf = io.BytesIO()
    w, h = landscape(A4)
    c = canvas.Canvas(buf, pagesize=(w, h))
    c.setTitle(f"{issuer} certificate — {name}")
    c.setAuthor(issuer)
    # black page, white card
    c.setFillColor(ink)
    c.rect(0, 0, w, h, fill=1, stroke=0)
    m = 22
    c.setFillColor(white)
    c.roundRect(m, m, w - 2 * m, h - 2 * m, 12, fill=1, stroke=0)
    # black header band with the logo and issuer
    band = 118
    c.setFillColor(ink)
    c.rect(m, h - m - band, w - 2 * m, band, fill=1, stroke=0)
    c.roundRect(m, h - m - 30, w - 2 * m, 30, 12, fill=1, stroke=0)
    c.setFillColor(red)
    c.rect(m, h - m - band - 5, w - 2 * m, 5, fill=1, stroke=0)
    if logo_path and Path(logo_path).exists():
        c.drawImage(str(logo_path), 60, h - m - band + 14, 90, 90, mask="auto")
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(168, h - m - 58, issuer.upper())
    c.setFillColor(soft)
    c.setFont("Helvetica", 12)
    c.drawString(168, h - m - 80, "CERTIFICATE OF COMPLETION")
    c.setFillColor(red)
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(w - 60, h - m - 58, "QUANTITATIVE FINANCE")
    c.setFillColor(soft)
    c.setFont("Helvetica", 10)
    c.drawRightString(w - 60, h - m - 76, day.strftime("%B %d, %Y"))
    # body
    y0 = h - m - band - 82
    c.setFillColor(grey)
    c.setFont("Helvetica", 13)
    c.drawCentredString(w / 2, y0, "This certifies that")
    c.setFillColor(ink)
    size = 32 if len(name.strip()) <= 28 else 24
    c.setFont("Helvetica-Bold", size)
    c.drawCentredString(w / 2, y0 - 44, name.strip())
    c.setStrokeColor(ink)
    c.setLineWidth(0.8)
    c.line(w / 2 - 190, y0 - 56, w / 2 + 190, y0 - 56)
    c.setFillColor(grey)
    c.setFont("Helvetica", 13)
    c.drawCentredString(w / 2, y0 - 82, "has successfully completed")
    c.setFillColor(red)
    c.setFont("Helvetica-Bold", 17 if len(title) <= 60 else 14)
    c.drawCentredString(w / 2, y0 - 110, title)
    c.setFillColor(ink)
    c.setFont("Helvetica", 12)
    c.drawCentredString(w / 2, y0 - 132, subtitle)
    if score is not None:
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(w / 2, y0 - 154, f"Assessment score: {score:.0%}")
    # signature
    if signatory:
        c.setStrokeColor(ink)
        c.line(w - 290, 140, w - 70, 140)
        c.setFillColor(ink)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(w - 180, 126, signatory)
        c.setFillColor(grey)
        c.setFont("Helvetica", 9)
        c.drawCentredString(w - 180, 113, issuer)
    # red accent mark, left
    c.setFillColor(red)
    c.rect(70, 126, 36, 4, fill=1, stroke=0)
    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(70, 112, "Verified skills")
    c.setFillColor(grey)
    c.setFont("Helvetica", 9)
    c.drawString(70, 99, f"Lesson completed and quiz passed ({pass_mark:.0%} required)")
    # black footer band
    fb = 64
    c.setFillColor(ink)
    c.rect(m, m + 10, w - 2 * m, fb - 10, fill=1, stroke=0)
    c.roundRect(m, m, w - 2 * m, 30, 12, fill=1, stroke=0)
    c.setFillColor(red)
    c.rect(m, m + fb, w - 2 * m, 3, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(60, m + 44, f"Certificate ID  {cert_id}")
    c.setFont("Helvetica", 9)
    c.drawRightString(w - 60, m + 44, f"Issued {day:%B %d, %Y}")
    c.setFillColor(soft)
    c.drawString(60, m + 29, f"Verify at {verify_url}" if verify_url else
                 "Verify online: quantforge app > Learn > Verify a certificate")
    note = ("Educational certificate. Not an academic degree, a professional license or a "
            "regulatory qualification.")
    if is_development_mode():
        note = "DEVELOPMENT CERTIFICATE (not issued by an official deployment). " + note
    c.setFont("Helvetica-Oblique", 7.5)
    c.drawString(60, m + 15, note)
    c.showPage()
    c.save()
    return buf.getvalue()
