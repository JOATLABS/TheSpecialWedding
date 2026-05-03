"""Build The Special Wedding brand guidelines PDF.

Output: /sessions/cool-eager-cori/mnt/WeddingWebApp/docs/brand/the-special-wedding-brand-guidelines.pdf
(maps to user's /Users/emmanuelakinwale/Desktop/WeddingWebApp/docs/brand/...)
"""

import os

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.graphics.shapes import (
    Circle,
    Drawing,
    Path,
    Rect,
    String,
)


# ── Brand palette ──────────────────────────────────────────────────────────
ROSE_HIGHLIGHT = HexColor("#FFE5DC")
ROSE_PRIMARY = HexColor("#E8B4B8")
ROSE_ACCENT = HexColor("#C8847E")
ROSE_MID = HexColor("#A87278")
ROSE_DEEP = HexColor("#7A4B50")
ROSE_BURGUNDY = HexColor("#5C2F34")
ROSE_OUTLINE = HexColor("#3D1418")
ROSE_NEAR_BLACK = HexColor("#1F0A0C")

NAVY = HexColor("#1e3a5f")
GOLD = HexColor("#d4af37")
SLATE_DARK = HexColor("#0b1120")
SLATE_950 = HexColor("#0f172a")
INK = HexColor("#1a1a1a")
INK_60 = HexColor("#5c5c5c")
INK_40 = HexColor("#8a8a8a")
PAPER = HexColor("#fdfaf6")
PAPER_2 = HexColor("#f3eee6")
LINE = HexColor("#d8cfc3")


# ── Document setup ─────────────────────────────────────────────────────────
OUTPUT_DIR = "/sessions/cool-eager-cori/mnt/WeddingWebApp/docs/brand"
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "the-special-wedding-brand-guidelines.pdf")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── Styles ─────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

H_DISPLAY = ParagraphStyle(
    "HDisplay",
    parent=styles["Heading1"],
    fontName="Times-Bold",
    fontSize=42,
    leading=46,
    textColor=ROSE_BURGUNDY,
    alignment=TA_LEFT,
    spaceAfter=10,
)

H_EYEBROW = ParagraphStyle(
    "HEyebrow",
    parent=styles["Normal"],
    fontName="Times-Italic",
    fontSize=10,
    leading=14,
    textColor=ROSE_DEEP,
    alignment=TA_LEFT,
    spaceAfter=2,
    letterSpace=2.5,
)

H1 = ParagraphStyle(
    "H1",
    parent=styles["Heading1"],
    fontName="Times-Bold",
    fontSize=26,
    leading=30,
    textColor=ROSE_BURGUNDY,
    spaceBefore=20,
    spaceAfter=12,
)

H2 = ParagraphStyle(
    "H2",
    parent=styles["Heading2"],
    fontName="Times-Bold",
    fontSize=16,
    leading=20,
    textColor=ROSE_DEEP,
    spaceBefore=14,
    spaceAfter=6,
)

H3 = ParagraphStyle(
    "H3",
    parent=styles["Heading3"],
    fontName="Helvetica-Bold",
    fontSize=10,
    leading=13,
    textColor=ROSE_DEEP,
    spaceBefore=8,
    spaceAfter=2,
)

BODY = ParagraphStyle(
    "Body",
    parent=styles["Normal"],
    fontName="Helvetica",
    fontSize=10,
    leading=15,
    textColor=INK,
    spaceAfter=6,
)

BODY_MUTED = ParagraphStyle(
    "BodyMuted",
    parent=BODY,
    textColor=INK_60,
    fontSize=9,
    leading=13,
)

BODY_SMALL = ParagraphStyle(
    "BodySmall",
    parent=BODY,
    fontSize=8.5,
    leading=12,
)

EYEBROW_LABEL = ParagraphStyle(
    "EyebrowLabel",
    parent=styles["Normal"],
    fontName="Helvetica-Bold",
    fontSize=8,
    leading=10,
    textColor=ROSE_ACCENT,
    spaceAfter=4,
)

CODE = ParagraphStyle(
    "Code",
    parent=BODY,
    fontName="Courier",
    fontSize=9,
    leading=13,
    textColor=INK,
)


# ── Helpers ────────────────────────────────────────────────────────────────
def page_decoration(canvas, doc):
    """Draw the running header/footer on every page."""
    canvas.saveState()

    # Footer line
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(
        doc.leftMargin,
        doc.bottomMargin - 24,
        doc.width + doc.leftMargin,
        doc.bottomMargin - 24,
    )

    # Footer brand text
    canvas.setFont("Times-Italic", 9)
    canvas.setFillColor(ROSE_DEEP)
    canvas.drawString(
        doc.leftMargin,
        doc.bottomMargin - 38,
        "The Special Wedding · Brand & Design Guidelines",
    )

    # Page number
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(INK_40)
    canvas.drawRightString(
        doc.width + doc.leftMargin,
        doc.bottomMargin - 38,
        f"Page {doc.page}",
    )

    canvas.restoreState()


def cover_decoration(canvas, doc):
    """Cover page is plain — no header/footer."""
    canvas.saveState()
    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, letter[0], letter[1], stroke=0, fill=1)
    canvas.restoreState()


