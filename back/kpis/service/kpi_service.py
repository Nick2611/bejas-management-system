from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from kpis.models.kpi_models import (
    DailyKpiPoint,
    DailySalesHistory,
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

    def daily_history(self, days: int = 60) -> DailySalesHistory:
        rows = self.repository.daily_history(days)
        points = [
            DailyKpiPoint(
                date=str(row.date),
                total_sales=int(row.total_sales),
                sales_count=int(row.sales_count),
                total_people=int(row.total_people),
            )
            for row in rows
        ]
        total = sum(p.total_sales for p in points)
        max_day = max((p.total_sales for p in points), default=0)
        active = len(points)
        avg = total // active if active else 0
        return DailySalesHistory(
            days=points,
            total_sales=total,
            max_day=max_day,
            avg_per_day=avg,
            active_days=active,
        )

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
