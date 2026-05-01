"""Build the 'How we compare' marketing PDF from app/features/page.tsx data."""

from __future__ import annotations
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Table,
    TableStyle,
)

WEDDING_ROSE = colors.HexColor("#D4A5A5")
WEDDING_BLUSH = colors.HexColor("#F8E8E8")
INK = colors.HexColor("#1F1F2A")
SOFT = colors.HexColor("#5C667A")
HAIRLINE = colors.HexColor("#E5E7EB")
GREEN = colors.HexColor("#16A34A")
AMBER = colors.HexColor("#D97706")
GRAY = colors.HexColor("#9CA3AF")

# Source: app/features/page.tsx (April 2026 audit)
ROWS = [
    ("Guest Management & RSVPs", True, "adj", True, True),
    ("Client Portal / Couple Portal", True, "adj", "adj", False),
    ("Built-In Wedding Microsite", True, False, False, False),
    ("SMS & Email Reminders", True, "adj", "adj", True),
    ("Real-Time Push Notifications", True, "adj", False, False),
    ("Inbound Email Threading", True, True, False, False),
    ("Seating Charts", True, False, True, True),
    ("AI Contract Generation & E-Sign", True, "adj", "adj", False),
    ("Service Packages", True, "adj", False, False),
    ("AI Cash Flow Predictions", True, False, False, False),
    ("Budget Management", True, "adj", True, True),
    ("Photo Gallery & Guest QR Uploads", True, False, "adj", False),
    ("Vendor / Contact CRM", True, "adj", "adj", True),
    ("Public Vendor Directory", True, False, False, False),
    ("Contract Vendor Portal (Token-Based)", True, "adj", False, False),
    ("Vendor Advertising Portal", True, False, False, False),
    ("AI Quote Comparison", True, False, False, False),
    ("Couple-Maintained FAQs", True, False, False, False),
    ("Meeting Scheduler", True, True, "adj", "adj"),
    ("Custom Forms & Intake", True, "adj", "adj", True),
    ("Calendar Sync", True, "adj", True, False),
    ("CSV / Google Sheets Guest Import", True, False, True, True),
    ("OTP Guest Access", True, False, False, False),
    ("Team Management & Permissions", True, "adj", "adj", False),
    ("Invoicing & Online Payments", True, "adj", "adj", True),
    ("Enterprise Scaling", True, "adj", False, False),
    ("In-App Support & Knowledge Base", True, "adj", "adj", "adj"),
    ("Day-of / Onsite Check-In", True, False, False, True),
]


def cell(value):
    if value is True:
        return Paragraph('<font color="#16A34A" size="11"><b>✓</b></font>', body_center)
    if value == "adj":
        return Paragraph('<font color="#D97706" size="11"><b>~</b></font>', body_center)
    return Paragraph('<font color="#9CA3AF" size="10">—</font>', body_center)


styles = getSampleStyleSheet()
title_style = ParagraphStyle(
    "Title",
    parent=styles["Title"],
    fontName="Helvetica-Bold",
    fontSize=22,
    leading=26,
    textColor=INK,
    alignment=1,
    spaceAfter=4,
)
subtitle_style = ParagraphStyle(
    "Subtitle",
    parent=styles["Normal"],
    fontName="Helvetica",
    fontSize=10.5,
    leading=14,
    textColor=SOFT,
    alignment=1,
    spaceAfter=14,
)
body_left = ParagraphStyle(
    "BL",
    parent=styles["Normal"],
    fontName="Helvetica",
    fontSize=8.7,
    leading=11,
    textColor=INK,
)
body_center = ParagraphStyle("BC", parent=body_left, alignment=1)
us_header = ParagraphStyle(
    "UH",
    parent=body_center,
    fontName="Helvetica-Bold",
    fontSize=8.5,
    textColor=WEDDING_ROSE,
)
other_header = ParagraphStyle(
    "OH", parent=body_center, fontName="Helvetica-Bold", fontSize=8.5, textColor=SOFT
)
feature_header = ParagraphStyle(
    "FH", parent=body_left, fontName="Helvetica-Bold", fontSize=8.5, textColor=SOFT
)
pricing_label = ParagraphStyle(
    "PL", parent=body_left, fontName="Helvetica-Bold", fontSize=9.5, textColor=INK
)
pricing_us = ParagraphStyle(
    "PU",
    parent=body_center,
    fontName="Helvetica-Bold",
    fontSize=10,
    textColor=WEDDING_ROSE,
)
pricing_other = ParagraphStyle(
    "PO",
    parent=body_center,
    fontName="Helvetica",
    fontSize=9,
    textColor=SOFT,
    leading=11,
)
legend_style = ParagraphStyle(
    "LG",
    parent=styles["Normal"],
    fontName="Helvetica",
    fontSize=7.5,
    leading=10,
    textColor=SOFT,
    alignment=0,
    spaceBefore=8,
)

