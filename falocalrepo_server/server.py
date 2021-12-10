from functools import cache
from functools import lru_cache
from io import BytesIO
from json import dumps
from logging import Logger
from logging import getLogger
from os import PathLike
from pathlib import Path
from sqlite3 import DatabaseError
from typing import Any
from typing import Callable
from typing import Optional
from typing import Union
from zipfile import ZipFile

from PIL import Image
from PIL import UnidentifiedImageError
from chardet import detect as detect_encoding
from fastapi import FastAPI
from fastapi import Request
from fastapi.exceptions import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pydantic import BaseSettings
from uvicorn import run

from .__version__ import __version__
from .database import Database
from .database import clean_username
from .database import default_order
from .database import default_sort
from .database import journals_table
from .database import submissions_table
from .database import users_table


class Settings(BaseSettings):
    database: Database = None
    static_folder: Path = None
    ssl_cert: Path = None
    ssl_key: Path = None


class SearchQuery(BaseModel):
    query: str = ""
    limit: int = 48
    offset: int = 0
    sort: str = ""
    order: str = ""


logger: Logger = getLogger("uvicorn")
fa_base_url: str = "https://www.furaffinity.net"
root: Path = Path(__file__).resolve().parent
app: FastAPI = FastAPI(title="FurAffinity Local Repo", openapi_url=None)
templates: Jinja2Templates = Jinja2Templates(str(root / "templates"))
settings: Settings = Settings(static_folder=root / "static")

button: Callable[[str, str], str] = lambda h, t: f'<a href="{h}"><button>{t}</button></a>'


def serve_error(request: Request, message: str, code: int):
    return templates.TemplateResponse(
        "error.html",
        {"title": f"{app.title} · Error {code}",
         "code": code,
         "message": message,
         "request": request},
        code
    )


@app.on_event("startup")
def log_settings():
    logger.info(f"Using database: {settings.database.database_path}")
    logger.info(f"Using SSL certificate: {settings.ssl_cert}") if settings.ssl_cert else None
    logger.info(f"Using SSL private key: {settings.ssl_key}") if settings.ssl_key else None


@cache
@app.get("/favicon.ico", response_class=FileResponse)
async def serve_favicon(request: Request):
    return await serve_static_file(request, Path("favicon.ico"))


@cache
@app.get("/icon.png", response_class=FileResponse)
@app.get("/touch-icon.png", response_class=FileResponse)
@app.get("/apple-touch-icon.png", response_class=FileResponse)
@app.get("/apple-touch-icon-precomposed.png", response_class=FileResponse)
async def serve_touch_icon():
    return await serve_static_file(Path("touch-icon.png"))


@app.exception_handler(HTTPException)
async def error_unknown(request: Request, err: HTTPException):
    logger.error(repr(err))
    if request.method == "POST":
        return JSONResponse({"errors": [{err.__class__.__name__: err.detail}]}, err.status_code)
    return serve_error(request, err.detail or err.__class__.__name__, err.status_code)


@app.exception_handler(404)
async def error_not_found(request: Request, err: HTTPException):
    if request.method == "POST":
        return JSONResponse({"errors": [{err.__class__.__name__: err.detail}]}, err.status_code)
    return serve_error(request, err.detail or "Not found", err.status_code)


@app.exception_handler(422)
@app.exception_handler(RequestValidationError)
async def error_not_found(request: Request, err: RequestValidationError):
    logger.error(f"{err.__class__.__name__} {err.errors()}")
    if request.method == "POST":
        return JSONResponse({"errors": err.errors()}, 422)
    return serve_error(request, err.errors()[0].get("msg", None) or err.__class__.__name__, 422)


@app.exception_handler(DatabaseError)
async def error_database(request: Request, err: DatabaseError):
    logger.error(repr(err))
    if request.method == "POST":
        return JSONResponse({"errors": [{err.__class__.__name__: err.args}]}, 500)
    return serve_error(request, err.__class__.__name__, 500)


@app.get("/view/{id_}", response_class=HTMLResponse)
@app.get("/full/{id_}", response_class=HTMLResponse)
async def redirect_submission(id_: int):
    return RedirectResponse(app.url_path_for(serve_submission.__name__, id_=str(id_)))


@app.get("/gallery/{username}", response_class=HTMLResponse)
@app.get("/search/gallery/{username}/", response_class=HTMLResponse)
async def serve_user_gallery(request: Request, username: str):
    return await serve_search(request, "submissions", f"Gallery {username}",
                              {"query": f'@author "{clean_username(username)}" @folder "gallery"'})


@app.get("/scraps/{username}", response_class=HTMLResponse)
@app.get("/search/scraps/{username}/", response_class=HTMLResponse)
async def serve_user_scraps(request: Request, username: str):
    return await serve_search(request, "submissions", f"Scraps {username}",
                              {"query": f'@author "{clean_username(username)}" @folder "scraps"'})


