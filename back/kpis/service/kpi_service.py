from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from kpis.models.kpi_models import (
    EmployeeClosingMetric,
    KpiSummaryResponse,
    PeriodKpiResponse,
)
from kpis.repository.kpi_repository import KpiRepository
from shared.time_utils import local_today, period_dates


class KpiService:
    def __init__(self, session: Session):
        self.repository = KpiRepository(session)

    def _period(self, period: str) -> PeriodKpiResponse:
        start_date, end_date = period_dates(period, local_today())
        start = datetime.combine(start_date, time.min)
        end = datetime.combine(end_date + timedelta(days=1), time.min)
        total, count = self.repository.period_summary(start, end)
        return PeriodKpiResponse(total_sales=total, sales_count=count)

    def summary(self) -> KpiSummaryResponse:
        month_start_date, month_end_date = period_dates(
            "mensual",
            local_today(),
        )
        month_start = datetime.combine(month_start_date, time.min)
        month_end = datetime.combine(
            month_end_date + timedelta(days=1),
            time.min,
        )
        return KpiSummaryResponse(
            daily=self._period("diario"),
            weekly=self._period("semanal"),
            monthly=self._period("mensual"),
            employee_performance=[
                EmployeeClosingMetric(
                    user_id=user_id,
                    username=username,
                    closed_tables=closed_tables,
                    total_sales=total_sales,
                )
                for user_id, username, closed_tables, total_sales
                in self.repository.employee_performance(
                    month_start,
                    month_end,
                )
            ],
        )
