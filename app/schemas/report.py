"""Top-level therapy-data report.

Returned by `GET /v2/profiles/{id}/therapy-data` and used as the input
of the PDF rendering pipeline. The same DTO drives mobile UI and PDF.
"""

from datetime import datetime
from uuid import UUID

from app.schemas.adherence import (
    AdherenceReport,
    BucketKind,
    DoseNoteEntry,
    ParameterSeries,
    PeriodSpec,
)
from app.schemas.base import PharmaBaseModel


class TherapyDataReport(PharmaBaseModel):
    profile_id: UUID
    period: PeriodSpec
    bucket: BucketKind
    generated_at: datetime
    adherence: AdherenceReport | None = None
    parameters: list[ParameterSeries] | None = None
    notes: list[DoseNoteEntry] | None = None
