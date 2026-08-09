"""
app.services.pdf.member_tasks
==============================
The member-facing "open tasks" handout: everything Sprint Ops has on record
as not-yet-done for one person in one sprint, meant to be handed directly to
them.
"""

from __future__ import annotations

from datetime import date, datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
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
    NAVY,
    NAVY_BG,
    PAGE_H,
    PAGE_W,
    PAPER,
    STATUS_META,
    WHITE,
    build_styles,
)


def _avatar_badge(member: dict) -> Table:
    color = colors.HexColor(member["color_tag"]) if member.get("color_tag") else NAVY
    initial = (member.get("name") or "?").strip()[:1].upper()
    style = ParagraphStyle(
        "avatar", fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=INK, alignment=TA_CENTER
    )
    size = 0.4 * inch
    radius = size / 2
    t = Table([[Paragraph(initial, style)]], colWidths=[size], rowHeights=[size], cornerRadii=[radius] * 4)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), color),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    return t


def _header_block(member: dict, sprint: dict, styles: dict[str, ParagraphStyle]) -> Table:
    text_cell = [
        Paragraph("OPEN TASKS", styles["eyebrow"]),
        Paragraph(member.get("name", "Team member"), styles["h1"]),
        Paragraph(
            f"{member.get('role_title', '')} &nbsp;&middot;&nbsp; {sprint.get('name', '')}",
            styles["subtitle"],
        ),
    ]
    badge = _avatar_badge(member)
    t = Table([[badge, text_cell]], colWidths=[0.55 * inch, CONTENT_W - 0.55 * inch])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (0, 0), 2),
                ("LEFTPADDING", (1, 0), (1, 0), 10),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
            ]
        )
    )
    return t


def _deadline_callout(sprint_end_date: date, day_number: int, working_days: int) -> Table:
    today = date.today()
    days_left = (sprint_end_date - today).days

    if days_left < 0:
        n = abs(days_left)
        headline = f"Sprint ended {n} day{'s' if n != 1 else ''} ago"
        fg, bg = DANGER, DANGER_BG
    elif days_left == 0:
        headline = "Sprint ends today"
        fg, bg = DANGER, DANGER_BG
    elif days_left <= 2:
        headline = f"{days_left} day{'s' if days_left != 1 else ''} left in the sprint"
        fg, bg = DANGER, DANGER_BG
    elif days_left <= 4:
        headline = f"{days_left} days left in the sprint"
        fg, bg = AMBER, AMBER_BG
    else:
        headline = f"{days_left} days left in the sprint"
        fg, bg = NAVY, NAVY_BG

    end_str = sprint_end_date.strftime("%b %d, %Y")
    sub = f"Ends {end_str} &nbsp;&middot;&nbsp; Day {day_number} of {working_days}"

    left = Paragraph(
        headline,
        ParagraphStyle("callout_head", fontName="Helvetica-Bold", fontSize=12.5, leading=15, textColor=fg),
    )
    right = Paragraph(
        sub,
        ParagraphStyle(
            "callout_sub", fontName="Helvetica", fontSize=9, leading=12, textColor=fg, alignment=TA_RIGHT
        ),
    )
    t = Table([[left, right]], colWidths=[CONTENT_W * 0.58, CONTENT_W * 0.42], cornerRadii=[10] * 4)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (0, 0), 14),
                ("RIGHTPADDING", (1, 0), (1, 0), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 11),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
            ]
        )
    )
    return t


def _stat_box(value: int, label: str, color, width: float, styles: dict[str, ParagraphStyle]) -> Table:
    value_style = ParagraphStyle("v", fontName="Helvetica-Bold", fontSize=18, leading=21, textColor=color)
    t = Table(
        [[Paragraph(str(value), value_style)], [Paragraph(label, styles["stat_label"])]],
        colWidths=[width],
        cornerRadii=[8] * 4,
    )
    t.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
                ("TOPPADDING", (0, 1), (-1, 1), 2),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 9),
            ]
        )
    )
    return t


