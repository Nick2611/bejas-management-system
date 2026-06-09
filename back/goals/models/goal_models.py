from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


GoalPeriod = Literal["diario", "semanal", "mensual"]


class CreateGoalRequest(BaseModel):
    period: GoalPeriod
    target_amount: int = Field(gt=0)
    description: str | None = None
    reference_date: date | None = None


class UpdateGoalRequest(BaseModel):
    period: GoalPeriod | None = None
    target_amount: int | None = Field(default=None, gt=0)
    description: str | None = None
    reference_date: date | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("Debe indicar al menos un campo")
        return self


class GoalResponse(BaseModel):
    id: int
    period: str
    target_amount: int
    description: str | None
    start_date: date
    end_date: date
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    current_sales: int
    progress: float
