"""
email_service.py – Send treasurer reports via Gmail SMTP.

Requires environment variables: GMAIL_USER, GMAIL_APP_PASSWORD
"""

import os
import smtplib
import tempfile
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

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
    """Generate PDF from Excel and email it to the treasurer via Gmail SMTP."""
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

    # 4. Send email via Gmail SMTP
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print(f"[EMAIL] GMAIL credentials not set — would send to {to_email}", flush=True)
        return

    month_he = MONTHS_HE.get(month, str(month))
    subject = f"דוח גזבר רווחה — {muni_name} {month_he}/{year}"
    pdf_filename = f"treasurer_report_{muni_name}_{month}_{year}.pdf"

    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = subject

    html = f"""\
    <div dir="rtl" style="font-family: Arial, sans-serif;">
        <h2>דוח גזבר רווחה</h2>
        <p><strong>רשות:</strong> {muni_name}</p>
        <p><strong>תקופה:</strong> {month_he} {year}</p>
        <p>הדוח מצורף כ-PDF.</p>
        <hr>
        <p style="color: #999; font-size: 12px;">נשלח אוטומטית ממערכת יומנית</p>
    </div>
    """
    msg.attach(MIMEText(html, "html", "utf-8"))

    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header("Content-Disposition", "attachment", filename=pdf_filename)
    msg.attach(attachment)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)

    print(f"[EMAIL] Sent to {to_email} via Gmail SMTP", flush=True)
