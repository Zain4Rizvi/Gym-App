import uuid
from pathlib import Path

from api.app.storage import data_dir


class PhotoPath(Exception):
    pass


def book_dir(book_id: str) -> Path:
    if book_id in {"", ".", ".."} or any(char in book_id for char in "/\\"):
        raise PhotoPath(book_id)
    root = (data_dir() / "photos" / book_id).resolve()
    base = (data_dir() / "photos").resolve()
    if not root.is_relative_to(base):
        raise PhotoPath(book_id)
    return root


def save_photo(book_id: str, payload: bytes, filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".heic", ".gif"}:
        suffix = ""
    if suffix == ".jpeg":
        suffix = ".jpg"
    name = f"{uuid.uuid4().hex}{suffix}"
    root = book_dir(book_id)
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise PhotoPath(name)
    root.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return f"photos/{book_id}/{name}"


def resolve_photo(book_id: str, storage_uri: str) -> Path:
    root = book_dir(book_id)
    uri = (storage_uri or "").replace("\\", "/")
    prefix = f"photos/{book_id}/"
    if not uri.startswith(prefix) or ".." in uri.split("/"):
        raise PhotoPath(storage_uri)
    name = uri[len(prefix) :]
    if name == "" or "/" in name:
        raise PhotoPath(storage_uri)
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise PhotoPath(storage_uri)
    return path
