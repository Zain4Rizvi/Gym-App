from fastapi import Header, HTTPException

from api.app.storage import account_for_token


def bearer_token(authorization: str | None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme != "Bearer" or token == "":
        return ""
    return token


def require_token(authorization: str | None = Header(default=None)) -> None:
    if account_for_token(bearer_token(authorization)) is None:
        raise HTTPException(status_code=401, detail="unauthorized")