def draw_logo_lockup(width, height, surface="dark", show_tagline=True, scale=1.0):
    """Render the brand lockup as a reportlab Drawing (icon + wordmark + tagline)."""
    d = Drawing(width, height)

    # Background fill matches surface so it reads against PDF page
    if surface == "dark":
        bg_color = SLATE_DARK
        wordmark_color = ROSE_PRIMARY
        eyebrow_color = ROSE_HIGHLIGHT
        tagline_color = HexColor("#a8a8b8")
    else:
        bg_color = PAPER
        wordmark_color = ROSE_BURGUNDY
        eyebrow_color = ROSE_MID
        tagline_color = HexColor("#7a5a5e")

    d.add(Rect(0, 0, width, height, strokeColor=None, fillColor=bg_color))

    # Icon — two interlocking rings + heart
    # Icon area takes left ~25% of width
    icon_size = min(height * 0.7, width * 0.22) * scale
    icon_cx = width * 0.10
    icon_cy = height * 0.5

    # Convert from our 60×60 viewBox to actual coords
    s = icon_size / 60.0
    ox = icon_cx - 30 * s
    oy = icon_cy - 30 * s

    # Two rings in rose gradient — flatten to mid-rose + outline pass to suggest 3D
    ring_color = ROSE_PRIMARY
    ring_outline = ROSE_BURGUNDY
    # Ring 1
    d.add(
        Circle(
            ox + 24 * s,
            oy + 30 * s,
            11 * s,
            strokeColor=ring_color,
            strokeWidth=5.5 * s,
            fillColor=None,
        )
    )
    # Ring 2
    d.add(
        Circle(
            ox + 36 * s,
            oy + 30 * s,
            11 * s,
            strokeColor=ring_color,
            strokeWidth=5.5 * s,
            fillColor=None,
        )
    )
    # Highlight rim on rings (top-left light)
    d.add(
        Circle(
            ox + 24 * s,
            oy + 30 * s,
            11 * s,
            strokeColor=ROSE_HIGHLIGHT,
            strokeWidth=1.2 * s,
            fillColor=None,
        )
    )
    d.add(
        Circle(
            ox + 36 * s,
            oy + 30 * s,
            11 * s,
            strokeColor=ROSE_HIGHLIGHT,
            strokeWidth=1.2 * s,
            fillColor=None,
        )
    )
    # Heart — solid filled rose with outline
    heart_path = Path(
        strokeColor=ring_outline, strokeWidth=0.5 * s, fillColor=ROSE_ACCENT
    )
    heart_path.moveTo(ox + 30 * s, oy + 27 * s)
    heart_path.curveTo(
        ox + 28 * s, oy + 24 * s, ox + 24 * s, oy + 24 * s, ox + 24 * s, oy + 27 * s
    )
    heart_path.curveTo(
        ox + 24 * s, oy + 31 * s, ox + 30 * s, oy + 36 * s, ox + 30 * s, oy + 36 * s
    )
    heart_path.curveTo(
        ox + 30 * s, oy + 36 * s, ox + 36 * s, oy + 31 * s, ox + 36 * s, oy + 27 * s
    )
    heart_path.curveTo(
        ox + 36 * s, oy + 24 * s, ox + 32 * s, oy + 24 * s, ox + 30 * s, oy + 27 * s
    )
    heart_path.closePath()
    d.add(heart_path)
    # Heart highlight (small bright spot)
    d.add(
        Circle(
            ox + 27 * s,
            oy + 27 * s,
            1.2 * s,
            strokeColor=None,
            fillColor=ROSE_HIGHLIGHT,
        )
    )

    # Wordmark — to the right of icon
    text_x = icon_cx + icon_size * 0.7
    eyebrow_y = icon_cy + icon_size * 0.18
    headline_y = icon_cy - icon_size * 0.18
    tagline_y = icon_cy - icon_size * 0.42

    eyebrow = String(
        text_x,
        eyebrow_y,
        "THE SPECIAL",
        fontName="Times-Italic",
        fontSize=icon_size * 0.18,
        fillColor=eyebrow_color,
    )
    eyebrow.textAnchor = "start"
    d.add(eyebrow)

    headline = String(
        text_x,
        headline_y,
        "Wedding",
        fontName="Times-Bold",
        fontSize=icon_size * 0.55,
        fillColor=wordmark_color,
    )
    headline.textAnchor = "start"
    d.add(headline)

    if show_tagline:
        tagline_full = String(
            text_x,
            tagline_y,
            "A JOATLABS.DEV PLATFORM",
            fontName="Helvetica",
            fontSize=icon_size * 0.16,
            fillColor=tagline_color,
        )
        tagline_full.textAnchor = "start"
        d.add(tagline_full)

    return d


def draw_color_swatch(width, height, color, label, value, text_on="dark"):
    d = Drawing(width, height)
    d.add(Rect(0, 0, width, height, strokeColor=LINE, strokeWidth=0.5, fillColor=color))

    text_color = HexColor("#FFFFFF") if text_on == "dark" else INK
    d.add(
        String(
            10,
            height - 18,
            label,
            fontName="Helvetica-Bold",
            fontSize=9,
            fillColor=text_color,
        )
    )
    d.add(String(10, 12, value, fontName="Courier", fontSize=8, fillColor=text_color))

    return d


