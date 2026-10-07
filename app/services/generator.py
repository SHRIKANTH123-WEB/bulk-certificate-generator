import os
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.pdfgen import canvas


class CertificateRenderer:
    """
    Renders high-quality, professional PDF certificates in landscape orientation.
    Uses standard built-in ReportLab canvas shapes and Helvetica fonts for zero external asset dependencies.
    """

    @staticmethod
    def generate_pdf(
        output_path: str,
        recipient_name: str,
        certificate_title: str,
        issuer_name: str,
        issue_date: str,
        description: str = "",
        custom_message: str = "",
        certificate_id: str = ""
    ) -> str:
        # Standard US Letter Landscape: 792 x 612 pt
        width, height = landscape(letter)

        # Ensure target directory exists
        parent_dir = os.path.dirname(output_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        c = canvas.Canvas(output_path, pagesize=landscape(letter))

        # 1. Background fill (soft warm ivory)
        c.setFillColor(colors.HexColor("#FCFDFD"))
        c.rect(0, 0, width, height, stroke=0, fill=1)

        # 2. Outer decorative border (Navy Blue)
        c.setStrokeColor(colors.HexColor("#1A365D"))
        c.setLineWidth(5)
        c.rect(24, 24, width - 48, height - 48, stroke=1, fill=0)

        # 3. Inner decorative border (Warm Gold)
        c.setStrokeColor(colors.HexColor("#D4AF37"))
        c.setLineWidth(1.5)
        c.rect(32, 32, width - 64, height - 64, stroke=1, fill=0)

        # 4. Corner Accents (Gold corner brackets)
        accent_len = 25
        c.setStrokeColor(colors.HexColor("#D4AF37"))
        c.setLineWidth(3)
        # Top-Left
        c.line(40, height - 40, 40 + accent_len, height - 40)
        c.line(40, height - 40, 40, height - 40 - accent_len)
        # Top-Right
        c.line(width - 40, height - 40, width - 40 - accent_len, height - 40)
        c.line(width - 40, height - 40, width - 40, height - 40 - accent_len)
        # Bottom-Left
        c.line(40, 40, 40 + accent_len, 40)
        c.line(40, 40, 40, 40 + accent_len)
        # Bottom-Right
        c.line(width - 40, 40, width - 40 - accent_len, 40)
        c.line(width - 40, 40, width - 40, 40 + accent_len)

        # 5. Header / Organization Badge
        c.setFillColor(colors.HexColor("#D4AF37"))
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(width / 2.0, height - 85, "★ OFFICIAL RECOGNITION ★")

        # 6. Certificate Title
        c.setFillColor(colors.HexColor("#1A365D"))
        c.setFont("Helvetica-Bold", 30)
        c.drawCentredString(width / 2.0, height - 130, certificate_title.upper())

        # Subtitle
        c.setFillColor(colors.HexColor("#64748B"))
        c.setFont("Helvetica-Oblique", 13)
        c.drawCentredString(width / 2.0, height - 165, "THIS IS PROUDLY PRESENTED TO")

        # 7. Recipient Name
        c.setFillColor(colors.HexColor("#0F172A"))
        c.setFont("Helvetica-Bold", 28)
        c.drawCentredString(width / 2.0, height - 215, recipient_name)

        # Gold underline beneath recipient name
        c.setStrokeColor(colors.HexColor("#D4AF37"))
        c.setLineWidth(2)
        c.line(width / 2.0 - 180, height - 227, width / 2.0 + 180, height - 227)

        # 8. Description Clause
        c.setFillColor(colors.HexColor("#334155"))
        c.setFont("Helvetica", 13)
        desc_text = description if description else "for successfully completing the course requirements."
        c.drawCentredString(width / 2.0, height - 270, desc_text)

        # 9. Optional Custom Message
        if custom_message:
            c.setFillColor(colors.HexColor("#475569"))
            c.setFont("Helvetica-Oblique", 11)
            c.drawCentredString(width / 2.0, height - 305, f'"{custom_message}"')

        # 10. Issuer & Date Signatures Section
        y_sig = 120

        # Left Column: Date of Issuance
        c.setStrokeColor(colors.HexColor("#94A3B8"))
        c.setLineWidth(1)
        c.line(120, y_sig, 280, y_sig)
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.HexColor("#0F172A"))
        c.drawCentredString(200, y_sig + 8, issue_date)
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.HexColor("#64748B"))
        c.drawCentredString(200, y_sig - 16, "Date of Issuance")

        # Right Column: Authorized Issuer
        c.line(width - 280, y_sig, width - 120, y_sig)
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.HexColor("#0F172A"))
        c.drawCentredString(width - 200, y_sig + 8, issuer_name)
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.HexColor("#64748B"))
        c.drawCentredString(width - 200, y_sig - 16, "Authorized Signature")

        # 11. Center Seal / Stamp
        seal_x = width / 2.0
        seal_y = y_sig
        c.setStrokeColor(colors.HexColor("#D4AF37"))
        c.setLineWidth(2)
        c.circle(seal_x, seal_y, 30, stroke=1, fill=0)
        c.circle(seal_x, seal_y, 26, stroke=1, fill=0)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(colors.HexColor("#D4AF37"))
        c.drawCentredString(seal_x, seal_y + 4, "VERIFIED")
        c.drawCentredString(seal_x, seal_y - 8, "EXCELLENCE")

        # 12. Certificate Identifier at bottom
        if certificate_id:
            c.setFont("Helvetica", 8)
            c.setFillColor(colors.HexColor("#94A3B8"))
            c.drawCentredString(width / 2.0, 50, f"Certificate ID: {certificate_id}")

        c.showPage()
        c.save()
        return output_path
