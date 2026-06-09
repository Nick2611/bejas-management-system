from pydantic import BaseModel, Field, model_validator
from http import HTTPStatus
from typing import Literal

class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: Literal["admin", "empleado"]

class GetUserResponse(BaseModel):
    id: int
    username: str
    role: str

class CreateUserResponse(BaseModel):
    id: int
    user: str
    role: str
    status: HTTPStatus

class LoginRequest(BaseModel):
    username: str
    password: str


class UpdateUserRequest(BaseModel):
    username: str | None = Field(default=None, min_length=1)
    password: str | None = Field(default=None, min_length=1)
    role: Literal["admin", "empleado"] | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set or not any(
            value is not None
            for value in (self.username, self.password, self.role)
        ):
            raise ValueError("Debe indicar al menos un campo para actualizar")
        return self
