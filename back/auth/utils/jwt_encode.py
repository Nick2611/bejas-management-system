from datetime import datetime, timedelta, timezone

import jwt

from auth.auth import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from db.db_models import UserModel


def jwt_encode_user(user: UserModel) -> str:
    payload = {
        "sub": user.username,
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        ),
    }

    return jwt.encode(payload, key=SECRET_KEY, algorithm=ALGORITHM)