def draw_typography_specimen(width, height, text, font, size, color):
    d = Drawing(width, height)
    s = String(
        0, height - size * 0.95, text, fontName=font, fontSize=size, fillColor=color
    )
    s.textAnchor = "start"
    d.add(s)
    return d


# ── Build content ──────────────────────────────────────────────────────────
def build_cover():
    """Cover page elements."""
    elements = []

    # Big lockup — fills upper portion of cover
    elements.append(Spacer(1, 1.2 * inch))
    elements.append(
        draw_logo_lockup(
            6.5 * inch, 1.8 * inch, surface="light", show_tagline=True, scale=1.4
        )
    )
    elements.append(Spacer(1, 0.6 * inch))

    # Title block
    title = ParagraphStyle(
        "CoverTitle",
        parent=styles["Title"],
        fontName="Times-Bold",
        fontSize=48,
        leading=52,
        textColor=ROSE_BURGUNDY,
        alignment=TA_LEFT,
        spaceAfter=14,
    )
    subtitle = ParagraphStyle(
        "CoverSub",
        parent=styles["Normal"],
        fontName="Times-Italic",
        fontSize=18,
        leading=24,
        textColor=ROSE_DEEP,
        alignment=TA_LEFT,
        spaceAfter=24,
    )
    meta = ParagraphStyle(
        "CoverMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=INK_60,
        alignment=TA_LEFT,
    )

    elements.append(Paragraph("Brand &amp; Design Guidelines", title))
    elements.append(
        Paragraph("For marketing partners, designers, and engineers", subtitle)
    )

    elements.append(Spacer(1, 0.4 * inch))
    elements.append(Paragraph("Version 2.0 — A JOATLABS.DEV PLATFORM", meta))
    elements.append(
        Paragraph("Issued April 2026 by Etastic on behalf of The Special Wedding", meta)
    )

    return elements


def build_intro():
    elements = []
    elements.append(Paragraph("About this document", H1))
    elements.append(
        Paragraph(
            "This guide is the source of truth for The Special Wedding's visual identity — the logo, "
            "colors, typography, and component patterns used across the platform and every customer-"
            "facing surface. Apply it consistently across marketing, sales collateral, partner assets, "
            "social, email, and product UI.",
            BODY,
        )
    )
    elements.append(
        Paragraph(
            "If you're an external partner or marketing agency, follow these rules without deviation. "
            "If you're an engineer building product, the canonical implementation lives in "
            "<font name='Courier'>app/components/brand/BrandLockup.tsx</font> — that component is the "
            "source of truth and the SVG files in <font name='Courier'>/public</font> are static "
            "fallbacks for places that need raw SVG.",
            BODY,
        )
    )

    elements.append(Paragraph("What you can change vs. what's locked", H2))

    rules_data = [
        [
            Paragraph("<b>Locked</b>", BODY),
            Paragraph(
                "Logo composition (rings + heart + wordmark), color family (rose), typography pairing (Georgia + Helvetica), tagline phrasing.",
                BODY,
            ),
        ],
        [
            Paragraph("<b>Adjustable</b>", BODY),
            Paragraph(
                "Surface (dark vs. light variants), size (responsive scaling), tagline visibility (mark vs. full lockup).",
                BODY,
            ),
        ],
        [
            Paragraph("<b>Forbidden</b>", BODY),
            Paragraph(
                "Recoloring (no navy or gold logo), separating ring icon from wordmark in the same context, distorting proportions, removing the tagline link, animating in production, adding decorative effects (shadows, glows beyond the spec).",
                BODY,
            ),
        ],
    ]
    rules_table = Table(rules_data, colWidths=[1.2 * inch, 5.2 * inch])
    rules_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), PAPER_2),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(rules_table)

    return elements


