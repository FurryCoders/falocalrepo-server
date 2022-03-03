from datetime import datetime
from functools import reduce
from io import BytesIO
from json import dumps
from logging import Logger
from logging import getLogger
from os import PathLike
from pathlib import Path
from re import IGNORECASE
from re import Pattern
from re import compile as re_compile
from secrets import compare_digest
from sqlite3 import DatabaseError
from sqlite3 import OperationalError
from typing import Any
from typing import Callable
from typing import Coroutine
from zipfile import ZipFile

from PIL import Image
from PIL import UnidentifiedImageError
from bs4 import BeautifulSoup
from bs4.element import Tag
from chardet import detect as detect_encoding
from falocalrepo_database.tables import JournalsColumns
from falocalrepo_database.tables import SubmissionsColumns
from falocalrepo_database.tables import UsersColumns
from fastapi import FastAPI
from fastapi import Form
from fastapi import Request
from fastapi import Response
from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic
from fastapi.security import HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from htmlmin import minify
from pydantic import BaseModel
from pydantic import BaseSettings
from uvicorn import run
from uvicorn.config import LOGGING_CONFIG

from .__version__ import __version__
from .database import Database
from .database import clean_username
from .database import default_order
from .database import default_sort
from .database import journals_table
from .database import submissions_table
from .database import users_table


class SearchSettings(BaseSettings):
    view: dict[str, str] = {users_table: "grid", submissions_table: "grid", journals_table: "grid"}
    limit: dict[str, str] = {users_table: "48", submissions_table: "48", journals_table: "48"}
    sort: dict[str, str] = default_sort
    order: dict[str, str] = default_order

    def reset(self):
        self.view = {users_table: "grid", submissions_table: "grid", journals_table: "grid"}
        self.limit = {users_table: "48", submissions_table: "48", journals_table: "48"}
        self.sort = default_sort
        self.order = default_order

    def load(self, obj: dict):
        self.view = obj.get("view", self.view)
        self.limit = obj.get("limit", self.limit)
        self.sort = obj.get("sort", self.sort)
        self.order = obj.get("order", self.order)


class Settings(BaseSettings):
    database: Database = None
    static_folder: Path = None
    ssl_cert: Path = None
    ssl_key: Path = None
    precache: bool = False
    username: str = None
    password: str = None


class SearchQuery(BaseModel):
    query: str = ""
    limit: int = 48
    offset: int = 0
    sort: str = ""
    order: str = ""


logger: Logger = getLogger("uvicorn")
LOGGING_CONFIG["formatters"]["access"]["fmt"] = \
    '%(levelprefix)s %(asctime)s %(client_addr)s - %(request_line)s %(status_code)s %(msecs).0fms'

fa_base_url: str = "https://www.furaffinity.net"
fa_link: Pattern = re_compile(r"(https?://)?(www.)?furaffinity.net", flags=IGNORECASE)
root: Path = Path(__file__).resolve().parent
app: FastAPI = FastAPI(title="FurAffinity Local Repo", openapi_url=None)
templates: Jinja2Templates = Jinja2Templates(str(root / "templates"))
settings: Settings = Settings(static_folder=root / "static")
search_settings: SearchSettings = SearchSettings()
security: HTTPBasic = HTTPBasic()

bbcode_expressions: list[tuple[Pattern, str]] = [
    (re_compile(r"\[(/?)([bius]|sup|sub|h\d)]"), r"<\1\2>",),
    (re_compile(r"\[color=([^]]+)]"), r'<span style="color: \1">,'),
    (re_compile(r"\[/color]"), "</span>",),
    (re_compile(r"\[(left|center|right)]"), r'<p style="text-align: \1">',),
    (re_compile(r"\[/(left|center|right)]"), "</p>",),
    (re_compile(r"\[quote=([^]]+)]"), r'<blockquote cite="\1">'),
    (re_compile(r"\[quote]"), "<blockquote>"),
    (re_compile(r"\[/quote]"), "</blockquote>"),
    (re_compile(r"\[url=([^]]+)]"), r'<a href="\1">'),
    (re_compile(r"\[/url]"), "</a>"),
    (re_compile(r"\[yt]((?:.(?!\[yt]))+)\[/yt]"), r'</a href="\1">\1</a>'),
    (re_compile(r"(:icon([^:]+):|:([^:]+)icon:)"), r'<a href="/user/\2\3">@\2\3</a>'),
    (re_compile(r"((?:\n(?!\n)|[^\n])+)\n\n+"), r"<p>\1</p>"),
    (re_compile(r"\n"), "<br/>")
]

