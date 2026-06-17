from pydantic import BaseModel


class PeriodKpiResponse(BaseModel):
    total_sales: int
    sales_count: int


class EmployeeClosingMetric(BaseModel):
    user_id: int
    username: str
    closed_tables: int
    total_sales: int


class KpiSummaryResponse(BaseModel):
    daily: PeriodKpiResponse
    weekly: PeriodKpiResponse
    monthly: PeriodKpiResponse
    employee_performance: list[EmployeeClosingMetric]


class DailyKpiPoint(BaseModel):
    date: str           # "YYYY-MM-DD"
    total_sales: int
    sales_count: int
    total_people: int


class DailySalesHistory(BaseModel):
    days: list[DailyKpiPoint]
    total_sales: int
    max_day: int
    avg_per_day: int
    active_days: int