def build_logo_section():
    elements = []
    elements.append(Paragraph("Logo", H1))
    elements.append(
        Paragraph(
            "The Special Wedding logo is a symbolic mark — two interlocking rings with a heart at "
            "their intersection — paired with a serif wordmark. The mark reads as <i>marriage, "
            "intimacy, premium</i>. Three variants ship: full lockup (with tagline), mark (icon + "
            "wordmark, no tagline), and icon-only.",
            BODY,
        )
    )

    # Three variants on dark surface
    elements.append(Paragraph("Three lockup variants", H2))

    elements.append(
        KeepTogether(
            [
                Paragraph(
                    "Full lockup — primary marketing surfaces, login pages, hero areas",
                    H3,
                ),
                draw_logo_lockup(
                    5.5 * inch, 1.2 * inch, surface="dark", show_tagline=True
                ),
                Spacer(1, 12),
            ]
        )
    )

    elements.append(
        KeepTogether(
            [
                Paragraph(
                    "Mark — sidebars, compact navigation, places without room for tagline",
                    H3,
                ),
                draw_logo_lockup(
                    4.5 * inch, 1.0 * inch, surface="dark", show_tagline=False
                ),
                Spacer(1, 12),
            ]
        )
    )

    elements.append(
        KeepTogether(
            [
                Paragraph(
                    "Light surface — admin login, microsite, cream backgrounds", H3
                ),
                draw_logo_lockup(
                    5.5 * inch, 1.2 * inch, surface="light", show_tagline=True
                ),
                Spacer(1, 12),
            ]
        )
    )

    # Sizing rules
    elements.append(Paragraph("Sizing rules", H2))

    sizing_data = [
        [
            Paragraph("<b>Context</b>", BODY_SMALL),
            Paragraph("<b>Variant</b>", BODY_SMALL),
            Paragraph("<b>Icon height</b>", BODY_SMALL),
            Paragraph("<b>Min clear space</b>", BODY_SMALL),
        ],
        [
            Paragraph("Browser favicon", BODY_SMALL),
            Paragraph("Simplified icon", BODY_SMALL),
            Paragraph("16–32px", BODY_SMALL),
            Paragraph("Edge-to-edge", BODY_SMALL),
        ],
        [
            Paragraph("Sidebar (collapsed)", BODY_SMALL),
            Paragraph("Icon", BODY_SMALL),
            Paragraph("36px", BODY_SMALL),
            Paragraph("8px on all sides", BODY_SMALL),
        ],
        [
            Paragraph("Sidebar (expanded)", BODY_SMALL),
            Paragraph("Mark", BODY_SMALL),
            Paragraph("36–40px", BODY_SMALL),
            Paragraph("12px on all sides", BODY_SMALL),
        ],
        [
            Paragraph("Marketing top nav", BODY_SMALL),
            Paragraph("Full lockup", BODY_SMALL),
            Paragraph("56px", BODY_SMALL),
            Paragraph("16px on all sides", BODY_SMALL),
        ],
        [
            Paragraph("Login page", BODY_SMALL),
            Paragraph("Full lockup", BODY_SMALL),
            Paragraph("56–80px", BODY_SMALL),
            Paragraph("24px above headline", BODY_SMALL),
        ],
        [
            Paragraph("Hero area / wedding microsite", BODY_SMALL),
            Paragraph("Icon (large)", BODY_SMALL),
            Paragraph("160–200px", BODY_SMALL),
            Paragraph("48px+ on all sides", BODY_SMALL),
        ],
        [
            Paragraph("PWA icon (Android)", BODY_SMALL),
            Paragraph("Icon-only PNG", BODY_SMALL),
            Paragraph("192×192, 512×512", BODY_SMALL),
            Paragraph("Fills frame", BODY_SMALL),
        ],
    ]
    sizing_table = Table(
        sizing_data, colWidths=[1.7 * inch, 1.2 * inch, 1.2 * inch, 2.3 * inch]
    )
    sizing_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, 0), ROSE_PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), ROSE_NEAR_BLACK),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER_2, HexColor("#FFFFFF")]),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(sizing_table)

    elements.append(Spacer(1, 14))

    # Don'ts
    elements.append(Paragraph("Don't", H2))
    donts = [
        "<b>Don't recolor the logo</b> — the rose family is the brand. Navy, gold, mono-black, and rainbow versions are not approved.",
        "<b>Don't substitute the wordmark</b> — &quot;The Special Wedding&quot; is the locked phrase. No abbreviations, no &quot;TSW&quot;, no all-caps wordmark in marketing.",
        "<b>Don't separate the rings from the heart</b> — the heart is part of the icon. Render together always.",
        "<b>Don't add effects</b> — no drop shadow beyond what's specified, no outer glow, no neon, no metallic foil overlay.",
        "<b>Don't distort proportions</b> — never stretch the wordmark vertically or compress horizontally to fit.",
        "<b>Don't drop the tagline link</b> — &quot;a Joatlabs.dev platform&quot; is always live and links to https://joatlabs.dev when tagline is shown.",
        "<b>Don't animate in production</b> — animation is for marketing motion graphics only, never as the resting state of the logo.",
    ]
    for d in donts:
        elements.append(Paragraph(f"• {d}", BODY_SMALL))

    return elements


