from typing import Annotated

from fastapi import APIRouter, Depends

from auth.auth import is_admin
from db.db_conn import SessionDep
from kpis.models.kpi_models import KpiSummaryResponse
from kpis.service.kpi_service import KpiService


kpi_router = APIRouter(prefix="/kpis", tags=["kpis"])
AdminClaims = Annotated[dict, Depends(is_admin)]


@kpi_router.get("/summary", response_model=KpiSummaryResponse)
def get_kpi_summary(session: SessionDep, claims: AdminClaims):
    return KpiService(session).summary()
