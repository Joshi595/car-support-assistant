"""Agent authentication: a signed JWT (HS256) issued by the frontend's sign-in (Auth.js), or by
`car-support agent-token` in development. Customers do not sign in; a conversation's random UUID is the
customer's handle to it."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from car_support.config import get_settings

_bearer = HTTPBearer(auto_error=False)


def _secret() -> str:
    secret = get_settings().agent_jwt_secret
    if secret is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "agent sign-in is not configured")
    return secret.get_secret_value()


def issue_token(email: str, hours: int = 12) -> str:
    now = datetime.now(UTC)
    claims = {"sub": email, "role": "agent", "iat": now, "exp": now + timedelta(hours=hours)}
    return jwt.encode(claims, _secret(), algorithm="HS256")


def current_agent(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    """The signed-in agent's email, or 401."""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "agent token required")
    try:
        claims = jwt.decode(
            credentials.credentials, _secret(), algorithms=["HS256"], options={"require": ["exp", "sub"]}
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid agent token: {exc}") from exc
    if claims.get("role") != "agent":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not an agent")
    return str(claims["sub"])


Agent = Annotated[str, Depends(current_agent)]