app.mount("/static", StaticFiles(directory=settings.static_folder), "static")


def bbcode_to_html(text: str) -> str:
    return reduce(lambda t, es: es[0].sub(es[1], t), bbcode_expressions, text.strip() + "\n\n")


def clean_html(html: str) -> str:
    html_parsed: BeautifulSoup = BeautifulSoup(html, "lxml")
    for icon in html_parsed.select("a.iconusername > img"):
        parent: Tag = icon.parent
        parent.clear()
        parent.insert(0, f"@{icon.attrs['title']}")
    for code in html_parsed.select("code"):
        code.name = "div"
    for link in html_parsed.select("a[href*='furaffinity.net']"):
        link.attrs["href"] = "/" + fa_link.sub("", link.attrs["href"]).strip("/")
    return str(html_parsed)


def serialise_entry(entry: dict) -> dict:
    return {k: sorted(v) if isinstance(v, set) else str(v) if isinstance(v, datetime) else v for k, v in entry.items()}


def error_response(request: Request, code: int, message: str = None, buttons: list[tuple[str, str]] = None) -> Response:
    return templates.TemplateResponse(
        "error.html",
        {"app": app.title,
         "title": f"Error {code}",
         "code": code,
         "message": message,
         "buttons": buttons,
         "request": request},
        code
    )


async def auth_middleware(request: Request, call_next: Callable[[Request], Coroutine[Any, Any, Response]]) -> Response:
    if request.url.path.startswith("/static"):
        return await call_next(request)

    try:
        creds: HTTPBasicCredentials = await security(request)
        if compare_digest(creds.username, settings.username) and compare_digest(creds.password, settings.password):
            return await call_next(request)
    except HTTPException as err:
        if err.status_code != status.HTTP_401_UNAUTHORIZED:
            return error_response(request, err.status_code, err.detail)

    return Response(
        error_response(request, status.HTTP_401_UNAUTHORIZED, "Incorrect username or password",
                       [("Retry", str(request.url))]).body,
        status.HTTP_401_UNAUTHORIZED, {"WWW-Authenticate": "Basic"})


@app.on_event("startup")
def log_settings():
    logger.info(f"Version: {__version__}")
    logger.info(f"Using database: {settings.database.path} ({settings.database.version})")
    logger.info(f"Using SSL certificate: {settings.ssl_cert}") if settings.ssl_cert else None
    logger.info(f"Using SSL private key: {settings.ssl_key}") if settings.ssl_key else None
    logger.info(f"Using HTTP Basic authentication") if settings.username or settings.password else None
    if settings.precache:
        for table in (settings.database.users, settings.database.submissions, settings.database.journals):
            for order in ("asc", "desc"):
                logger.info(
                    f"Caching {table.name.upper()}:{(sort := default_sort[table.name]).upper()}:{order.upper()}")
                settings.database.load_search(table.name, "", sort, order)


@app.on_event("shutdown")
def close_database():
    if settings.database.is_open:
        settings.database.close()


@app.get("/favicon.ico", response_class=FileResponse)
async def serve_favicon():
    return RedirectResponse("/static/favicon.ico", 301)


@app.get("/icon.png", response_class=FileResponse)
@app.get("/touch-icon.png", response_class=FileResponse)
@app.get("/apple-touch-icon.png", response_class=FileResponse)
@app.get("/apple-touch-icon-precomposed.png", response_class=FileResponse)
async def serve_touch_icon():
    return RedirectResponse("/static/touch-icon.png", 301)


@app.exception_handler(HTTPException)
async def error_unknown(request: Request, err: HTTPException):
    logger.error(repr(err))
    if request.method == "POST":
        return JSONResponse({"errors": [{err.__class__.__name__: err.detail}]}, err.status_code)
    return error_response(request, err.status_code, err.detail or None)


@app.exception_handler(404)
async def error_not_found(request: Request, err: HTTPException):
    if request.method == "POST":
        return JSONResponse({"errors": [{err.__class__.__name__: err.detail}]}, err.status_code)
    return error_response(request, err.status_code, err.detail or "Not found")