@app.get("/submissions/{username}/", response_class=HTMLResponse)
@app.get("/search/submissions/{username}/", response_class=HTMLResponse)
async def serve_user_submissions(request: Request, username: str):
    return await serve_search(request, "submissions", f"Submissions {username}",
                              {"query": f'@author "{clean_username(username)}"'})


@app.get("/journals/{username}/", response_class=HTMLResponse)
@app.get("/search/journals/{username}/", response_class=HTMLResponse)
async def serve_user_journals(request: Request, username: str):
    return await serve_search(request, "journals", f"Journals {username}",
                              {"query": f'@author "{clean_username(username)}"'})


@app.get("/favorites/{username}", response_class=HTMLResponse)
@app.get("/search/favorites/{username}/", response_class=HTMLResponse)
async def serve_user_favorites(request: Request, username: str):
    return await serve_search(request, "submissions", f"Favorites {username}",
                              {"query": f'@favorite "|{clean_username(username)}|"'})


@app.get("/mentions/{username}", response_class=HTMLResponse)
@app.get("/search/mentions/{username}/", response_class=HTMLResponse)
async def serve_user_mentions(request: Request, username: str):
    return await serve_search(request, "submissions", f"Mentions {username}",
                              {"query": f'@mentions "|{clean_username(username)}|"'})


@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    usr_n, sub_n, jrn_n, version = settings.database.load_info()
    return templates.TemplateResponse(
        "info.html",
        {"title": app.title,
         "submissions_total": sub_n,
         "journals_total": jrn_n,
         "users_total": usr_n,
         "version_db": version,
         "version": __version__,
         "request": request}
    )


@app.get("/user/{username}", response_class=HTMLResponse)
async def serve_user(request: Request, username: str):
    if username != (username_clean := clean_username(username)):
        return RedirectResponse(app.url_path_for(serve_user.__name__, username=username_clean))

    user_entry: Optional[dict] = settings.database.load_user(username)
    user_stats: dict[str, int] = settings.database.load_user_stats(username)

    return templates.TemplateResponse(
        "user.html",
        {"title": f"{app.title} · {username}",
         "user": username,
         "folders": user_entry["FOLDERS"] if user_entry else [],
         "gallery_length": user_stats["gallery"],
         "scraps_length": user_stats["scraps"],
         "favorites_length": user_stats["favorites"],
         "mentions_length": user_stats["mentions"],
         "journals_length": user_stats["journals"],
         "request": request}
    )


