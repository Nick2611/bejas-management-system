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
