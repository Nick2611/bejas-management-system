from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError

from db.db_conn import SessionDep
from db.db_models import UserModel

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth")

SECRET_KEY="2a3331699ddb69b8771b9aeddffb77606db90604ad28b408f025d54dcca12de2"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=1440


def validate_token(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: SessionDep,
):
    try:
        claims = jwt.decode(
            token,
            key=SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        user_id = int(claims["user_id"])
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o vencido",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o vencido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = session.get(UserModel, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El usuario ya no está activo",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims["username"] = user.username
    claims["sub"] = user.username
    claims["role"] = (
        user.role if user.role in ("admin", "empleado") else "empleado"
    )
    return claims


def is_admin(
    claims: Annotated[dict, Depends(validate_token)],
):
    if claims.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol admin",
        )
    return claims
    
