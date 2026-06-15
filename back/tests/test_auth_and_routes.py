from datetime import datetime, timedelta, timezone
from http import HTTPStatus

import jwt
import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from unittest.mock import MagicMock

from auth.auth import ALGORITHM, SECRET_KEY, is_admin, validate_token
from db.db_models import UserModel
from main import app


def test_validate_token_accepts_valid_claims():
    token = jwt.encode(
        {
            "sub": "admin",
            "user_id": 1,
            "role": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    session = MagicMock()
    session.get.return_value = UserModel(
        id=1,
        username="admin",
        password="hash",
        role="admin",
        deleted_at=None,
    )
    claims = validate_token(token, session)

    assert claims["sub"] == "admin"
    assert claims["role"] == "admin"


def test_validate_token_rejects_invalid_token():
    with pytest.raises(HTTPException) as error:
        validate_token("not-a-jwt", MagicMock())

    assert error.value.status_code == HTTPStatus.UNAUTHORIZED


def test_validate_token_refreshes_role_from_database():
    token = jwt.encode(
        {
            "sub": "empleado",
            "user_id": 2,
            "role": "empleado",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    session = MagicMock()
    session.get.return_value = UserModel(
        id=2,
        username="nuevo-admin",
        password="hash",
        role="admin",
        deleted_at=None,
    )

    claims = validate_token(token, session)

    assert claims["username"] == "nuevo-admin"
    assert claims["role"] == "admin"


def test_is_admin_rejects_employee_and_accepts_admin():
    assert is_admin({"role": "admin", "user_id": 1})["user_id"] == 1

    with pytest.raises(HTTPException) as error:
        is_admin({"role": "empleado", "user_id": 2})

    assert error.value.status_code == HTTPStatus.FORBIDDEN


def _route(path: str, method: str) -> APIRoute:
    return next(
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path == path
        and method in route.methods
    )


@pytest.mark.parametrize(
    ("path", "method", "dependency"),
    [
        ("/auth/register", "POST", is_admin),
        ("/products/create", "POST", is_admin),
        ("/closings", "GET", is_admin),
        ("/closings/summary", "GET", is_admin),
        ("/closings/validate", "POST", is_admin),
        ("/closings/declare", "POST", is_admin),
        (
            "/closings/declarations/{closure_id}",
            "GET",
            is_admin,
        ),
        ("/cash-closings", "POST", is_admin),
        ("/cash-closings/{cash_closing_id}", "PATCH", is_admin),
        (
            "/cash-closings/{cash_closing_id}/revisions",
            "GET",
            is_admin,
        ),
        ("/invoices", "GET", is_admin),
        ("/invoices/pending-summary", "GET", is_admin),
        ("/invoices/retry-period", "POST", is_admin),
        ("/goals", "GET", is_admin),
        ("/kpis/summary", "GET", is_admin),
        ("/users", "GET", is_admin),
        ("/users/{user_id}", "PATCH", is_admin),
        ("/users/{user_id}", "DELETE", is_admin),
    ],
)
def test_admin_routes_use_is_admin(path, method, dependency):
    calls = {
        item.call
        for item in _route(path, method).dependant.dependencies
    }

    assert dependency in calls


def test_login_is_public():
    calls = {
        item.call
        for item in _route("/auth", "POST").dependant.dependencies
    }

    assert validate_token not in calls
    assert is_admin not in calls


def test_ticket_route_requires_authentication_but_not_admin():
    calls = {
        item.call
        for item in _route(
            "/closings/{closing_id}/ticket",
            "POST",
        ).dependant.dependencies
    }

    assert validate_token in calls
    assert is_admin not in calls


@pytest.mark.parametrize(
    ("path", "method"),
    [
        ("/tables", "POST"),
        ("/tables/{table_number}", "DELETE"),
    ],
)
def test_employee_table_configuration_routes_require_authentication(
    path,
    method,
):
    calls = {
        item.call
        for item in _route(path, method).dependant.dependencies
    }

    assert validate_token in calls
    assert is_admin not in calls
