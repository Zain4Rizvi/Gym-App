import os
import re

from fastapi import APIRouter, Body, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse

from api.app.auth import bearer_token, require_token, token_matches
from api.app.parse import configured_model, learn_alias, run_parse
from api.app.photos import PhotoPath, resolve_photo, save_photo
from api.app.schema import DATE_FIELDS, DATE_TABS, PATHS, POSES
from api.app.storage import (
    SHARED_BOOK_ID,
    Book,
    Duplicate,
    Missing,
    account_for_token,
    delete_row,
    get_row,
    insert_row,
    load_book,
    load_local_book,
    login_account,
    patch_row,
    rebuild_daily_view,
    register_account,
    row_by_date,
    rows_by_field,
    save_book,
    save_local_book,
    sets_on_date,
    sheets_service,
    toggle_supplement,
    upsert_by_date,
)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

app = FastAPI()


def get_model():
    return configured_model()


def get_book(authorization: str | None = Header(default=None)):
    sheet_id = os.getenv("SHEET_ID")
    token = bearer_token(authorization)
    if sheet_id:
        if not token_matches(token, os.environ.get("AUTH_TOKEN", "")):
            raise HTTPException(status_code=401, detail="unauthorized")
        service = sheets_service()
        book = load_book(service, sheet_id)
        book.book_id = sheet_id
        try:
            yield book
        finally:
            if book.dirty:
                save_book(service, sheet_id, book)
        return
    if token_matches(token, os.environ.get("AUTH_TOKEN", "")):
        book_id = SHARED_BOOK_ID
    else:
        account = account_for_token(token)
        if account is None:
            raise HTTPException(status_code=401, detail="unauthorized")
        book_id = account["id"]
    book = load_local_book(book_id)
    book.book_id = book_id
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


def _email_and_password(body: dict) -> tuple[str, str]:
    email = str(body.get("email") or "").strip()
    password = "" if body.get("password") is None else str(body.get("password"))
    if email == "" or password == "":
        raise HTTPException(status_code=400, detail="email and password are required")
    return email, password


@app.post("/accounts")
def create_account(body: dict = Body(...)):
    email, password = _email_and_password(body)
    return register_account(email, password)


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
    return {"email": account["email"]}


def mount(router: APIRouter) -> None:
    @router.post("/notes")
    def create_note(body: dict = Body(...), book: Book = Depends(get_book), model=Depends(get_model)):
        if not str(body.get("client_request_id") or ""):
            raise HTTPException(status_code=400, detail="client_request_id is required")
        note = insert_row(book, "Notes", body)
        if model is None or note["parse_status"] == "done":
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

    @router.post("/daily-view/rebuild")
    def rebuild(book: Book = Depends(get_book)):
        rebuild_daily_view(book)
        return book["DailyView"]

    @router.get("/daily-view")
    def daily_all(book: Book = Depends(get_book)):
        return book["DailyView"]

    @router.get("/daily-view/{date}")
    def daily_one(date: str, book: Book = Depends(get_book)):
        return row_by_date(book, "DailyView", date)

    @router.post("/supplements/toggle")
    def toggle_supplement_log(body: dict = Body(...), book: Book = Depends(get_book)):
        date = str(body.get("date") or "")
        item = str(body.get("item") or "").strip()
        if DATE_RE.fullmatch(date) is None:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
        if item == "":
            raise HTTPException(status_code=400, detail="item is required")
        row = toggle_supplement(book, date, item)
        if row is None:
            return Response(status_code=204)
        return row

    @router.post("/media")
    async def create_media(request: Request, book: Book = Depends(get_book)):
        if "multipart/form-data" in request.headers.get("content-type", ""):
            form = await request.form()
            date = str(form.get("date") or "")
            pose = str(form.get("pose") or "")
            upload = form.get("file")
            if DATE_RE.fullmatch(date) is None:
                raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
            if pose not in POSES:
                raise HTTPException(status_code=400, detail="pose")
            if upload is None or not hasattr(upload, "read"):
                raise HTTPException(status_code=400, detail="file is required")
            book_id = getattr(book, "book_id", "")
            payload = await upload.read()
            try:
                uri = save_photo(book_id, payload, getattr(upload, "filename", "") or "")
            except PhotoPath:
                raise HTTPException(status_code=400, detail="path")
            return insert_row(book, "Media", {"date": date, "pose": pose, "storage_uri": uri})
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="json object")
        return insert_row(book, "Media", body)

    @router.get("/media/{row_id}/file")
    def media_file(row_id: str, book: Book = Depends(get_book)):
        row = get_row(book, "Media", row_id)
        try:
            path = resolve_photo(getattr(book, "book_id", ""), row.get("storage_uri", ""))
        except PhotoPath:
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(path)

    for tab, path in PATHS.items():
        add_item_routes(router, tab, path)
        if tab in DATE_TABS:
            add_put_by_date(router, tab, path)
        elif tab not in {"Notes", "Media"}:
            add_post(router, tab, path)
        add_list(router, tab, path)


def add_item_routes(router: APIRouter, tab: str, path: str) -> None:
    sheet = tab

    @router.get(f"/{path}/{{key}}", operation_id=f"get_{path}")
    def read(key: str, book: Book = Depends(get_book)):
        if sheet in DATE_TABS and DATE_RE.fullmatch(key):
            return row_by_date(book, sheet, key)
        return get_row(book, sheet, key)

    @router.patch(f"/{path}/{{row_id}}", operation_id=f"patch_{path}")
    def patch(row_id: str, body: dict = Body(...), book: Book = Depends(get_book)):
        assigning = sheet == "Sets" and bool(body.get("exercise_id"))
        if sheet == "Sets":
            body = {**body, "edited_by_user": True}
        row = patch_row(book, sheet, row_id, body)
        if assigning:
            learn_alias(book, row)
        return row

    @router.delete(f"/{path}/{{row_id}}", operation_id=f"delete_{path}")
    def remove(row_id: str, book: Book = Depends(get_book)):
        delete_row(book, sheet, row_id)
        return Response(status_code=204)


def add_put_by_date(router: APIRouter, tab: str, path: str) -> None:
    sheet = tab

    @router.put(f"/{path}/{{date}}", operation_id=f"put_{path}")
    def put(date: str, body: dict = Body(...), book: Book = Depends(get_book)):
        if DATE_RE.fullmatch(date) is None:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
        return upsert_by_date(book, sheet, date, body)


def add_post(router: APIRouter, tab: str, path: str) -> None:
    sheet = tab

    @router.post(f"/{path}", operation_id=f"post_{path}")
    def create(body: dict = Body(...), book: Book = Depends(get_book)):
        return insert_row(book, sheet, body)


def add_list(router: APIRouter, tab: str, path: str) -> None:
    sheet = tab

    @router.get(f"/{path}", operation_id=f"list_{path}")
    def listing(date: str | None = None, book: Book = Depends(get_book)):
        if sheet == "Sets" and date is not None:
            return sets_on_date(book, date)
        field = DATE_FIELDS.get(sheet)
        if date is not None and field:
            return rows_by_field(book, sheet, field, date)
        return list(book[sheet])


router = APIRouter(dependencies=[Depends(require_token)])
mount(router)
app.include_router(router)