# Build table data
header = [
    Paragraph("FEATURE", feature_header),
    Paragraph("US", us_header),
    Paragraph("HONEYBOOK", other_header),
    Paragraph("AISLE PLANNER", other_header),
    Paragraph("PLANNING POD", other_header),
]
data = [header]
for f, u, h, a, p in ROWS:
    data.append([Paragraph(f, body_left), cell(u), cell(h), cell(a), cell(p)])
data.append(
    [
        Paragraph("Starting price", pricing_label),
        Paragraph("$29/mo", pricing_us),
        Paragraph('$29/mo<br/><font size="6">(billed annually)</font>', pricing_other),
        Paragraph("$49.99/mo", pricing_other),
        Paragraph("$149/mo", pricing_other),
    ]
)

col_widths = [2.55 * inch, 0.95 * inch, 1.05 * inch, 1.15 * inch, 1.10 * inch]
tbl = Table(data, colWidths=col_widths, repeatRows=1)
ts = TableStyle(
    [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F9FAFB")),
        ("BOX", (0, 0), (-1, -1), 0.5, HAIRLINE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, colors.HexColor("#D1D5DB")),
        ("LINEBELOW", (0, -2), (-1, -2), 0.6, colors.HexColor("#D1D5DB")),
        ("BACKGROUND", (1, 1), (1, -2), WEDDING_BLUSH),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F9FAFB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 9),
        ("TOPPADDING", (0, 1), (-1, -1), 5.5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5.5),
        ("TOPPADDING", (0, -1), (-1, -1), 9),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 9),
    ]
)
# Zebra rows for readability
for i in range(1, len(data) - 1):
    if i % 2 == 0:
        ts.add("BACKGROUND", (0, i), (0, i), colors.HexColor("#FAFAFC"))
        ts.add("BACKGROUND", (2, i), (-1, i), colors.HexColor("#FAFAFC"))
tbl.setStyle(ts)

legend = Paragraph(
    '<font color="#16A34A"><b>✓</b></font>&nbsp;= confirmed&nbsp;&nbsp;&nbsp;'
    '<font color="#D97706"><b>~</b></font>&nbsp;= adjacent capability&nbsp;&nbsp;&nbsp;'
    '<font color="#9CA3AF">—</font>&nbsp;= not found.&nbsp;&nbsp;'
    "Pricing and feature statuses reflect publicly documented capabilities as of April 2026.",
    legend_style,
)

footer = Paragraph(
    '<font color="#9CA3AF" size="7">© The Special Wedding &nbsp;·&nbsp; thespecialwedding.io &nbsp;·&nbsp; Source: /features comparison audit, April 2026</font>',
    ParagraphStyle("FT", parent=styles["Normal"], alignment=1, spaceBefore=14),
)

doc = SimpleDocTemplate(
    "/sessions/clever-cool-allen/mnt/WeddingWebApp/how-we-compare.pdf",
    pagesize=letter,
    leftMargin=0.55 * inch,
    rightMargin=0.55 * inch,
    topMargin=0.55 * inch,
    bottomMargin=0.45 * inch,
    title="How we compare — The Special Wedding",
    author="The Special Wedding",
    subject="Feature comparison: The Special Wedding vs HoneyBook, Aisle Planner, Planning Pod",
)

story = [
    Paragraph("How we compare", title_style),
    Paragraph(
        "The Special Wedding vs the tools you&rsquo;re probably juggling right now.",
        subtitle_style,
    ),
    tbl,
    legend,
    footer,
]
doc.build(story)
print("OK wrote /Users/emmanuelakinwale/Desktop/WeddingWebApp/how-we-compare.pdf")
