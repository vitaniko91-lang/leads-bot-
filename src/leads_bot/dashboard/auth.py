"""HTTP Basic authentication for the dashboard API.

Single user, credentials from env (DASHBOARD_USER / DASHBOARD_PASSWORD).
Uses constant-time comparison to avoid timing attacks.
"""
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from leads_bot.config import Settings, get_settings

_basic = HTTPBasic(auto_error=True, realm="leads-dashboard")


def require_basic_auth(
    credentials: Annotated[HTTPBasicCredentials, Depends(_basic)],
    settings: Settings = Depends(get_settings),
) -> str:
    """Return the username if creds are valid, else 401."""
    correct_user = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        settings.dashboard_user.encode("utf-8"),
    )
    correct_pwd = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        settings.dashboard_password.encode("utf-8"),
    )
    if not (correct_user and correct_pwd):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": 'Basic realm="leads-dashboard"'},
        )
    return credentials.username