def build_color_section():
    elements = []
    elements.append(Paragraph("Color palette", H1))
    elements.append(
        Paragraph(
            "The brand color is rose. The full palette is a rose ramp from highlight white through "
            "near-black rose. Use the ramp positionally — highlights for top-light edges, mid-tones "
            "for fills, deep tones for shadows and outlines. Navy and gold are part of the wedding "
            "theme palette but are <i>not</i> brand colors and never apply to the logo.",
            BODY,
        )
    )

    # Brand rose ramp
    elements.append(Paragraph("Brand rose ramp", H2))

    swatches = [
        ("Highlight", "#FFE5DC", ROSE_HIGHLIGHT, "light"),
        ("Primary rose", "#E8B4B8", ROSE_PRIMARY, "light"),
        ("Wedding rose", "#C8847E", ROSE_ACCENT, "light"),
        ("Mid rose", "#A87278", ROSE_MID, "dark"),
        ("Deep rose", "#7A4B50", ROSE_DEEP, "dark"),
        ("Burgundy", "#5C2F34", ROSE_BURGUNDY, "dark"),
        ("Outline", "#3D1418", ROSE_OUTLINE, "dark"),
        ("Near-black", "#1F0A0C", ROSE_NEAR_BLACK, "dark"),
    ]

    swatch_w = 0.9 * inch
    swatch_h = 0.9 * inch

    # Build a 4×2 grid of swatches
    rows = []
    cur_row = []
    for label, value, color, text_on in swatches:
        cur_row.append(
            draw_color_swatch(swatch_w, swatch_h, color, label, value, text_on=text_on)
        )
        if len(cur_row) == 4:
            rows.append(cur_row)
            cur_row = []
    if cur_row:
        rows.append(cur_row)

    swatch_table = Table(
        rows, colWidths=[swatch_w] * 4, rowHeights=[swatch_h] * len(rows)
    )
    swatch_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(swatch_table)

    # Wedding theme palette (separate from brand)
    elements.append(Spacer(1, 16))
    elements.append(Paragraph("Wedding theme palette (per-wedding microsite)", H2))
    elements.append(
        Paragraph(
            "Each wedding microsite is themed independently from these defaults. These are <b>not</b> "
            "platform brand colors — they apply only to per-couple microsite styling and never to "
            "the logo.",
            BODY_MUTED,
        )
    )

    theme_swatches = [
        ("Wedding navy (primary)", "#1e3a5f", NAVY, "dark"),
        ("Wedding gold (secondary)", "#d4af37", GOLD, "dark"),
        ("Wedding rose (accent)", "#c8847e", ROSE_ACCENT, "light"),
    ]
    theme_row = [
        draw_color_swatch(1.6 * inch, 0.9 * inch, c, label, v, text_on=t)
        for label, v, c, t in theme_swatches
    ]
    theme_table = Table(
        [theme_row], colWidths=[1.6 * inch] * 3, rowHeights=[0.9 * inch]
    )
    theme_table.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(theme_table)

    # Usage map
    elements.append(Spacer(1, 16))
    elements.append(Paragraph("Where each color goes", H2))

    usage_data = [
        [
            Paragraph("<b>Color</b>", BODY_SMALL),
            Paragraph("<b>Where it goes</b>", BODY_SMALL),
        ],
        [
            Paragraph("Highlight (#FFE5DC)", BODY_SMALL),
            Paragraph(
                "Top-light edges of metallic rings; logo highlight stops; cream backgrounds fade",
                BODY_SMALL,
            ),
        ],
        [
            Paragraph("Primary rose (#E8B4B8)", BODY_SMALL),
            Paragraph(
                "Logo wordmark on dark surfaces; primary CTA hover state; accent badges",
                BODY_SMALL,
            ),
        ],
        [
            Paragraph("Wedding rose (#C8847E)", BODY_SMALL),
            Paragraph("Heart fill; primary CTA background; key UI accents", BODY_SMALL),
        ],
        [
            Paragraph("Mid rose (#A87278)", BODY_SMALL),
            Paragraph("Logo wordmark on light surfaces; secondary accents", BODY_SMALL),
        ],
        [
            Paragraph("Deep rose (#7A4B50)", BODY_SMALL),
            Paragraph(
                "Mid-shadow zones on rings; section headings; emphasis text", BODY_SMALL
            ),
        ],
        [
            Paragraph("Burgundy (#5C2F34)", BODY_SMALL),
            Paragraph(
                "Logo wordmark headline on light surfaces; H1 display copy on cream",
                BODY_SMALL,
            ),
        ],
        [
            Paragraph("Outline (#3D1418)", BODY_SMALL),
            Paragraph(
                "Heart silhouette outline; deepest gradient stop on the dark logo",
                BODY_SMALL,
            ),
        ],
        [
            Paragraph("Near-black (#1F0A0C)", BODY_SMALL),
            Paragraph(
                "Heart deep-shadow center on light surfaces; rim shadow", BODY_SMALL
            ),
        ],
    ]
    usage_table = Table(usage_data, colWidths=[1.7 * inch, 4.7 * inch])
    usage_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, 0), ROSE_PRIMARY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER_2, HexColor("#FFFFFF")]),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elements.append(usage_table)

    return elements