@app.get("/browse/{table}/", response_class=HTMLResponse)
@app.get("/search/{table}/", response_class=HTMLResponse)  # Keep /search as last option for url_path_for
async def serve_search(request: Request, table: str, title: str = None, args: dict[str, str] = None):
    if (table := table.upper()) not in (submissions_table, journals_table, users_table):
        raise HTTPException(404, f"Table {table.lower()} not found.")

    args = {k.lower(): v for k, v in (args or {}).items()}
    args_req = {k.lower(): v for k, v in request.query_params.items()}
    query: str = " & ".join([f"({q})" for args_ in (args_req, args) if (q := args_.get("query", None))])
    args |= args_req

    if query and request.url.path.startswith("/browse/"):
        return RedirectResponse(app.url_path_for(serve_search.__name__, table=table.lower()) + "?" + request.url.query)

    page: int = int(args.get("page", 1))
    limit: int = int(args.get("limit", 48))
    sort: str = args.get("sort", default_sort[table]).lower()
    order: str = args.get("order", default_order[table]).lower()
    view: str = args.get("view", "").lower()
    view = "grid" if view not in ("list", "grid") and table == submissions_table else view
    view = "list" if table != submissions_table else view

    results: list[dict]
    columns_table: list[str]
    columns_results: list[str]
    columns_list: list[str]
    column_id: str

    results, columns_table, columns_results, columns_list, column_id, sort, order = settings.database.load_search(
        table,
        query.lower().strip(),
        sort,
        order,
        force=request.url.path.startswith("/browse/")
    )

    return templates.TemplateResponse(
        "search.html",
        {"title": f"{app.title} · " + (title or f"{request.url.path.split('/')[1].title()} {table.title()}"),
         "table": table.lower(),
         "query": query,
         "sort": sort,
         "order": order,
         "view": view,
         "allow_view": table == submissions_table,
         "thumbnails": table == submissions_table,
         "columns_table": columns_table,
         "columns_results": columns_results,
         "columns_list": columns_list,
         "column_id": column_id,
         "limit": limit,
         "page": (page := (len(results) // limit) + (1 * bool(len(results) % limit)) if page == -1 else page),
         "offset": (offset := (page - 1) * limit),
         "results": results[offset:offset + limit],
         "results_total": len(results),
         "request": request}
    )


@app.get("/submission/{id_}/", response_class=HTMLResponse)
async def serve_submission(request: Request, id_: int):
    if (sub := settings.database.load_submission(id_)) is None:
        raise HTTPException(
            404,
            f"Submission not found.<br>{button(f'{fa_base_url}/view/{id_}', 'Open on Fur Affinity')}", )

    f: Optional[Path] = None
    if sub["FILEEXT"] == "txt" and sub["FILESAVED"] >= 10:
        f, _ = settings.database.load_submission_files(id_)
    p, n = settings.database.load_prev_next(submissions_table, id_)
    return templates.TemplateResponse(
        "submission.html",
        {"title": f"{app.title} · {sub['TITLE']} by {sub['AUTHOR']}",
         "submission": sub,
         "file_text": f.read_text(encoding=detect_encoding(f.read_bytes())["encoding"]) if f else None,
         "filename": f"submission{('.' + sub['FILEEXT']) * bool(sub['FILEEXT'])}",
         "filename_id": f"{sub['ID']:010d}{('.' + sub['FILEEXT']) * bool(sub['FILEEXT'])}",
         "prev": p,
         "next": n,
         "request": request}
    )


@lru_cache(maxsize=10)
@app.get("/submission/{id_}/file/")
@app.get("/submission/{id_}/file/{_filename}")
async def serve_submission_file(id_: int, _filename=None):
    if (f := settings.database.load_submission_files(id_)[0]) is None:
        raise HTTPException(404)
    elif not f.is_file():
        raise HTTPException(404)
    return FileResponse(f, filename=f.name)


@cache
@app.get("/submission/{id_}/thumbnail/")
@app.get("/submission/{id_}/thumbnail/{_filename}")
@app.get("/submission/{id_}/thumbnail/{x}/")
@app.get("/submission/{id_}/thumbnail/{x}/{_filename}")
@app.get("/submission/{id_}/thumbnail/{x}x{y}>/")
@app.get("/submission/{id_}/thumbnail/{x}x{y}>/{_filename}")
async def serve_submission_thumbnail(id_: int, x: int = None, y: int = None, _filename=None):
    f, t = settings.database.load_submission_files(id_)
    if t is not None and t.is_file():
        if not x:
            return FileResponse(t, filename=t.name)
        with Image.open(t) as img:
            img.thumbnail((x, y or x))
            img.save(f_obj := BytesIO(), img.format, quality=95)
            f_obj.seek(0)
            return StreamingResponse(f_obj, 201, media_type=f"image/{img.format}".lower())
    elif f is not None and f.is_file():
        try:
            with Image.open(f) as img:
                img.thumbnail((x or 400, y or x or 400))
                img.save(f_obj := BytesIO(), img.format, quality=95)
                f_obj.seek(0)
                return StreamingResponse(f_obj, 201, media_type=f"image/{img.format}".lower())
        except UnidentifiedImageError:
            raise HTTPException(404)
    else:
        raise HTTPException(404)


@lru_cache(maxsize=10)
@app.get("/submission/{id_}/zip/")
@app.get("/submission/{id_}/zip/{_filename}")
async def serve_submission_zip(id_: int, _filename=None):
    if (sub := settings.database.load_submission(id_)) is None:
        raise HTTPException(404)

    sub_file, sub_thumb = settings.database.load_submission_files(id_)

    with ZipFile(f_obj := BytesIO(), "w") as z:
        z.writestr(sub_file.name, sub_file.read_bytes()) if sub_file else None
        z.writestr(sub_thumb.name, sub_thumb.read_bytes()) if sub_thumb else None
        z.writestr("description.html", sub["DESCRIPTION"].encode())
        z.writestr("metadata.json", dumps({k: v for k, v in sub.items() if k != "DESCRIPTION"}).encode())

    f_obj.seek(0)
    return StreamingResponse(f_obj, media_type="application/zip")


@app.get("/journal/{id_}/", response_class=HTMLResponse)
async def serve_journal(request: Request, id_: int):
    if (jrnl := settings.database.load_journal(id_)) is None:
        raise HTTPException(
            404,
            f"Journal not found.<br>{button(f'{fa_base_url}/journal/{id_}', 'Open on Fur Affinity')}")

    p, n = settings.database.load_prev_next(journals_table, id_)
    return templates.TemplateResponse(
        "journal.html",
        {"title": f"{app.title} · {jrnl['TITLE']} by {jrnl['AUTHOR']}",
         "journal": jrnl,
         "prev": p,
         "next": n,
         "request": request}
    )


@lru_cache(maxsize=10)
@app.get("/journal/{id_}/zip/")
@app.get("/journal/{id_}/zip/{filename}")
async def serve_journal_zip(id_: int, _filename=None):
    if (jrnl := settings.database.load_journal(id_)) is None:
        raise HTTPException(404)

    with ZipFile(f_obj := BytesIO(), "w") as z:
        z.writestr("content.html", jrnl["CONTENT"].encode())
        z.writestr("metadata.json", dumps({k: v for k, v in jrnl.items() if k != "CONTENT"}).encode())

    f_obj.seek(0)
    return StreamingResponse(f_obj, media_type="application/zip")


@cache
@app.get("/static/{file:path}", response_class=FileResponse)
async def serve_static_file(file: Path):
    if not (file := settings.static_folder / file).is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(file, filename=file.name)


@app.get("/json/search/{table}/", response_class=JSONResponse)
@app.post("/json/search/{table}/", response_class=JSONResponse)
async def serve_search_json(request: Request, table: str, query_data: SearchQuery = None):
    if query_data is None:
        query_data = SearchQuery()
        query_data.query = request.query_params.get("query", query_data.query)
        query_data.offset = int(request.query_params.get("offset", query_data.offset))
        query_data.limit = int(request.query_params.get("limit", query_data.limit))
        query_data.sort = request.query_params.get("sort", query_data.sort)
        query_data.order = request.query_params.get("order", query_data.order)

    results, cols_table, cols_results, cols_list, col_id, sort, order = settings.database.load_search_uncached(
        table := table.upper(),
        query_data.query.lower().strip(),
        query_data.sort,
        query_data.order,
        force=True
    )

    return {"table": table.lower(),
            "query": query_data.query,
            "sort": query_data.sort,
            "order": query_data.order,
            "columns_table": cols_table,
            "columns_results": cols_results,
            "columns_list": cols_list,
            "column_id": col_id,
            "limit": query_data.limit,
            "offset": query_data.offset,
            "results": results[query_data.offset:query_data.offset + query_data.limit],
            "results_total": len(results)}


@app.get("/json/submission/{id_}/", response_class=JSONResponse)
@app.post("/json/submission/{id_}/", response_class=JSONResponse)
async def serve_submission_json(id_: int):
    if not (s := settings.database.load_submission_uncached(id_)):
        raise HTTPException(404)
    else:
        return s


@app.get("/json/journal/{id_}/", response_class=JSONResponse)
@app.post("/json/journal/{id_}/", response_class=JSONResponse)
async def serve_journal_json(id_: int):
    if not (j := settings.database.load_journal_uncached(id_)):
        raise HTTPException(404)
    else:
        return j


@app.get("/json/user/{username}", response_class=JSONResponse)
@app.post("/json/user/{username}", response_class=JSONResponse)
async def serve_user_json(username: str):
    username = clean_username(username)
    user_entry: Optional[dict] = settings.database.load_user_uncached(username)
    user_stats: dict[str, int] = settings.database.load_user_stats_uncached(username)

    return {"user": username,
            "folders": user_entry["FOLDERS"] if user_entry else [],
            "length": {
                "gallery": user_stats["gallery"],
                "scraps": user_stats["scraps"],
                "favorites": user_stats["favorites"],
                "mentions": user_stats["mentions"],
                "journals": user_stats["journals"]
            }}


def run_redirect(host: str, port_listen: int, port_redirect: int):
    redirect_app: FastAPI = FastAPI()
    redirect_app.add_event_handler("startup", lambda: logger.info(f"Redirecting target https://{host}:{port_redirect}"))
    redirect_app.add_route(
        "/{__:path}",
        lambda r, *_: RedirectResponse(f"https://{r.url.hostname}:{port_redirect}{r.url.path}?{r.url.query}"),
        ["GET"]
    )

    try:
        # noinspection PyTypeChecker
        run(redirect_app, host=host, port=port_listen)
    except KeyboardInterrupt:
        pass


# noinspection HttpUrlsUsage
def server(database_path: Union[str, PathLike], host: str = "0.0.0.0", port: int = None,
           ssl_cert: Union[str, PathLike] = None, ssl_key: Union[str, PathLike] = None, redirect_port: int = None):
    if redirect_port:
        return run_redirect(host, port, redirect_port)
    settings.database = Database(Path(database_path).resolve())
    run_args: dict[str, Any] = {}
    if ssl_cert and ssl_key:
        settings.ssl_cert, settings.ssl_key = Path(ssl_cert), Path(ssl_key)
        if not settings.ssl_cert.is_file():
            raise FileNotFoundError(f"SSL certificate {settings.ssl_cert}")
        elif not settings.ssl_key.is_file():
            raise FileNotFoundError(f"SSL private key {settings.ssl_key}")
        run_args |= {"port": port or 443, "ssl_certfile": settings.ssl_cert, "ssl_keyfile": settings.ssl_key}
    run_args |= {"port": run_args.get("port", port) or 80}
    try:
        # noinspection PyTypeChecker
        run(app, host=host, **run_args)
    except KeyboardInterrupt:
        pass
