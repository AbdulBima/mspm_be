"""
app.services.pdf.layout
========================
Reportlab flowable helpers shared by more than one PDF builder. Anything
specific to a single document (headers, callouts, closing notes) stays in
that document's own module; only what's genuinely reused lives here.
"""

from __future__ import annotations

from datetime import datetime

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph

from app.services.pdf.theme import BORDER, FAINT, INK, MARGIN_BOTTOM, MARGIN_X, MUTED, NAVY, PAGE_H, PAGE_W


def task_cell(task: dict, styles: dict[str, ParagraphStyle]) -> list:
    """Task title + optional truncated description + overdue/stale flags, as
    a list of flowables for a single table cell. Shared by the member
    open-tasks table and the in-review queue table."""
    parts = [Paragraph(task.get("title", "Untitled task"), styles["task_title"])]
    desc = (task.get("description") or "").strip()
    if desc:
        if len(desc) > 150:
            desc = desc[:150].rsplit(" ", 1)[0] + "..."
        parts.append(Paragraph(desc, styles["task_meta"]))
    if task.get("is_overdue"):
        parts.append(Paragraph("OVERDUE", styles["task_flag_danger"]))
    if task.get("is_stale"):
        parts.append(Paragraph("GONE QUIET", styles["task_flag_amber"]))
    return parts


def render_page_furniture(canvas, doc, sprint_name: str) -> None:
    """Top accent bar + running header (page 2+) + footer (every page).
    Registered as the SimpleDocTemplate onFirstPage/onLaterPages callback by
    each builder."""
    canvas.saveState()

    canvas.setFillColor(INK)
    canvas.rect(0, PAGE_H - 0.1 * inch, PAGE_W, 0.1 * inch, stroke=0, fill=1)

    if canvas.getPageNumber() > 1:
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.setFillColor(NAVY)
        canvas.drawString(MARGIN_X, PAGE_H - 0.55 * inch, "SPRINT OPS")
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 0.55 * inch, sprint_name)
        canvas.setStrokeColor(BORDER)
        canvas.line(MARGIN_X, PAGE_H - 0.62 * inch, PAGE_W - MARGIN_X, PAGE_H - 0.62 * inch)

    canvas.setStrokeColor(BORDER)
    canvas.line(MARGIN_X, MARGIN_BOTTOM - 0.15 * inch, PAGE_W - MARGIN_X, MARGIN_BOTTOM - 0.15 * inch)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(FAINT)
    canvas.drawString(
        MARGIN_X,
        MARGIN_BOTTOM - 0.3 * inch,
        f"Generated {datetime.now().strftime('%b %d, %Y %I:%M %p')} \u00b7 Sprint Ops \u00b7 Internal use only",
    )
    canvas.drawRightString(PAGE_W - MARGIN_X, MARGIN_BOTTOM - 0.3 * inch, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()
