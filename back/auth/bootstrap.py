import os
from hashlib import sha256

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from db.db_conn import engine
from db.db_models import UserModel


def initialize_users() -> None:
    with Session(engine) as session:
        session.execute(
            update(UserModel)
            .where(UserModel.role.not_in(("admin", "empleado")))
            .values(role="empleado")
        )

        existing_user = session.scalar(select(UserModel.id).limit(1))
        if existing_user is None:
            username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin").strip()
            password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "admin").strip()
            if not username or not password:
                raise RuntimeError(
                    "BOOTSTRAP_ADMIN_USERNAME y BOOTSTRAP_ADMIN_PASSWORD "
                    "son obligatorios para inicializar una base vacía"
                )

            session.add(
                UserModel(
                    username=username,
                    password=sha256(password.encode("utf-8")).hexdigest(),
                    role="admin",
                    deleted_at=None,
                )
            )

        session.commit()
