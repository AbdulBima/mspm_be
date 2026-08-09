"""
app.services.pdf.in_review_queue
=================================
Cross-team "in review" queue: every task currently sitting in review for a
sprint, sorted oldest-waiting-first by the caller so the most overdue
approvals surface at the top.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.pdf.layout import render_page_furniture, task_cell
from app.services.pdf.theme import (
    AMBER,
    AMBER_BG,
    BORDER,
    CONTENT_W,
    DANGER,
    DANGER_BG,
    FAINT,
    HAIRLINE,
    INK,
    MARGIN_BOTTOM,
    MARGIN_TOP,
    MARGIN_X,
    MUTED,
    PAGE_H,
    PAGE_W,
    PAPER,
    SLATE,
    WHITE,
    build_styles,
)


def _queue_header(sprint: dict, count: int, generated_by: str | None) -> list:
    eyebrow = Paragraph(
        "IN REVIEW QUEUE",
        ParagraphStyle(
            "queue_eyebrow", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=AMBER, spaceAfter=6
        ),
    )
    title = Paragraph(
        f"{count} task{'s' if count != 1 else ''} awaiting review",
        ParagraphStyle(
            "queue_h1", fontName="Helvetica-Bold", fontSize=21, leading=24, textColor=INK, spaceAfter=3
        ),
    )
    sub_text = sprint.get("name", "")
    if generated_by:
        sub_text += f" &nbsp;&middot;&nbsp; pulled by {generated_by}"
    subtitle = Paragraph(
        sub_text,
        ParagraphStyle("queue_subtitle", fontName="Helvetica", fontSize=10.5, leading=14, textColor=MUTED),
    )
    return [eyebrow, title, subtitle]


def _waiting_cell(days: int | None) -> Paragraph:
    if days is None:
        return Paragraph(
            "--",
            ParagraphStyle(
                "wait_none",
                fontName="Helvetica",
                fontSize=8.8,
                leading=11.5,
                textColor=FAINT,
                alignment=TA_CENTER,
            ),
        )
    if days <= 1:
        fg, label = SLATE, ("Today" if days == 0 else "1 day")
    elif days <= 3:
        fg, label = AMBER, f"{days} days"
    else:
        fg, label = DANGER, f"{days} days"
    return Paragraph(
        label,
        ParagraphStyle(
            f"wait_{days}",
            fontName="Helvetica-Bold",
            fontSize=8.8,
            leading=11.5,
            textColor=fg,
            alignment=TA_CENTER,
        ),
    )


def _in_review_table(tasks: list, styles: dict[str, ParagraphStyle]) -> Table:
    col_widths = [0.38 * inch, 2.35 * inch, 1.05 * inch, 1.35 * inch, 1.05 * inch, 1.02 * inch]

    header = [
        Paragraph("#", styles["th_center"]),
        Paragraph("TASK", styles["th"]),
        Paragraph("MEMBER", styles["th"]),
        Paragraph("GOAL", styles["th"]),
        Paragraph("WAITING", styles["th_center"]),
        Paragraph("DUE", styles["th_center"]),
    ]
    rows = [header]
    row_styles = []

    for i, t in enumerate(tasks, start=1):
        goal_title = t.get("goal_title")
        goal_cell = (
            Paragraph(goal_title, styles["cell"])
            if goal_title
            else Paragraph("Unlinked", ParagraphStyle("unlinked", parent=styles["cell"], textColor=FAINT))
        )

        member_color = colors.HexColor(t["member_color"]) if t.get("member_color") else INK
        member_cell = Paragraph(
            t.get("member_name", "Unassigned"),
            ParagraphStyle(
                f"member_{i}", fontName="Helvetica-Bold", fontSize=8.8, leading=11.5, textColor=member_color
            ),
        )

        due = t.get("due_date")
        if due:
            due_date = due.date() if isinstance(due, datetime) else due
            due_str = due_date.strftime("%b %d")
            due_cell = Paragraph(due_str, styles["due_overdue"] if t.get("is_overdue") else styles["due"])
        else:
            due_cell = Paragraph("--", styles["due"])

        rows.append(
            [
                Paragraph(f"P{t.get('priority', '-')}", styles["priority"]),
                task_cell(t, styles),
                member_cell,
                goal_cell,
                _waiting_cell(t.get("waiting_days")),
                due_cell,
            ]
        )
        row_idx = i
        waiting_days = t.get("waiting_days")
        if t.get("is_overdue"):
            row_styles.append(("BACKGROUND", (0, row_idx), (-1, row_idx), DANGER_BG))
        elif waiting_days is not None and waiting_days > 3:
            row_styles.append(("BACKGROUND", (0, row_idx), (-1, row_idx), AMBER_BG))
        elif i % 2 == 0:
            row_styles.append(("BACKGROUND", (0, row_idx), (-1, row_idx), PAPER))

    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (4, 0), (4, -1), "CENTER"),
                ("ALIGN", (5, 0), (5, -1), "CENTER"),
                ("LINEBELOW", (0, 0), (-1, 0), 1, AMBER),
                ("LINEBELOW", (0, 1), (-1, -1), 0.5, HAIRLINE),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 4),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                *row_styles,
            ]
        )
    )
    return table


def _queue_closing_note(styles: dict[str, ParagraphStyle]) -> Table:
    body = (
        "This is a snapshot of everything sitting in review across the team right now, oldest first. "
        "Approve or bounce each one back into progress in Sprint Ops -- this list won't update itself."
    )
    lead = Paragraph("WORKING QUEUE", styles["section_label"])
    text = Paragraph(body, styles["closing_body"])
    t = Table([[lead], [Spacer(1, 4)], [text]], colWidths=[CONTENT_W - 28])
    t.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0, WHITE),
                ("LINEBEFORE", (0, 0), (0, -1), 2.5, AMBER),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, 0), 4),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 4),
            ]
        )
    )
    return t


def build_in_review_queue_pdf(*, sprint: dict, tasks: list, generated_by: str | None = None) -> bytes:
    """
    Renders the cross-team "in review" queue, sorted oldest-waiting-first by
    the caller.

    `tasks` are expected to already carry `is_overdue`, `waiting_days`
    (whole days since the task last entered "in_review", via
    app.services.task_flags.in_review_since), `member_name` / `member_color`,
    and an optional `goal_title`.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=(PAGE_W, PAGE_H),
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        title=f"{sprint.get('name', 'Sprint')} - In Review Queue",
        author="Sprint Ops",
    )
    styles = build_styles()
    story = [*_queue_header(sprint, len(tasks), generated_by), Spacer(1, 18)]

    if tasks:
        story.append(_in_review_table(tasks, styles))
    else:
        story.append(HRFlowable(width="100%", thickness=0.75, color=BORDER))
        story.append(Spacer(1, 14))
        story.append(Paragraph("Nothing in review right now.", styles["empty"]))

    story.append(Spacer(1, 22))
    story.append(HRFlowable(width="100%", thickness=0.75, color=BORDER))
    story.append(Spacer(1, 14))
    story.append(_queue_closing_note(styles))

    def _furniture(canvas, doc_):
        render_page_furniture(canvas, doc_, sprint.get("name", ""))

    doc.build(story, onFirstPage=_furniture, onLaterPages=_furniture)
    return buf.getvalue()
