from hashlib import sha256
from http import HTTPStatus
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from db.db_models import UserModel
from users.models.user_dto import UpdateUserRequest
from users.users_service.users_service import UserService


class FakeSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def _service_with_user(role="empleado"):
    session = FakeSession()
    service = UserService(session)
    service.repository = MagicMock()
    user = UserModel(
        id=2,
        username="nico",
        password=sha256(b"anterior").hexdigest(),
        role=role,
        deleted_at=None,
    )
    service.repository.get_user_by_id.return_value = user
    service.repository.find_by_username_except.return_value = None
    service.repository.count_active_admins.return_value = 2
    return service, session, user


def test_admin_can_update_username_password_and_role():
    service, session, user = _service_with_user()

    response = service.update_user(
        2,
        UpdateUserRequest(
            username="nuevo",
            password="secreto",
            role="admin",
        ),
    )

    assert response.username == "nuevo"
    assert response.role == "admin"
    assert user.password == sha256(b"secreto").hexdigest()
    assert session.commits == 1


def test_duplicate_username_is_rejected():
    service, session, _ = _service_with_user()
    service.repository.find_by_username_except.return_value = UserModel(
        id=3,
        username="ocupado",
        password="hash",
        role="empleado",
        deleted_at=None,
    )

    with pytest.raises(HTTPException) as error:
        service.update_user(
            2,
            UpdateUserRequest(username="ocupado"),
        )

    assert error.value.status_code == HTTPStatus.CONFLICT
    assert session.commits == 0


def test_last_admin_cannot_be_demoted():
    service, session, user = _service_with_user(role="admin")
    service.repository.count_active_admins.return_value = 1

    with pytest.raises(HTTPException) as error:
        service.update_user(
            2,
            UpdateUserRequest(role="empleado"),
        )

    assert error.value.status_code == HTTPStatus.CONFLICT
    assert user.role == "admin"
    assert session.commits == 0