def build_typography_section():
    elements = []
    elements.append(Paragraph("Typography", H1))
    elements.append(
        Paragraph(
            "Two typeface families. <b>Georgia</b> (or any solid serif: Times New Roman as fallback) "
            "for the brand wordmark and editorial headlines — it carries the wedding-industry "
            "premium signal. <b>Helvetica</b> / system-ui sans-serif for product UI, body copy, and "
            "the Joatlabs.dev tagline. Never mix more than these two families on a single surface.",
            BODY,
        )
    )

    elements.append(Paragraph("Display + headlines (Georgia serif)", H2))

    type_specimens = [
        ("Display 1 — 48pt bold", "Times-Bold", 36, "Wedding"),
        ("H1 — 28pt bold", "Times-Bold", 22, "Run every wedding from one record."),
        ("H2 — 18pt bold", "Times-Bold", 16, "The Couple Sees What You See"),
        ("Eyebrow — 11pt italic, 0.28em tracking", "Times-Italic", 11, "THE SPECIAL"),
    ]
    for label, font, size, sample in type_specimens:
        elements.append(Paragraph(label, EYEBROW_LABEL))
        elements.append(
            draw_typography_specimen(
                6.4 * inch, size + 6, sample, font, size, ROSE_BURGUNDY
            )
        )
        elements.append(Spacer(1, 8))

    elements.append(Paragraph("UI + body (Helvetica / system sans)", H2))

    sans_specimens = [
        ("UI Title — 16pt semibold", "Helvetica-Bold", 16, "Pipeline overview"),
        (
            "Body — 13pt regular, 1.5 leading",
            "Helvetica",
            13,
            "Most planners juggle six tools to run one wedding.",
        ),
        (
            "Small / metadata — 10pt",
            "Helvetica",
            10,
            "Updated 2 minutes ago — RSVPs, payments, and notes",
        ),
        (
            "Tagline — 9pt uppercase, 0.22em tracking",
            "Helvetica",
            9,
            "A JOATLABS.DEV PLATFORM",
        ),
    ]
    for label, font, size, sample in sans_specimens:
        elements.append(Paragraph(label, EYEBROW_LABEL))
        elements.append(
            draw_typography_specimen(6.4 * inch, size + 6, sample, font, size, INK)
        )
        elements.append(Spacer(1, 8))

    elements.append(Paragraph("Type rules", H2))
    type_rules = [
        "<b>Wordmark only uses Georgia.</b> Never Inter, never Poppins, never the system default.",
        "<b>Body copy is sans-serif everywhere except marketing editorial.</b> Headlines on the marketing site can use Georgia for premium feel; product UI does not.",
        "<b>Sentence case for headlines</b> — never Title Case, never ALL CAPS (except the eyebrow above the wordmark and the Joatlabs.dev tagline).",
        "<b>Two weights, ever:</b> 400 regular and 700 bold. Avoid 500 / 600 — they look weak against the bold serif headlines.",
        "<b>Line-height 1.5 for body</b>, 0.95 for the wordmark, 1.0 for tagline.",
        "<b>Letter-spacing:</b> 0.28em on the &quot;THE SPECIAL&quot; eyebrow, 0.06em on the &quot;Wedding&quot; headline, 0.22em on the tagline.",
    ]
    for rule in type_rules:
        elements.append(Paragraph(f"• {rule}", BODY_SMALL))

    return elements


def build_spacing_section():
    elements = []
    elements.append(Paragraph("Spacing &amp; layout", H1))
    elements.append(
        Paragraph(
            "The spacing system uses a 4px base unit. All paddings, margins, and component sizes "
            "should be multiples of 4. The grid is 12 columns at 1280px+ desktop, 4 columns on mobile.",
            BODY,
        )
    )

    spacing_data = [
        [
            Paragraph("<b>Token</b>", BODY_SMALL),
            Paragraph("<b>Value</b>", BODY_SMALL),
            Paragraph("<b>Use for</b>", BODY_SMALL),
        ],
        [
            Paragraph("xs", BODY_SMALL),
            Paragraph("4px", BODY_SMALL),
            Paragraph("Inline icon padding, badge padding", BODY_SMALL),
        ],
        [
            Paragraph("sm", BODY_SMALL),
            Paragraph("8px", BODY_SMALL),
            Paragraph("Stacked items in tight lists, small button padding", BODY_SMALL),
        ],
        [
            Paragraph("md", BODY_SMALL),
            Paragraph("12–16px", BODY_SMALL),
            Paragraph("Card padding, default form gap, button padding", BODY_SMALL),
        ],
        [
            Paragraph("lg", BODY_SMALL),
            Paragraph("24px", BODY_SMALL),
            Paragraph("Section margins, card-to-card gap", BODY_SMALL),
        ],
        [
            Paragraph("xl", BODY_SMALL),
            Paragraph("32–48px", BODY_SMALL),
            Paragraph("Major section breaks, hero padding", BODY_SMALL),
        ],
        [
            Paragraph("2xl", BODY_SMALL),
            Paragraph("64–96px", BODY_SMALL),
            Paragraph(
                "Page-level vertical rhythm, between marketing sections", BODY_SMALL
            ),
        ],
    ]
    spacing_table = Table(spacing_data, colWidths=[0.8 * inch, 1.0 * inch, 4.6 * inch])
    spacing_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, 0), ROSE_PRIMARY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER_2, HexColor("#FFFFFF")]),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elements.append(spacing_table)

    elements.append(Spacer(1, 14))
    elements.append(Paragraph("Border-radius", H2))

    radius_data = [
        [
            Paragraph("<b>Token</b>", BODY_SMALL),
            Paragraph("<b>Value</b>", BODY_SMALL),
            Paragraph("<b>Use for</b>", BODY_SMALL),
        ],
        [
            Paragraph("md", BODY_SMALL),
            Paragraph("8px", BODY_SMALL),
            Paragraph("Buttons, inputs, badges", BODY_SMALL),
        ],
        [
            Paragraph("lg", BODY_SMALL),
            Paragraph("12px", BODY_SMALL),
            Paragraph("Cards, modals, popovers", BODY_SMALL),
        ],
        [
            Paragraph("xl", BODY_SMALL),
            Paragraph("16–24px", BODY_SMALL),
            Paragraph("Hero glass cards, login cards", BODY_SMALL),
        ],
        [
            Paragraph("full", BODY_SMALL),
            Paragraph("9999px", BODY_SMALL),
            Paragraph("Pills, avatars, toggle thumbs", BODY_SMALL),
        ],
    ]
    radius_table = Table(radius_data, colWidths=[0.8 * inch, 1.0 * inch, 4.6 * inch])
    radius_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, 0), ROSE_PRIMARY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER_2, HexColor("#FFFFFF")]),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elements.append(radius_table)

    return elements


