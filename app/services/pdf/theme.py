"""
app.services.pdf.theme
=======================
Shared color palette, status styling, page geometry, and paragraph styles
for every PDF export. Kept separate from the builders themselves
(member_tasks.py, in_review_queue.py) so a palette or typography tweak
touches one file instead of two near-duplicates.

Built with reportlab: pure Python, no system font/rendering dependencies
(unlike weasyprint/wkhtmltopdf), so it runs anywhere the FastAPI service is
deployed without extra system packages.
"""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch

# ── palette -- mirrors the web app's tokens (member detail page etc.) ──────
INK = colors.HexColor("#0B0C0F")
NAVY = colors.HexColor("#1D2B64")
SLATE = colors.HexColor("#54525C")
MUTED = colors.HexColor("#84828C")
FAINT = colors.HexColor("#B4B2AC")
BORDER = colors.HexColor("#E7E5E2")
HAIRLINE = colors.HexColor("#EEEDEB")
PAPER = colors.HexColor("#FAFAF9")
WHITE = colors.white
NAVY_BG = colors.HexColor("#EAEDF7")

DANGER, DANGER_BG = colors.HexColor("#B42318"), colors.HexColor("#FEE2E2")
AMBER, AMBER_BG = colors.HexColor("#92590A"), colors.HexColor("#FEF3C7")
GOOD, GOOD_BG = colors.HexColor("#15803D"), colors.HexColor("#DCFCE7")
BLUE, BLUE_BG = colors.HexColor("#1D4ED8"), colors.HexColor("#DBEAFE")
SLATE_BG = colors.HexColor("#E2E8F0")

STATUS_META = {
    "not_started": {"label": "NOT STARTED", "fg": SLATE, "bg": SLATE_BG},
    "in_progress": {"label": "IN PROGRESS", "fg": BLUE, "bg": BLUE_BG},
    "blocked": {"label": "BLOCKED", "fg": DANGER, "bg": DANGER_BG},
    "in_review": {"label": "IN REVIEW", "fg": AMBER, "bg": AMBER_BG},
}

PAGE_W, PAGE_H = LETTER
MARGIN_X = 0.65 * inch
MARGIN_TOP = 0.95 * inch
MARGIN_BOTTOM = 0.75 * inch
CONTENT_W = PAGE_W - 2 * MARGIN_X


def build_styles() -> dict[str, ParagraphStyle]:
    """
    A fresh ParagraphStyle set per PDF, threaded through every helper that
    needs one. The original version of this module had each builder call
    the equivalent of this function once at the top of a build_* function
    but then had `_stat_box` silently rebuild the *entire* style dict again,
    from scratch, on every one of the four stat boxes per PDF — this version
    builds it once per document and passes it down.
    """
    return {
        "eyebrow": ParagraphStyle(
            "eyebrow", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=NAVY, spaceAfter=6
        ),
        "h1": ParagraphStyle(
            "h1", fontName="Helvetica-Bold", fontSize=21, leading=24, textColor=INK, spaceAfter=3
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontName="Helvetica", fontSize=10.5, leading=14, textColor=MUTED
        ),
        "section_label": ParagraphStyle(
            "section_label", fontName="Helvetica-Bold", fontSize=8.3, leading=11, textColor=MUTED
        ),
        "stat_label": ParagraphStyle(
            "stat_label", fontName="Helvetica", fontSize=7.4, leading=10, textColor=MUTED
        ),
        "task_title": ParagraphStyle(
            "task_title", fontName="Helvetica-Bold", fontSize=9.6, leading=12.5, textColor=INK
        ),
        "task_meta": ParagraphStyle(
            "task_meta", fontName="Helvetica", fontSize=8, leading=11, textColor=MUTED, spaceBefore=2
        ),
        "task_flag_danger": ParagraphStyle(
            "task_flag_danger",
            fontName="Helvetica-Bold",
            fontSize=7.4,
            leading=10,
            textColor=DANGER,
            spaceBefore=2,
        ),
        "task_flag_amber": ParagraphStyle(
            "task_flag_amber",
            fontName="Helvetica-Bold",
            fontSize=7.4,
            leading=10,
            textColor=AMBER,
            spaceBefore=2,
        ),
        "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.8, leading=11.5, textColor=SLATE),
        "priority": ParagraphStyle(
            "priority",
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            textColor=NAVY,
            alignment=TA_CENTER,
        ),
        "due": ParagraphStyle(
            "due", fontName="Helvetica", fontSize=8.8, leading=11.5, textColor=SLATE, alignment=TA_CENTER
        ),
        "due_overdue": ParagraphStyle(
            "due_overdue",
            fontName="Helvetica-Bold",
            fontSize=8.8,
            leading=11.5,
            textColor=DANGER,
            alignment=TA_CENTER,
        ),
        "th": ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=7.2, leading=9, textColor=MUTED),
        "th_center": ParagraphStyle(
            "th_center",
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=9,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
        "closing_lead": ParagraphStyle(
            "closing_lead", fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=INK, spaceAfter=4
        ),
        "closing_body": ParagraphStyle(
            "closing_body", fontName="Helvetica", fontSize=9.2, leading=13.5, textColor=SLATE
        ),
        "empty": ParagraphStyle("empty", fontName="Helvetica", fontSize=10, leading=14, textColor=MUTED),
    }