@app.exception_handler(422)
@app.exception_handler(RequestValidationError)
async def error_not_found(request: Request, err: RequestValidationError):
    logger.error(f"{err.__class__.__name__} {err.errors()}")
    if request.method == "POST":
        return JSONResponse({"errors": err.errors()}, 422)
    return error_response(request, 422, err.errors()[0].get("msg", None) or err.__class__.__name__)


@app.exception_handler(DatabaseError)
@app.exception_handler(OperationalError)
async def error_database(request: Request, err: DatabaseError | OperationalError):
    logger.error(repr(err))
    if request.method == "POST":
        return JSONResponse({"errors": [{err.__class__.__name__: err.args}]}, 500)
    return error_response(request, 500, "<br/>".join([err.__class__.__name__, *map(str, err.args)]))


@app.exception_handler(FileNotFoundError)
async def error_database_not_found(request: Request, err: FileNotFoundError):
    logger.error(repr(err))
    if request.method == "POST":
        return JSONResponse({"errors": [{err.__class__.__name__: err.args}]}, status.HTTP_503_SERVICE_UNAVAILABLE)
    return error_response(request, 500, "Database not found")


@app.get("/view/{id_}/", response_class=HTMLResponse)
@app.get("/full/{id_}/", response_class=HTMLResponse)
async def redirect_submission(id_: int):
    return RedirectResponse(app.url_path_for(serve_submission.__name__, id_=str(id_)),
                            status.HTTP_301_MOVED_PERMANENTLY)


@app.get("/gallery/{username}/", response_class=HTMLResponse)
@app.get("/search/gallery/{username}/", response_class=HTMLResponse)
async def serve_user_gallery(request: Request, username: str):
    return await serve_search(request, "submissions", f"Gallery {username}",
                              {"query": f'@author "{clean_username(username)}" @folder "gallery"'})


@app.get("/scraps/{username}/", response_class=HTMLResponse)
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


@app.get("/favorites/{username}/", response_class=HTMLResponse)
@app.get("/search/favorites/{username}/", response_class=HTMLResponse)
async def serve_user_favorites(request: Request, username: str):
    return await serve_search(request, "submissions", f"Favorites {username}",
                              {"query": f'@favorite "|{clean_username(username)}|"'})


@app.get("/mentions/{username}/", response_class=HTMLResponse)
@app.get("/search/mentions/{username}/", response_class=HTMLResponse)
async def serve_user_mentions(request: Request, username: str):
    return await serve_search(request, "submissions", f"Mentions {username}",
                              {"query": f'@mentions "|{clean_username(username)}|"'})


@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    usr_n, sub_n, jrn_n, version = settings.database.load_info()
    return HTMLResponse(minify(templates.get_template("info.html").render({
        "app": app.title,
        "title": "",
        "submissions_total": sub_n,
        "journals_total": jrn_n,
        "users_total": usr_n,
        "version_db": version,
        "version": __version__,
        "request": request}),
        remove_comments=True))


@app.get("/settings/")
async def serve_settings(request: Request):
    return HTMLResponse(minify(templates.get_template("settings.html").render({
        "app": app.title,
        "title": "Search Settings",
        "tables": [users_table, submissions_table, journals_table],
        "columns": {users_table: [c.name for c in UsersColumns],
                    submissions_table: [c.name for c in SubmissionsColumns] + ["relevance"],
                    journals_table: [c.name for c in JournalsColumns]},
        "settings": search_settings,
        "default_sort": default_sort,
        "default_order": default_order,
        "request": request}),
        remove_comments=True))


@app.get("/settings/set/")
async def save_settings(request: Request):
    for param, value in request.query_params.items():
        table, setting = param.split(".")
        search_settings.__setattr__(setting, search_settings.__getattribute__(setting) | {table.upper(): value})

    if settings.database.read_only:
        return Response("Database is read only, settings will be reset on restart",
                        status_code=status.HTTP_403_FORBIDDEN)

    settings.database.save_settings("SEARCH", search_settings.dict())

    return Response("Settings saved", status_code=200)