def build_components_section():
    elements = []
    elements.append(Paragraph("Component patterns", H1))
    elements.append(
        Paragraph(
            "Reference patterns for the most common UI elements. The full implementation lives in "
            "<font name='Courier'>app/components/ui</font>; these notes are for partners and writers "
            "who need to understand the visual language without reading the code.",
            BODY,
        )
    )

    elements.append(Paragraph("Buttons", H2))
    button_specs = [
        "<b>Primary</b> — Wedding-rose background (#C8847E), navy/black text, 8px radius, 12×16px padding. Used for Sign up, Save, Send. One per surface area.",
        "<b>Secondary</b> — Transparent or white/glass background, navy text or outlined border, 8px radius. Used for Cancel, Back, secondary actions.",
        "<b>Ghost / link</b> — No background, navy or rose text, underline on hover. Used inline within copy.",
    ]
    for s in button_specs:
        elements.append(Paragraph(f"• {s}", BODY_SMALL))

    elements.append(Paragraph("Cards", H2))
    card_specs = [
        "<b>Glass card</b> — White-with-30%-opacity background, 12px radius, soft inner glow + 2px white border at 40% opacity. Used on marketing site and login pages.",
        "<b>Solid card</b> — White (or slate-900 in dark mode) background, 12px radius, 0.5px border at #d8cfc3. Default for product UI surfaces.",
        "<b>Metric card</b> — Slate background (#f3eee6 or dark equivalent), 8px radius, no border. 13px label above 24px/500 number. Used in dashboard summary tiles.",
    ]
    for s in card_specs:
        elements.append(Paragraph(f"• {s}", BODY_SMALL))

    elements.append(Paragraph("Inputs", H2))
    input_specs = [
        "Height 36px (compact) or 44px (touch). Radius 8px. Border 1px #d8cfc3 default, focus rings to wedding-rose at 2px solid. Helper text 12px / muted-rose.",
        "Form labels 13px / Helvetica-Bold / navy. Error messages 12px / red-700, prefixed with an alert icon. Never use red as a brand color outside error states.",
    ]
    for s in input_specs:
        elements.append(Paragraph(f"• {s}", BODY_SMALL))

    elements.append(Paragraph("Badges &amp; pills", H2))
    badge_specs = [
        "12px Helvetica-Bold, uppercase, 0.05em letter-spacing. Padding 4×10px. Radius 9999px (full).",
        "Backgrounds use ramp 50 (lightest) with text in ramp 800 — see brand color palette. Never solid black or generic gray.",
    ]
    for s in badge_specs:
        elements.append(Paragraph(f"• {s}", BODY_SMALL))

    return elements


def build_voice_section():
    elements = []
    elements.append(Paragraph("Voice &amp; tone", H1))
    elements.append(
        Paragraph(
            "The Special Wedding writes for professional wedding planners — people running a business, "
            "not first-time brides. Voice is warm, confident, and operationally specific. Always lead "
            "with the planner moment, name the tools being replaced, and end with the human consequence.",
            BODY,
        )
    )

    elements.append(Paragraph("Voice constants (every surface)", H2))
    voice_we_are = [
        "<b>Confident</b>, not boastful. We've shipped this; we know how it works.",
        "<b>Operationally specific</b>, not vague. Real cron schedules, real retry windows, real planner moments.",
        "<b>Warm</b>, not corporate. Weddings are emotional work; the platform isn't sterile.",
        "<b>Honest about the alternative</b>. We name the competitors we replace (HoneyBook, Aisle Planner, DocuSign, Squarespace).",
        "<b>Anchored to the record</b>. &quot;One record, five surfaces&quot; is the brand thesis — every story ladders back to it.",
    ]
    for s in voice_we_are:
        elements.append(Paragraph(f"• {s}", BODY_SMALL))

    elements.append(Paragraph("We are not", H2))
    voice_we_are_not = [
        "<b>Salesy</b> — no &quot;revolutionary,&quot; &quot;game-changing,&quot; &quot;industry-leading.&quot;",
        "<b>Tech-bro</b> — no &quot;disrupt,&quot; &quot;leverage synergies,&quot; &quot;next-gen.&quot;",
        "<b>Generic</b> — no &quot;all-in-one&quot; without naming what's collapsed; no &quot;simplify your life&quot; without the specific pain.",
        "<b>Patronizing</b> — planners are running a business; don't write to them like couples planning their first wedding.",
    ]
    for s in voice_we_are_not:
        elements.append(Paragraph(f"• {s}", BODY_SMALL))

    elements.append(Paragraph("Tone flexes by content type", H2))
    tone_data = [
        [
            Paragraph("<b>Surface</b>", BODY_SMALL),
            Paragraph("<b>Formality</b>", BODY_SMALL),
            Paragraph("<b>Energy</b>", BODY_SMALL),
            Paragraph("<b>Detail</b>", BODY_SMALL),
        ],
        [
            Paragraph("Marketing homepage", BODY_SMALL),
            Paragraph("Mid", BODY_SMALL),
            Paragraph("High", BODY_SMALL),
            Paragraph("High — name tools, name moments", BODY_SMALL),
        ],
        [
            Paragraph("Sales call follow-up", BODY_SMALL),
            Paragraph("High", BODY_SMALL),
            Paragraph("Mid", BODY_SMALL),
            Paragraph("High — specific to their stack", BODY_SMALL),
        ],
        [
            Paragraph("Product UI / system messages", BODY_SMALL),
            Paragraph("Mid", BODY_SMALL),
            Paragraph("Low", BODY_SMALL),
            Paragraph("Low — terse, factual", BODY_SMALL),
        ],
        [
            Paragraph("Couple-facing copy (microsite)", BODY_SMALL),
            Paragraph("Low", BODY_SMALL),
            Paragraph("Mid", BODY_SMALL),
            Paragraph("Low — warm, human", BODY_SMALL),
        ],
        [
            Paragraph("Error / billing messages", BODY_SMALL),
            Paragraph("High", BODY_SMALL),
            Paragraph("Low", BODY_SMALL),
            Paragraph("Mid — what failed, what to do", BODY_SMALL),
        ],
    ]
    tone_table = Table(
        tone_data, colWidths=[2.0 * inch, 1.0 * inch, 1.0 * inch, 2.4 * inch]
    )
    tone_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, 0), ROSE_PRIMARY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER_2, HexColor("#FFFFFF")]),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elements.append(tone_table)

    return elements


