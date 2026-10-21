import os
import secrets

from fastapi import Header, HTTPException


def require_token(authorization: str | None = Header(default=None)) -> None:
    expected = os.environ.get("AUTH_TOKEN", "")
    scheme, _, got = (authorization or "").partition(" ")
    if scheme != "Bearer" or expected == "" or not secrets.compare_digest(got, expected):
        raise HTTPException(status_code=401, detail="unauthorized")