@app.get("/user/{username}/", response_class=HTMLResponse)
async def serve_user(request: Request, username: str):
    if username != (username_clean := clean_username(username)):
        return RedirectResponse(app.url_path_for(serve_user.__name__, username=username_clean))

    user_entry: dict | None = settings.database.load_user(username)
    user_stats: dict[str, int] = settings.database.load_user_stats(username)
    p, n = settings.database.load_prev_next(users_table, username) if user_entry else (0, 0)

    return HTMLResponse(minify(templates.get_template("user.html").render({
        "app": app.title,
        "title": username,
        "user": username,
        "folders": user_entry["FOLDERS"] if user_entry else [],
        "active": user_entry["ACTIVE"] if user_entry else True,
        "gallery_length": user_stats["gallery"],
        "scraps_length": user_stats["scraps"],
        "favorites_length": user_stats["favorites"],
        "mentions_length": user_stats["mentions"],
        "journals_length": user_stats["journals"],
        "userpage": clean_html(user_entry["USERPAGE"]) if user_entry else "",
        "in_database": user_entry is not None,
        "prev": p,
        "next": n,
        "request": request}),
        remove_comments=True))


@app.get("/search/{table}/", response_class=HTMLResponse)
async def serve_search(request: Request, table: str, title: str = None, args: dict[str, str] = None):
    if (table := table.upper()) not in (submissions_table, journals_table, users_table):
        raise HTTPException(404, f"Table {table.lower()} not found.")

    args = {k.lower(): v for k, v in (args or {}).items()}
    args_req = {k.lower(): v for k, v in request.query_params.items()}
    query: str = " & ".join([f"({q})" for args_ in (args_req, args) if (q := args_.get("query", None))])
    args |= args_req

    page: int = p if (p := int(args.get("page", 1))) > 0 else 1
    limit: int = l if (l := int(args.get("limit", search_settings.limit[table]))) > 0 else 48
    sort: str = args.get("sort", search_settings.sort[table]).lower()
    order: str = args.get("order", search_settings.order[table]).lower()
    view: str = v if (v := args.get("view", search_settings.view[table]).lower()) in ("list", "grid") else "grid"

    results: list[dict]
    columns_table: list[str]
    columns_results: list[str]
    columns_list: list[str]
    column_id: str

    results, columns_table, columns_results, columns_list, column_id, sort, order = settings.database.load_search(
        table,
        query.lower().strip(),
        sort,
        order
    )

    return HTMLResponse(minify(templates.get_template("search.html").render({
        "app": app.title,
        "title": title or f"Search {table.title()}",
        "action": request.url.path,
        "table": table.lower(),
        "query": query,
        "sort": sort,
        "order": order,
        "view": view,
        "thumbnails": table == submissions_table,
        "columns_table": columns_table,
        "columns_results": columns_results,
        "columns_list": columns_list,
        "column_id": column_id,
        "limit": limit,
        "page": page,
        "offset": (offset := (page - 1) * limit),
        "results": results[offset:offset + limit],
        "results_total": len(results),
        "request": request}),
        remove_comments=True))


@app.get("/submission/{id_}/", response_class=HTMLResponse)
async def serve_submission(request: Request, id_: int):
    if (sub := settings.database.load_submission(id_)) is None:
        return error_response(request, 404, "Submission not found",
                              [("Open on Fur Affinity", f"{fa_base_url}/view/{id_}")])

    f: Path | None = None
    if sub["FILEEXT"] == "txt" and sub["FILESAVED"] & 0b10:
        f, _ = settings.database.load_submission_files(id_)
    p, n = settings.database.load_prev_next(submissions_table, id_)
    return HTMLResponse(minify(templates.get_template("submission.html").render({
        "app": app.title,
        "title": f"{sub['TITLE']} by {sub['AUTHOR']}",
        "submission": sub | {"DESCRIPTION": clean_html(sub["DESCRIPTION"])},
        "file_text": bbcode_to_html(f.read_text(encoding=detect_encoding(f.read_bytes())["encoding"])) if f else None,
        "filename": f"submission{('.' + sub['FILEEXT']) * bool(sub['FILEEXT'])}",
        "filename_id": f"{sub['ID']:010d}{('.' + sub['FILEEXT']) * bool(sub['FILEEXT'])}",
        "prev": p,
        "next": n,
        "request": request}),
        remove_comments=True))