def _stat_row(tasks: list, styles: dict[str, ParagraphStyle]) -> Table:
    total = len(tasks)
    blocked = sum(1 for t in tasks if t.get("status") == "blocked")
    overdue = sum(1 for t in tasks if t.get("is_overdue"))
    stale = sum(1 for t in tasks if t.get("is_stale"))

    gap = 8
    cell_w = (CONTENT_W - gap * 3) / 4
    boxes = [
        _stat_box(total, "OPEN TASKS", INK, cell_w, styles),
        _stat_box(blocked, "BLOCKED", DANGER if blocked else INK, cell_w, styles),
        _stat_box(overdue, "OVERDUE", DANGER if overdue else INK, cell_w, styles),
        _stat_box(stale, "GONE QUIET", AMBER if stale else INK, cell_w, styles),
    ]
    row, widths = [], []
    for i, b in enumerate(boxes):
        row.append(b)
        widths.append(cell_w)
        if i != len(boxes) - 1:
            row.append("")
            widths.append(gap)

    t = Table([row], colWidths=widths)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def _status_pill(status: str) -> Table:
    meta = STATUS_META.get(status, STATUS_META["not_started"])
    style = ParagraphStyle(
        f"status_{status}",
        fontName="Helvetica-Bold",
        fontSize=7.2,
        leading=9,
        textColor=meta["fg"],
        alignment=TA_CENTER,
    )
    t = Table([[Paragraph(meta["label"], style)]], colWidths=[1.0 * inch], cornerRadii=[8] * 4)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), meta["bg"]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    return t


def _tasks_table(tasks: list, styles: dict[str, ParagraphStyle]) -> Table:
    col_widths = [0.42 * inch, 2.72 * inch, 1.52 * inch, 1.12 * inch, 0.9 * inch]

    header = [
        Paragraph("#", styles["th_center"]),
        Paragraph("TASK", styles["th"]),
        Paragraph("GOAL", styles["th"]),
        Paragraph("STATUS", styles["th_center"]),
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
                goal_cell,
                _status_pill(t.get("status", "not_started")),
                due_cell,
            ]
        )
        row_idx = i
        if t.get("is_overdue"):
            row_styles.append(("BACKGROUND", (0, row_idx), (-1, row_idx), DANGER_BG))
        elif i % 2 == 0:
            row_styles.append(("BACKGROUND", (0, row_idx), (-1, row_idx), PAPER))

    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (3, 0), (3, -1), "CENTER"),
                ("ALIGN", (4, 0), (4, -1), "CENTER"),
                ("LINEBELOW", (0, 0), (-1, 0), 1, NAVY),
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


def _closing_note(
    member: dict, manager_name: str | None, manager_email: str | None, styles: dict[str, ParagraphStyle]
) -> Table:
    who = manager_name or "your PM"
    contact = f" at {manager_email}" if manager_email else ""
    body = (
        f"This list reflects what Sprint Ops has on record as still open for "
        f"{member.get('name', 'you')} right now. If any of the tasks above are actually "
        f"finished, please let {who}{contact} know (or flag it however you two usually do) "
        f"so the board can be updated -- this snapshot won't update itself."
    )
    lead = Paragraph("A QUICK ASK", styles["section_label"])
    text = Paragraph(body, styles["closing_body"])
    t = Table([[lead], [Spacer(1, 4)], [text]], colWidths=[CONTENT_W - 28])
    t.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0, WHITE),
                ("LINEBEFORE", (0, 0), (0, -1), 2.5, NAVY),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, 0), 4),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 4),
            ]
        )
    )
    return t


def build_member_open_tasks_pdf(
    *,
    member: dict,
    sprint: dict,
    tasks: list,
    day_number: int,
    working_days: int,
    sprint_end_date: date,
    manager_name: str | None = None,
    manager_email: str | None = None,
) -> bytes:
    """
    Renders the "open tasks" handout for a single team member: everything
    Sprint Ops has on record as not-yet-done for them in the given sprint,
    plus how much runway is left before the sprint ends.

    `tasks` are expected to already carry `is_overdue` / `is_stale` (via
    app.services.task_flags) and an optional `goal_title` (resolved goal
    name, since tasks only store goal_id).
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=(PAGE_W, PAGE_H),
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        title=f"{member.get('name', 'Team member')} - Open Tasks",
        author="Sprint Ops",
    )
    styles = build_styles()
    story = [
        _header_block(member, sprint, styles),
        Spacer(1, 16),
        _deadline_callout(sprint_end_date, day_number, working_days),
        Spacer(1, 14),
        _stat_row(tasks, styles),
        Spacer(1, 20),
    ]

    if tasks:
        story.append(Paragraph(f"OPEN ITEMS ({len(tasks)})", styles["section_label"]))
        story.append(Spacer(1, 8))
        story.append(_tasks_table(tasks, styles))
    else:
        story.append(HRFlowable(width="100%", thickness=0.75, color=BORDER))
        story.append(Spacer(1, 14))
        story.append(Paragraph("Nothing open -- every task is marked done. Nice.", styles["empty"]))

    story.append(Spacer(1, 22))
    story.append(HRFlowable(width="100%", thickness=0.75, color=BORDER))
    story.append(Spacer(1, 14))
    story.append(_closing_note(member, manager_name, manager_email, styles))

    def _furniture(canvas, doc_):
        render_page_furniture(canvas, doc_, sprint.get("name", ""))

    doc.build(story, onFirstPage=_furniture, onLaterPages=_furniture)
    return buf.getvalue()
