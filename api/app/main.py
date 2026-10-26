import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Body, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.app.auth import bearer_token, require_token
from api.app.coach import ask, configured_coach, normalize_messages
from api.app.demo import ensure_demo, reset_demo
from api.app.parse import configured_model, run_parse
from api.app.storage import (
    Book,
    Duplicate,
    Missing,
    account_for_token,
    delete_row,
    get_row,
    insert_row,
    load_local_book,
    login_account,
    patch_row,
    public_profile,
    save_local_book,
    update_profile,
)
from api.app.trends import build_trends


def _load_env() -> None:
    path = Path(".env")
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    ensure_demo()
    yield


app = FastAPI(lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_model():
    return configured_model()


def _coach_error(exc: RuntimeError) -> str:
    text = str(exc)
    if "413" in text or "rate_limit" in text or "Request too large" in text:
        return "The log is too large for the model right now."
    return text[:180]


def get_book(authorization: str | None = Header(default=None)):
    account = account_for_token(bearer_token(authorization))
    if account is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    book_id = account["id"]
    book = load_local_book(book_id)
    try:
        yield book
    finally:
        if book.dirty:
            save_local_book(book_id, book)


@app.exception_handler(Missing)
def missing_handler(_request, exc: Missing):
    return JSONResponse(status_code=404, content={"detail": exc.row_id})


@app.exception_handler(Duplicate)
def duplicate_handler(_request, exc: Duplicate):
    return JSONResponse(status_code=409, content={"detail": exc.tab})


@app.exception_handler(ValueError)
def value_handler(_request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/demo/reset")
def demo_reset(authorization: str | None = Header(default=None)):
    if not reset_demo(bearer_token(authorization)):
        raise HTTPException(status_code=404, detail="not the demo book")
    return {"ok": True}


def _email_and_password(body: dict) -> tuple[str, str]:
    email = str(body.get("email") or "").strip()
    password = "" if body.get("password") is None else str(body.get("password"))
    if email == "" or password == "":
        raise HTTPException(status_code=400, detail="email and password are required")
    return email, password


@app.post("/login")
def login(body: dict = Body(...)):
    email, password = _email_and_password(body)
    found = login_account(email, password)
    if found is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    return found


@app.get("/me")
def me(authorization: str | None = Header(default=None)):
    account = account_for_token(bearer_token(authorization))
    if account is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    return public_profile(account)


@app.patch("/me")
def patch_me(body: dict = Body(...), authorization: str | None = Header(default=None)):
    updated = update_profile(bearer_token(authorization), body)
    if updated is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    return updated


def _sync_note_text(book: Book, note: dict, previous: str, model) -> dict:
    if note.get("raw_text", "") == previous:
        return note
    # ponytail: a text edit drops generated sets immediately; queued parse waits until a key exists
    if model is None:
        for row in list(book["Sets"]):
            if row["note_id"] == note["id"] and row["source"] == "gemini" and row["edited_by_user"] != "TRUE":
                delete_row(book, "Sets", row["id"])
        return patch_row(
            book,
            "Notes",
            note["id"],
            {"parse_status": "pending", "error_text": None, "parsed_json": None},
        )
    return run_parse(book, note, model, None)["note"]


router = APIRouter(dependencies=[Depends(require_token)])


@router.post("/notes")
def create_note(body: dict = Body(...), book: Book = Depends(get_book), model=Depends(get_model)):
    if not str(body.get("client_request_id") or ""):
        raise HTTPException(status_code=400, detail="client_request_id is required")
    defer = bool(body.get("defer_parse"))
    note = insert_row(book, "Notes", body)
    if defer or model is None or note["parse_status"] == "done":
        sets = [row for row in book["Sets"] if row["note_id"] == note["id"]]
        return {"note": note, "sets": sets}
    return run_parse(book, note, model, None)


@router.post("/notes/{row_id}/parse")
def parse_note(
    row_id: str,
    book: Book = Depends(get_book),
    model=Depends(get_model),
    body: dict | None = Body(default=None),
):
    note = get_row(book, "Notes", row_id)
    if model is None:
        raise HTTPException(status_code=503, detail="parser not configured")
    overwrite = None
    if isinstance(body, dict) and isinstance(body.get("overwrite_set_ids"), list):
        overwrite = [str(item) for item in body["overwrite_set_ids"]]
    return run_parse(book, note, model, overwrite)


@router.patch("/notes/{row_id}")
def patch_note(
    row_id: str,
    body: dict = Body(...),
    book: Book = Depends(get_book),
    model=Depends(get_model),
):
    previous = get_row(book, "Notes", row_id).get("raw_text", "")
    row = patch_row(book, "Notes", row_id, body)
    if "raw_text" in body:
        deferred = bool(body.get("defer_parse"))
        row = _sync_note_text(book, row, previous, None if deferred else model)
    return row


@router.get("/notes")
def list_notes(book: Book = Depends(get_book)):
    return list(book["Notes"])


@router.get("/trends")
def read_trends(book: Book = Depends(get_book)):
    return build_trends(book)


@router.post("/coach")
def coach(body: dict = Body(...), book: Book = Depends(get_book)):
    messages = normalize_messages(body.get("messages"))
    complete = configured_coach()
    if complete is None:
        raise HTTPException(status_code=503, detail="coach not configured")
    try:
        reply = ask(book, messages, complete)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=_coach_error(exc)) from exc
    return {"reply": reply}


app.include_router(router)