def build_handoff_section():
    elements = []
    elements.append(Paragraph("Implementation handoff", H1))
    elements.append(
        Paragraph(
            "If you're an engineer or designer building new surfaces, here are the canonical "
            "references in the codebase.",
            BODY,
        )
    )

    handoff_data = [
        [
            Paragraph("<b>Concern</b>", BODY_SMALL),
            Paragraph("<b>Source of truth</b>", BODY_SMALL),
        ],
        [
            Paragraph("Logo lockup", BODY_SMALL),
            Paragraph(
                "<font name='Courier'>app/components/brand/BrandLockup.tsx</font>",
                BODY_SMALL,
            ),
        ],
        [
            Paragraph("Static SVG fallbacks", BODY_SMALL),
            Paragraph(
                "<font name='Courier'>public/logo.svg</font>, <font name='Courier'>public/logo-light.svg</font>, <font name='Courier'>public/logo-icon.svg</font>, <font name='Courier'>public/favicon.svg</font>",
                BODY_SMALL,
            ),
        ],
        [
            Paragraph("PNG regeneration", BODY_SMALL),
            Paragraph(
                "<font name='Courier'>public/BRAND_ASSETS.md</font> — rsvg-convert / ImageMagick commands",
                BODY_SMALL,
            ),
        ],
        [
            Paragraph("Marketing copy / feature stories", BODY_SMALL),
            Paragraph(
                "<font name='Courier'>app/data/marketingFeatures.ts</font> — single source of truth for the feature grid",
                BODY_SMALL,
            ),
        ],
        [
            Paragraph("Wedding theme palette", BODY_SMALL),
            Paragraph(
                "<font name='Courier'>app/models/wedding.py</font> — <font name='Courier'>ThemeConfigModel</font>",
                BODY_SMALL,
            ),
        ],
        [
            Paragraph("Tailwind tokens", BODY_SMALL),
            Paragraph(
                "<font name='Courier'>tailwind.config.js</font> — <font name='Courier'>wedding-rose</font>, <font name='Courier'>wedding-navy</font>, <font name='Courier'>wedding-gold</font>",
                BODY_SMALL,
            ),
        ],
    ]
    handoff_table = Table(handoff_data, colWidths=[2.0 * inch, 4.4 * inch])
    handoff_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, 0), ROSE_PRIMARY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER_2, HexColor("#FFFFFF")]),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elements.append(handoff_table)

    elements.append(Spacer(1, 18))
    elements.append(Paragraph("Brand contact", H2))
    elements.append(
        Paragraph(
            "Questions, change requests, or partnership clearances: contact Etastic at "
            "<font color='#7A4B50'>emmanuel.t.akinwale@gmail.com</font>. Joatlabs.dev is the parent "
            "platform; The Special Wedding is its operational SaaS for wedding planners.",
            BODY,
        )
    )

    return elements


# ── Document assembly ──────────────────────────────────────────────────────
def build_pdf():
    doc = BaseDocTemplate(
        OUTPUT_PATH,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=1.0 * inch,
        title="The Special Wedding — Brand & Design Guidelines",
        author="The Special Wedding · Joatlabs.dev",
        subject="Visual identity, typography, and component patterns",
    )

    cover_frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="cover",
    )
    body_frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="body",
    )

    doc.addPageTemplates(
        [
            PageTemplate(id="Cover", frames=[cover_frame], onPage=cover_decoration),
            PageTemplate(id="Body", frames=[body_frame], onPage=page_decoration),
        ]
    )

    story = []
    story.extend(build_cover())
    story.append(NextPageTemplate("Body"))
    story.append(PageBreak())
    story.extend(build_intro())
    story.append(PageBreak())
    story.extend(build_logo_section())
    story.append(PageBreak())
    story.extend(build_color_section())
    story.append(PageBreak())
    story.extend(build_typography_section())
    story.append(PageBreak())
    story.extend(build_spacing_section())
    story.append(PageBreak())
    story.extend(build_components_section())
    story.append(PageBreak())
    story.extend(build_voice_section())
    story.append(PageBreak())
    story.extend(build_handoff_section())

    doc.build(story)
    print(f"PDF written to {OUTPUT_PATH}")


if __name__ == "__main__":
    build_pdf()
