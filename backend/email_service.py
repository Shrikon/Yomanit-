"""
email_service.py – Send treasurer reports via SendGrid.

Requires SENDGRID_API_KEY environment variable.
"""

import os
import base64
import tempfile
from pathlib import Path

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@yomanit.co.il")

MONTHS_HE = {
    1: "ינואר", 2: "פברואר", 3: "מרץ", 4: "אפריל",
    5: "מאי", 6: "יוני", 7: "יולי", 8: "אוגוסט",
    9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר",
}


async def send_treasurer_report(
    municipality_id: str,
    excel_bytes: bytes,
    month: int,
    year: int,
):
    """Generate PDF from Excel and email it to the treasurer."""
    import db

    # 1. Get treasurer email
    row = await db.fetch_one(
        """SELECT value FROM municipality_settings
           WHERE municipality_id = :muni AND key = 'treasurer_email'""",
        values={"muni": municipality_id},
    )
    if not row or not row["value"]:
        print("[EMAIL] No treasurer_email configured — skipping", flush=True)
        return

    to_email = row["value"].strip()

    # 2. Get municipality name
    muni_row = await db.fetch_one(
        "SELECT name FROM municipalities WHERE id = :id",
        values={"id": municipality_id},
    )
    muni_name = muni_row["name"] if muni_row else municipality_id

    # 3. Generate PDF from Excel
    from welfare_report_analyzer import parse_excel, generate_pdf

    tmp_excel = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    try:
        tmp_excel.write(excel_bytes)
        tmp_excel.close()
        tmp_pdf.close()

        report = parse_excel(tmp_excel.name)
        generate_pdf(report, tmp_pdf.name)

        with open(tmp_pdf.name, "rb") as f:
            pdf_bytes = f.read()
    finally:
        os.unlink(tmp_excel.name)
        try:
            os.unlink(tmp_pdf.name)
        except OSError:
            pass

    # 4. Send email via SendGrid
    if not SENDGRID_API_KEY:
        print(f"[EMAIL] SENDGRID_API_KEY not set — would send to {to_email}", flush=True)
        return

    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import (
        Mail, Attachment, FileContent, FileName, FileType, Disposition,
    )

    month_he = MONTHS_HE.get(month, str(month))
    subject = f"דוח גזבר רווחה — {muni_name} {month_he}/{year}"
    filename = f"treasurer_report_{muni_name}_{month}_{year}.pdf"

    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=to_email,
        subject=subject,
        html_content=f"""
        <div dir="rtl" style="font-family: Arial, sans-serif;">
            <h2>דוח גזבר רווחה</h2>
            <p><strong>רשות:</strong> {muni_name}</p>
            <p><strong>תקופה:</strong> {month_he} {year}</p>
            <p>הדוח מצורף כ-PDF.</p>
            <hr>
            <p style="color: #999; font-size: 12px;">נשלח אוטומטית ממערכת יומנית</p>
        </div>
        """,
    )

    attachment = Attachment(
        FileContent(base64.b64encode(pdf_bytes).decode()),
        FileName(filename),
        FileType("application/pdf"),
        Disposition("attachment"),
    )
    message.attachment = attachment

    sg = SendGridAPIClient(SENDGRID_API_KEY)
    response = sg.send(message)
    print(f"[EMAIL] Sent to {to_email}: status={response.status_code}", flush=True)