@app.get("/submission/{id_}/file/")
@app.get("/submission/{id_}/file/{_filename}")
async def serve_submission_file(id_: int, _filename=None):
    if (f := settings.database.load_submission_files(id_)[0]) is None or not f.is_file():
        return Response(status_code=404)
    return FileResponse(f)


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
            return FileResponse(t)
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
        z.writestr("metadata.json", dumps({k: v for k, v in serialise_entry(sub).items()
                                           if k != "DESCRIPTION"}).encode())

    f_obj.seek(0)
    return StreamingResponse(f_obj, media_type="application/zip")


@app.get("/journal/{id_}/", response_class=HTMLResponse)
async def serve_journal(request: Request, id_: int):
    if (jrnl := settings.database.load_journal(id_)) is None:
        return error_response(request, 404, "Journal not found",
                              [("Open on Fur Affinity", f"{fa_base_url}/journal/{id_}")])

    p, n = settings.database.load_prev_next(journals_table, id_)
    return HTMLResponse(minify(templates.get_template("journal.html").render({
        "app": app.title,
        "title": f"{jrnl['TITLE']} by {jrnl['AUTHOR']}",
        "journal": jrnl | {"CONTENT": clean_html(jrnl["CONTENT"])},
        "prev": p,
        "next": n,
        "request": request}),
        remove_comments=True))


@app.get("/journal/{id_}/zip/")
@app.get("/journal/{id_}/zip/{filename}")
async def serve_journal_zip(id_: int, _filename=None):
    if (jrnl := settings.database.load_journal(id_)) is None:
        raise HTTPException(404)

    with ZipFile(f_obj := BytesIO(), "w") as z:
        z.writestr("content.html", jrnl["CONTENT"].encode())
        z.writestr("metadata.json", dumps({k: v for k, v in serialise_entry(jrnl).items()
                                           if k != "CONTENT"}).encode())

    f_obj.seek(0)
    return StreamingResponse(f_obj, media_type="application/zip")


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
        query_data.order
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


@app.get("/json/user/{username}/", response_class=JSONResponse)
@app.post("/json/user/{username}/", response_class=JSONResponse)
async def serve_user_json(username: str):
    username = clean_username(username)
    user_entry: dict | None = settings.database.load_user_uncached(username)
    user_stats: dict[str, int] = settings.database.load_user_stats_uncached(username)

    return {"username": username, **{k.lower(): v for k, v in (user_entry or {}).items()}, "length": user_stats}


def run_redirect(host: str, port_listen: int, port_redirect: int):
    redirect_app: FastAPI = FastAPI()
    redirect_app.add_event_handler("startup", lambda: logger.info(f"Redirecting target https://{host}:{port_redirect}"))
    redirect_app.add_route(
        "/{__:path}",
        lambda r, *_: RedirectResponse(f"https://{r.url.hostname}:{port_redirect}{r.url.path}?{r.url.query}"),
        ["GET"]
    )
    # noinspection PyTypeChecker
    run(redirect_app, host=host, port=port_listen)


def server(database_path: str | PathLike, host: str = "0.0.0.0", port: int = None,
           ssl_cert: str | PathLike | None = None, ssl_key: str | PathLike | None = None,
           redirect_port: int = None, precache: bool = False, authentication: str = None):
    if redirect_port:
        return run_redirect(host, port, redirect_port)
    settings.precache = precache
    if authentication:
        settings.username = authentication.split(":")[0]
        settings.password = authentication.split(":", 1)[1] if ":" in authentication else ""
        app.middleware("http")(auth_middleware)
    run_args: dict[str, Any] = {}
    if ssl_cert and ssl_key:
        settings.ssl_cert, settings.ssl_key = Path(ssl_cert), Path(ssl_key)
        if not settings.ssl_cert.is_file():
            raise FileNotFoundError(f"SSL certificate {settings.ssl_cert}")
        elif not settings.ssl_key.is_file():
            raise FileNotFoundError(f"SSL private key {settings.ssl_key}")
        run_args |= {"port": port or 443, "ssl_certfile": settings.ssl_cert, "ssl_keyfile": settings.ssl_key}
    run_args |= {"port": run_args.get("port", port) or 80}
    with Database(Path(database_path).resolve()) as settings.database:
        search_settings.load(settings.database.load_settings("SEARCH"))
        # noinspection PyTypeChecker
        run(app, host=host, **run_args)
