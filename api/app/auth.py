import os
import secrets

from fastapi import Header, HTTPException

from api.app.storage import account_for_token


def bearer_token(authorization: str | None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme != "Bearer" or token == "":
        return ""
    return token


def token_matches(got: str, expected: str) -> bool:
    if expected == "" or len(got) != len(expected):
        return False
    return secrets.compare_digest(got, expected)


def require_token(authorization: str | None = Header(default=None)) -> None:
    token = bearer_token(authorization)
    expected = os.environ.get("AUTH_TOKEN", "")
    if os.getenv("SHEET_ID"):
        if not token_matches(token, expected):
            raise HTTPException(status_code=401, detail="unauthorized")
        return
    if token_matches(token, expected):
        return
    if account_for_token(token) is not None:
        return
    raise HTTPException(status_code=401, detail="unauthorized")
