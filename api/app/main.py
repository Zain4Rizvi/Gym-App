import os
import re

from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse

from api.app.auth import require_token
from api.app.schema import DATE_FIELDS, DATE_TABS, PATHS
from api.app.storage import (
    Book,
    Duplicate,
    Missing,
    delete_row,
    get_row,
    insert_row,
    load_book,
    patch_row,
    rebuild_daily_view,
    row_by_date,
    rows_by_field,
    save_book,
    sets_on_date,
    sheets_service,
    upsert_by_date,
)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

app = FastAPI()


def get_book():
    sheet_id = os.getenv("SHEET_ID")
    if not sheet_id:
        raise HTTPException(status_code=500, detail="SHEET_ID is not set")
    service = sheets_service()
    book = load_book(service, sheet_id)
    try:
        yield book
    finally:
        if book.dirty:
            save_book(service, sheet_id, book)


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


def mount(router: APIRouter) -> None:
    @router.post("/notes")
    def create_note(body: dict = Body(...), book: Book = Depends(get_book)):
        if not str(body.get("client_request_id") or ""):
            raise HTTPException(status_code=400, detail="client_request_id is required")
        note = insert_row(book, "Notes", body)
        sets = [row for row in book["Sets"] if row["note_id"] == note["id"]]
        return {"note": note, "sets": sets}

    @router.post("/notes/{row_id}/parse")
    def parse_note(row_id: str, book: Book = Depends(get_book)):
        get_row(book, "Notes", row_id)
        raise HTTPException(status_code=503, detail="parser not configured")

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

    for tab, path in PATHS.items():
        add_item_routes(router, tab, path)
        if tab in DATE_TABS:
            add_put_by_date(router, tab, path)
        elif tab != "Notes":
            add_post(router, tab, path)
        add_list(router, tab, path)


def add_item_routes(router: APIRouter, tab: str, path: str) -> None:
    @router.get(f"/{path}/{{key}}", operation_id=f"get_{path}")
    def read(key: str, book: Book = Depends(get_book), tab: str = tab):
        if tab in DATE_TABS and DATE_RE.fullmatch(key):
            return row_by_date(book, tab, key)
        return get_row(book, tab, key)

    @router.patch(f"/{path}/{{row_id}}", operation_id=f"patch_{path}")
    def patch(row_id: str, body: dict = Body(...), book: Book = Depends(get_book), tab: str = tab):
        return patch_row(book, tab, row_id, body)

    @router.delete(f"/{path}/{{row_id}}", operation_id=f"delete_{path}")
    def remove(row_id: str, book: Book = Depends(get_book), tab: str = tab):
        delete_row(book, tab, row_id)
        return Response(status_code=204)


def add_put_by_date(router: APIRouter, tab: str, path: str) -> None:
    @router.put(f"/{path}/{{date}}", operation_id=f"put_{path}")
    def put(date: str, body: dict = Body(...), book: Book = Depends(get_book), tab: str = tab):
        if DATE_RE.fullmatch(date) is None:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
        return upsert_by_date(book, tab, date, body)


def add_post(router: APIRouter, tab: str, path: str) -> None:
    @router.post(f"/{path}", operation_id=f"post_{path}")
    def create(body: dict = Body(...), book: Book = Depends(get_book), tab: str = tab):
        return insert_row(book, tab, body)


def add_list(router: APIRouter, tab: str, path: str) -> None:
    @router.get(f"/{path}", operation_id=f"list_{path}")
    def listing(date: str | None = None, book: Book = Depends(get_book), tab: str = tab):
        if tab == "Sets" and date is not None:
            return sets_on_date(book, date)
        field = DATE_FIELDS.get(tab)
        if date is not None and field:
            return rows_by_field(book, tab, field, date)
        return list(book[tab])


router = APIRouter(dependencies=[Depends(require_token)])
mount(router)
app.include_router(router)
