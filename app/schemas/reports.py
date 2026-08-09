"""app.schemas.reports — report-generation request contract."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.schemas.enums import ReportType


class ReportGenerateRequest(BaseModel):
    sprint_id: str
    report_type: ReportType
    period_start: date | None = None  # required for daily/weekly; ignored for sprint
    period_end: date | None = None
    include_ai_narrative: bool = True
    notes: str | None = None  # PM's own added notes, folded into the report
