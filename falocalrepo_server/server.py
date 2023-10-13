from datetime import datetime
from datetime import timedelta
from datetime import timezone
from io import BytesIO
from json import dumps
from logging import Logger
from logging import getLogger
from math import ceil
from os import PathLike
from pathlib import Path
from re import IGNORECASE
from re import Pattern
from re import compile as re_compile
from re import match
from re import sub as re_sub
from secrets import compare_digest
from sqlite3 import DatabaseError
from sqlite3 import OperationalError
from typing import Any
from typing import Callable
from typing import Coroutine
from webbrowser import open as open_browser
from zipfile import ZipFile

from PIL import Image
from PIL import UnidentifiedImageError
from bbcode import Parser as BBCodeParser
from bs4 import BeautifulSoup
from bs4.element import NavigableString
from bs4.element import Tag
from chardet import detect as detect_encoding
from falocalrepo_database.tables import JournalsColumns
from falocalrepo_database.tables import SubmissionsColumns
from falocalrepo_database.tables import UsersColumns
from fastapi import FastAPI
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
from starlette.middleware.base import BaseHTTPMiddleware
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
    open_browser: bool = True
    address: str = None
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

app_title: str = "FurAffinity Local Repo"
fa_base_url: str = "https://www.furaffinity.net"
fa_link: Pattern = re_compile(r"(https?://)?(www.)?furaffinity.net", flags=IGNORECASE)
root: Path = Path(__file__).resolve().parent
app: FastAPI = FastAPI(title=app_title, openapi_url=None)
templates: Jinja2Templates = Jinja2Templates(str(root / "templates"))
settings: Settings = Settings(static_folder=root / "static")
search_settings: SearchSettings = SearchSettings()
security: HTTPBasic = HTTPBasic()

icons: list[str] = ["crying", "derp", "dunno", "embarrassed", "evil", "gift", "huh", "lmao", "love", "nerd", "note",
                    "oooh", "pleased", "rollingeyes", "sad", "sarcastic", "serious", "sleepy", "smile", "teeth",
                    "tongue", "veryhappy", "wink", "yelling", "zipped", "angel", "badhairday", "cd", "coffee", "cool",
                    "whatever"]

app.mount("/static", StaticFiles(directory=settings.static_folder), "static")


def flatten_comments(comments: list[dict]) -> list[dict]:
    return [*{c["ID"]: c for c in [r for c in comments for r in [c, *flatten_comments(c["REPLIES"])]]}.values()]


def comments_depth(comments: list[dict], depth: int = 0, root_comment: int = None) -> list[dict]:
    return [com | {"DEPTH": depth,
                   "REPLIES": comments_depth(com.get("REPLIES", []), depth + 1, root_comment or com["ID"]),
                   "ROOT": root_comment}
            for com in comments]


def prepare_comments(comments: list[dict], use_bbcode: bool) -> list[dict]:
    return [c | {"TEXT": bbcode_to_html(c["TEXT"]) if use_bbcode else clean_html(c["TEXT"])}
            for c in flatten_comments(comments_depth(comments, 0))]


def bbcode_to_html(bbcode: str) -> str:
    def render_url(_tag_name, value: str, options: dict[str, str], _parent, _context) -> str:
        return f'<a class="auto_link named_url" href="{options.get("url", "#")}">{value}</a>'

    def render_color(_tag_name, value, options, _parent, _context) -> str:
        return f'<span class=bbcode style="color:{options.get("color", "inherit")};">{value}</span>'

    def render_quote(_tag_name, value: str, options: dict[str, str], _parent, _context) -> str:
        author: str = options.get("quote", "")
        author = f"<span class=bbcode_quote_name>{author} wrote:</span>" if author else ""
        return f'<span class="bbcode bbcode_quote">{author}{value}</span>'

    def render_tags(tag_name: str, value: str, options: dict[str, str], _parent, _context) -> str:
        if not options and tag_name.islower():
            return f"<{tag_name}>{value}</{tag_name}>"
        return f"[{tag_name} {' '.join(f'{k}={v}' if v else k for k, v in options.items())}]{value}"

    def render_tag(_tag_name, value: str, options: dict[str, str], _parent, _context) -> str:
        name, *classes = options["tag"].split(".")
        return f'<{name} class="{" ".join(classes)}">{value}</{name}>'

    def parse_extra(page: BeautifulSoup) -> BeautifulSoup:
        child: NavigableString
        child_new: Tag
        has_match: bool = True
        while has_match:
            has_match = False
            for child in [c for e in page.select("*:not(a)") for c in e.children if isinstance(c, NavigableString)]:
                if m_ := match(r"(.*)(https?://(?:www\.)?((?:[\w/%#\[\]@*-]|[.,?!'()&~:;=](?! ))+))(.*)", child):
                    has_match = True
                    child_new = Tag(name="a", attrs={"class": f"auto_link_shortened", "href": m_[2]})
                    child_new.insert(0, m_[3].split("?", 1)[0])
                    child.replaceWith(m_[1], child_new, m_[4])
                elif m_ := match(rf"(.*):({'|'.join(icons)}):(.*)", child):
                    has_match = True
                    child_new = Tag(name="i", attrs={"class": f"smilie {m_[2]}"})
                    child.replaceWith(m_[1], child_new, m_[3])
                elif m_ := match(r"(.*)(?:@([a-zA-Z0-9.~_-]+)|:link([a-zA-Z0-9.~_-]+):)(.*)", child):
                    has_match = True
                    child_new = Tag(name="a", attrs={"class": "linkusername", "href": f"/user/{m_[2] or m_[3]}"})
                    child_new.insert(0, m_[2] or m_[3])
                    child.replaceWith(m_[1], child_new, m_[4])
                elif m_ := match(r"(.*):(?:icon([a-zA-Z0-9.~_-]+)|([a-zA-Z0-9.~_-]+)icon):(.*)", child):
                    has_match = True
                    user: str = m_[2] or m_[3] or ""
                    child_new = Tag(name="a", attrs={"class": "iconusername", "href": f"/user/{user}"})
                    child_new_img: Tag = Tag(
                        name="img",
                        attrs={"alt": user, "title": user,
                               "src": f"/user/{clean_username(user)}/icon"})
                    child_new.insert(0, child_new_img)
                    if m_[2]:
                        child_new.insert(1, f"\xA0{m_[2]}")
                    child.replaceWith(m_[1], child_new, m_[4])
                elif m_ := match(r"(.*)\[ *(?:(\d+)|-)?, *(?:(\d+)|-)? *, *(?:(\d+)|-)? *](.*)", child):
                    has_match = True
                    child_new = Tag(name="span", attrs={"class": "parsed_nav_links"})
                    child_new_1: Tag | str = "<<<\xA0PREV"
                    child_new_2: Tag | str = "FIRST"
                    child_new_3: Tag | str = "NEXT\xA0>>>"
                    if m_[2]:
                        child_new_1 = Tag(name="a", attrs={"href": f"/view/{m_[2]}"})
                        child_new_1.insert(0, "<<<\xA0PREV")
                    if m_[3]:
                        child_new_2 = Tag(name="a", attrs={"href": f"/view/{m_[3]}"})
                        child_new_2.insert(0, "<<<\xA0FIRST")
                    if m_[4]:
                        child_new_3 = Tag(name="a", attrs={"href": f"/view/{m_[4]}"})
                        child_new_3.insert(0, "NEXT\xA0>>>")
                    child_new.insert(0, child_new_1)
                    child_new.insert(1, "\xA0|\xA0")
                    child_new.insert(2, child_new_2)
                    child_new.insert(3, "\xA0|\xA0")
                    child_new.insert(4, child_new_3)
                    child.replaceWith(m_[1], child_new, m_[5])

        for p in page.select("p"):
            p.replaceWith(*p.children)

        return page

    parser: BBCodeParser = BBCodeParser(install_defaults=False, replace_links=False, replace_cosmetic=True)
    parser.REPLACE_ESCAPE = (
        ("&", "&amp;"),
        ("<", "&lt;"),
        (">", "&gt;"),
    )
    parser.REPLACE_COSMETIC = (
        ("(c)", "&copy;"),
        ("(r)", "&reg;"),
        ("(tm)", "&trade;"),
    )

    for tag in ("i", "b", "u", "s", "sub", "sup", "h1", "h2", "h3", "h3", "h4", "h5", "h6"):
        parser.add_formatter(tag, render_tags)
    for align in ("left", "center", "right"):
        parser.add_simple_formatter(align, f'<code class="bbcode bbcode_{align}">%(value)s</code>')

    parser.add_simple_formatter("spoiler", '<span class="bbcode bbcode_spoiler">%(value)s</span>')
    parser.add_simple_formatter("url", '<a class="auto_link named_link">%(value)s</a>')
    parser.add_simple_formatter(
        "iconusername",
        f'<a class=iconusername href="/user/%(value)s">'
        f'<img alt="%(value)s" title="%(value)s" src="/user/%(value)s/icon">'
        f'%(value)s'
        f'</a>'
    )
    parser.add_simple_formatter(
        "usernameicon",
        f'<a class=iconusername href="/user/%(value)s">'
        f'<img alt="%(value)s" title="%(value)s" src="/user/%(value)s/icon">'
        f'</a>'
    )
    parser.add_simple_formatter("linkusername", '<a class=linkusername href="/user/%(value)s">%(value)s</a>')
    parser.add_simple_formatter("hr", "<hr>", standalone=True)

    parser.add_formatter("url", render_url)
    parser.add_formatter("color", render_color)
    parser.add_formatter("quote", render_quote)
    parser.add_formatter("tag", render_tag)

    bbcode = re_sub(r"-{5,}", "[hr]", bbcode)

    result_page: BeautifulSoup = parse_extra(BeautifulSoup(parser.format(bbcode), "lxml"))
    return (result_page.select_one("html > body") or result_page).decode_contents()


def clean_html(html: str) -> str:
    html_parsed: BeautifulSoup = BeautifulSoup(html, "lxml")
    for icon in html_parsed.select("a.iconusername > img"):
        icon.attrs["hidden"] = "true"
        icon.attrs["onload"] = "this.hidden = false"
        icon.attrs["src"] = f"/user/{clean_username(icon.attrs['title'])}/icon/"
    for link in html_parsed.select("a[href*='furaffinity.net']"):
        link["href"] = "/" + fa_link.sub("", link.attrs["href"]).strip("/")
    return str(html_parsed)


def prepare_html(html: str, use_bbcode: bool) -> str:
    return clean_html(bbcode_to_html(html)) if use_bbcode else clean_html(html)


def serialise_entry(entry: Any, convert_datetime: bool = False, lowercase_keys: bool = True) -> Any:
    if isinstance(entry, dict):
        return {(k.lower() if lowercase_keys else k): serialise_entry(v, convert_datetime, lowercase_keys)
                for k, v in entry.items()}
    elif isinstance(entry, (list, tuple)):
        return [serialise_entry(e, convert_datetime, lowercase_keys) for e in entry]
    elif isinstance(entry, set):
        return sorted((serialise_entry(e, convert_datetime, lowercase_keys) for e in entry))
    elif isinstance(entry, datetime) and convert_datetime:
        return str(entry)
    else:
        return entry


def error_response(request: Request, code: int, message: str = None, buttons: list[tuple[str, str]] = None) -> Response:
    return templates.TemplateResponse(
        "error.html",
        {"app": app_title,
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
def app_startup():
    logger.info(f"Version: {__version__}")
    logger.info(f"Using database: {settings.database.path} ({settings.database.version})" +
                (" (BBCode)" if settings.database.use_bbcode() else ""))
    logger.info(f"Using SSL certificate: {settings.ssl_cert}") if settings.ssl_cert else None
    logger.info(f"Using SSL private key: {settings.ssl_key}") if settings.ssl_key else None
    logger.info(f"Using HTTP Basic authentication") if settings.username or settings.password else None
    settings.database.clear_cache(settings.database.m_time)
    if settings.precache:
        for table, order in [
            (t, o)
            for t in (settings.database.users, settings.database.submissions, settings.database.journals)
            for o in ("asc", "desc")
        ]:
            logger.info("Caching " + f"{table.name}:{(sort := search_settings.sort[table.name])}:{order}".upper())
            settings.database.load_search(table.name, "", "id" if sort.lower() == "date" else sort, order)
    if settings.open_browser:
        open_browser(settings.address)


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
                              {"query": f'@author ^{clean_username(username)}$ @folder "gallery"'})


@app.get("/scraps/{username}/", response_class=HTMLResponse)
@app.get("/search/scraps/{username}/", response_class=HTMLResponse)
async def serve_user_scraps(request: Request, username: str):
    return await serve_search(request, "submissions", f"Scraps {username}",
                              {"query": f'@author ^{clean_username(username)}$ @folder "scraps"'})


@app.get("/submissions/{username}/", response_class=HTMLResponse)
@app.get("/search/submissions/{username}/", response_class=HTMLResponse)
async def serve_user_submissions(request: Request, username: str):
    return await serve_search(request, "submissions", f"Submissions {username}",
                              {"query": f'@author ^{clean_username(username)}$'})


@app.get("/journals/{username}/", response_class=HTMLResponse)
@app.get("/search/journals/{username}/", response_class=HTMLResponse)
async def serve_user_journals(request: Request, username: str):
    return await serve_search(request, "journals", f"Journals {username}",
                              {"query": f'@author ^{clean_username(username)}$'})


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


@app.get("/search/")
async def server_search_default(request: Request):
    return RedirectResponse(app.url_path_for(serve_search.__name__, table=submissions_table.lower()) +
                            "?" + request.url.query,
                            status.HTTP_301_MOVED_PERMANENTLY)


@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    usr_n, sub_n, jrn_n, version = settings.database.load_info()
    hist = settings.database.history.select(order=[f"{settings.database.history.key.name} DESC"])
    return HTMLResponse(minify(templates.get_template("info.html").render({
        "app": app_title,
        "title": "",
        "submissions_total": sub_n,
        "journals_total": jrn_n,
        "users_total": usr_n,
        "version_db": version,
        "version": __version__,
        "m_time": next(hist.tuples, [datetime.fromtimestamp(settings.database.m_time)])[0],
        "request": request}),
        remove_comments=True))


@app.get("/settings/")
async def serve_settings(request: Request):
    return HTMLResponse(minify(templates.get_template("settings.html").render({
        "version": __version__,
        "app": app_title,
        "title": "Search Settings",
        "tables": [users_table, submissions_table, journals_table],
        "columns": {users_table: [c.name for c in UsersColumns.as_list()],
                    submissions_table: [c.name for c in SubmissionsColumns.as_list()] + ["relevance"],
                    journals_table: [c.name for c in JournalsColumns.as_list()]},
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

    user_entry: dict = settings.database.load_user(username) or {}
    user_stats: dict[str, int] = settings.database.load_user_stats(username)
    p, n = settings.database.load_prev_next(users_table, username) if user_entry else (0, 0)

    return HTMLResponse(minify(templates.get_template("user.html").render({
        "version": __version__,
        "app": app_title,
        "title": username,
        "user": username,
        "folders": user_entry.get("FOLDERS", []),
        "active": user_entry.get("ACTIVE", True),
        "gallery_length": user_stats["gallery"],
        "scraps_length": user_stats["scraps"],
        "favorites_length": user_stats["favorites"],
        "mentions_length": user_stats["mentions"],
        "journals_length": user_stats["journals"],
        "userpage": prepare_html(user_entry.get("USERPAGE", ""), settings.database.use_bbcode()),
        "userpage_bbcode": user_entry.get("USERPAGE", None) if settings.database.use_bbcode() else None,
        "icon": f"/user/{username}/icon",
        "in_database": bool(user_entry),
        "prev": p,
        "next": n,
        "request": request}),
        remove_comments=True))


@app.get("/user/{username}/icon/")
@app.get("/user/{username}/thumbnail/")
async def serve_user_thumbnail(username: str):
    if username != (username_clean := clean_username(username)):
        return RedirectResponse(app.url_path_for(serve_user_thumbnail.__name__, username=username_clean))

    server_time: datetime = datetime.now(timezone(timedelta(hours=-8)))
    return RedirectResponse(f"https://a.furaffinity.net/{server_time:%Y%m%d}/{username}.gif")


@app.get("/search/{table}/", response_class=HTMLResponse)
async def serve_search(request: Request, table: str, title: str = None, args: dict[str, str] = None):
    if (table := table.upper()) not in (submissions_table, journals_table, users_table):
        raise HTTPException(404, f"Table {table.lower()} not found.")

    args = {k.lower(): v for k, v in (args or {}).items()}
    args_req = {k.lower(): v for k, v in request.query_params.items()}
    query: str = " & ".join([f"({q})" for args_ in (args_req, args) if (q := args_.get("query", args_.get("q", None)))])
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

    results, columns_table, columns_results, columns_list, column_id, _, order = settings.database.load_search(
        table,
        query.lower().strip(),
        "id" if sort == "date" else sort,
        order
    )

    if (page - 1) * limit > len(results):
        page = ceil(len(results) / limit) or 1

    return HTMLResponse(minify(templates.get_template("search.html").render({
        "version": __version__,
        "app": app_title,
        "title": title or f"Search {table.title()}",
        "action": request.url.path,
        "table": table.lower(),
        "query": args_req.get("query", args_req.get("q", "")),
        "sort": sort,
        "order": order,
        "view": view,
        "thumbnails": table in (submissions_table, users_table),
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

    fs: list[Path] | None = None
    if "txt" in sub["FILEEXT"] and sub["FILESAVED"] & 0b10:
        fs, _ = settings.database.load_submission_files(id_)
    p, n = settings.database.load_prev_next(submissions_table, id_)
    return HTMLResponse(minify(templates.get_template("submission.html").render({
        "version": __version__,
        "app": app_title,
        "title": f"{sub['TITLE']} by {sub['AUTHOR']}",
        "submission": sub | {
            "DESCRIPTION": prepare_html(sub["DESCRIPTION"], settings.database.use_bbcode()),
            "FOOTER": prepare_html(sub["FOOTER"], settings.database.use_bbcode()),
            "DESCRIPTION_BBCODE": sub["DESCRIPTION"].strip() or None if settings.database.use_bbcode() else None,
            "FOOTER_BBCODE": sub["FOOTER"].strip() or None if settings.database.use_bbcode() else None,
        },
        "files_text": [
            bbcode_to_html(fs[i].read_text(detect_encoding(fs[i].read_bytes())["encoding"], "ignore"))
            if ext.lower() == "txt" else ""
            for i, ext in enumerate(sub['FILEEXT']) if fs[i].is_file()] if fs else [],
        "filenames": [f"submission{('.' + ext) * bool(ext)}" for ext in sub['FILEEXT']],
        "filenames_id": [f"{sub['ID']:010d}{('.' + ext) * bool(ext)}" for ext in sub['FILEEXT']],
        "comments": prepare_comments(settings.database.load_submission_comments(id_), settings.database.use_bbcode()),
        "prev": p,
        "next": n,
        "request": request}),
        remove_comments=True))


@app.get("/submission/{id_}/file/")
@app.get("/submission/{id_}/file/{n}")
@app.get("/submission/{id_}/file/{n}/{_filename}")
async def serve_submission_file(id_: int, n: int = 0, _filename=None):
    if (fs := settings.database.load_submission_files(id_)[0]) is None or not fs[n].is_file():
        return Response(status_code=404)
    return FileResponse(fs[n])


@app.get("/submission/{id_}/files/")
@app.get("/submission/{id_}/files/{_filename}")
@app.get("/submission/{id_}/files/{n1}-{n2}")
@app.get("/submission/{id_}/files/{n1}-{n2}/{_filename}")
async def serve_submission_zip(id_: int, n1: int = 0, n2: int = None, _filename=None):
    if id_ not in settings.database.submissions:
        raise HTTPException(404)

    sub_files, _ = settings.database.load_submission_files(id_)

    with ZipFile(f_obj := BytesIO(), "w") as z:
        for sub_file in sub_files[n1:(n2 + 1) if n2 is not None else None]:
            z.writestr(sub_file.name, sub_file.read_bytes())

    f_obj.seek(0)
    return StreamingResponse(f_obj, media_type="application/zip")


@app.get("/submission/{id_}/thumbnail/")
@app.get("/submission/{id_}/thumbnail/{_filename}")
@app.get("/submission/{id_}/thumbnail/{x}x/")
@app.get("/submission/{id_}/thumbnail/{x}x/{_filename}")
@app.get("/submission/{id_}/thumbnail/x{y}/")
@app.get("/submission/{id_}/thumbnail/x{y}/{_filename}")
@app.get("/submission/{id_}/thumbnail/{x}x{y}>/")
@app.get("/submission/{id_}/thumbnail/{x}x{y}>/{_filename}")
async def serve_submission_thumbnail(id_: int, x: int = None, y: int = None, _filename=None):
    fs, t = settings.database.load_submission_files(id_)
    if t is not None and t.is_file():
        if not x and not y:
            return FileResponse(t)
        with Image.open(t) as img:
            img.thumbnail((x or y, y or x))
            img.save(f_obj := BytesIO(), img.format, quality=95)
            f_obj.seek(0)
            return StreamingResponse(f_obj, 201, media_type=f"image/{img.format}".lower())
    elif fs and fs[0].is_file():
        try:
            with Image.open(fs[0]) as img:
                img.thumbnail((x or y or 400, y or x or 400))
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

    sub_files, sub_thumb = settings.database.load_submission_files(id_)

    with ZipFile(f_obj := BytesIO(), "w") as z:
        for sub_file in sub_files:
            z.writestr(sub_file.name, sub_file.read_bytes())
        z.writestr(sub_thumb.name, sub_thumb.read_bytes()) if sub_thumb else None
        z.writestr("description.txt" if settings.database.use_bbcode() else "description.html",
                   sub["DESCRIPTION"].encode())
        z.writestr("metadata.json", dumps({k: v for k, v in serialise_entry(sub, convert_datetime=True).items()
                                           if k != "description"}).encode())
        z.writestr("comments.json", dumps([serialise_entry(c, convert_datetime=True)
                                           for c in settings.database.load_submission_comments(id_)]).encode())

    f_obj.seek(0)
    return StreamingResponse(f_obj, media_type="application/zip")


@app.get("/journal/{id_}/", response_class=HTMLResponse)
async def serve_journal(request: Request, id_: int):
    if (jrnl := settings.database.load_journal(id_)) is None:
        return error_response(request, 404, "Journal not found",
                              [("Open on Fur Affinity", f"{fa_base_url}/journal/{id_}")])

    p, n = settings.database.load_prev_next(journals_table, id_)
    return HTMLResponse(minify(templates.get_template("journal.html").render({
        "version": __version__,
        "app": app_title,
        "title": f"{jrnl['TITLE']} by {jrnl['AUTHOR']}",
        "journal": jrnl | {
            "CONTENT": prepare_html(jrnl["CONTENT"], settings.database.use_bbcode()),
            "HEADER": prepare_html(jrnl["HEADER"], settings.database.use_bbcode()),
            "FOOTER": prepare_html(jrnl["FOOTER"], settings.database.use_bbcode()),
            "CONTENT_BBCODE": jrnl["CONTENT"].strip() or None if settings.database.use_bbcode() else None,
            "HEADER_BBCODE": jrnl["HEADER"].strip() or None if settings.database.use_bbcode() else None,
            "FOOTER_BBCODE": jrnl["FOOTER"].strip() or None if settings.database.use_bbcode() else None,
        },
        "comments": prepare_comments(settings.database.load_journal_comments(id_), settings.database.use_bbcode()),
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
        z.writestr("content.txt" if settings.database.use_bbcode() else "content.html", jrnl["CONTENT"].encode())
        z.writestr("metadata.json", dumps({k: v for k, v in serialise_entry(jrnl, convert_datetime=True).items()
                                           if k != "content"}).encode())
        z.writestr("comments.json", dumps([serialise_entry(c, convert_datetime=True)
                                           for c in settings.database.load_journal_comments(id_)]).encode())

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
            "results": serialise_entry(results[query_data.offset:query_data.offset + query_data.limit]),
            "results_total": len(results)}


@app.get("/json/submission/{id_}/", response_class=JSONResponse)
@app.post("/json/submission/{id_}/", response_class=JSONResponse)
async def serve_submission_json(id_: int):
    if not (s := settings.database.load_submission_uncached(id_)):
        raise HTTPException(404)
    else:
        return serialise_entry(s | {"comments": settings.database.load_submission_comments_uncached(id_)})


@app.get("/json/journal/{id_}/", response_class=JSONResponse)
@app.post("/json/journal/{id_}/", response_class=JSONResponse)
async def serve_journal_json(id_: int):
    if not (j := settings.database.load_journal_uncached(id_)):
        raise HTTPException(404)
    else:
        return serialise_entry(j | {"comments": settings.database.load_journal_comments_uncached(id_)})


@app.get("/json/user/{username}/", response_class=JSONResponse)
@app.post("/json/user/{username}/", response_class=JSONResponse)
async def serve_user_json(username: str):
    username = clean_username(username)
    user_entry: dict = settings.database.load_user_uncached(username) or {}
    user_stats: dict[str, int] = settings.database.load_user_stats_uncached(username)

    return serialise_entry({"username": username, "length": user_stats} | user_entry)


def run_redirect(host: str, port_listen: int, port_redirect: int):
    redirect_app: FastAPI = FastAPI()
    redirect_app.add_event_handler("startup", lambda: logger.info(f"Redirecting target https://{host}:{port_redirect}"))
    redirect_app.add_route(
        "/{__:path}",
        lambda r, *_: RedirectResponse(f"https://{r.url.hostname}:{port_redirect}{r.url.path}?{r.url.query}"),
        ["GET"]
    )
    run(redirect_app, host=host, port=port_listen, log_config=LOGGING_CONFIG)


def server(database_path: str | PathLike, host: str = "0.0.0.0", port: int = None,
           ssl_cert: str | PathLike | None = None, ssl_key: str | PathLike | None = None,
           redirect_port: int = None, precache: bool = False, authentication: str = None,
           browser: bool = True):
    if redirect_port:
        return run_redirect(host, port, redirect_port)

    settings.precache = precache
    settings.open_browser = browser

    if authentication:
        settings.username = authentication.split(":")[0]
        settings.password = authentication.split(":", 1)[1] if ":" in authentication else ""
        app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)

    if ssl_cert and ssl_key:
        settings.ssl_cert, settings.ssl_key = Path(ssl_cert), Path(ssl_key)
        if not settings.ssl_cert.is_file():
            raise FileNotFoundError(f"SSL certificate {settings.ssl_cert}")
        elif not settings.ssl_key.is_file():
            raise FileNotFoundError(f"SSL private key {settings.ssl_key}")
        port = port or 443

    settings.address = f"{'https' if settings.ssl_cert else 'http'}://" \
                       f"{'localhost' if host == '0.0.0.0' else host}" \
                       f"{f':{port}' if port else ''}"

    with Database(Path(database_path).resolve(), logger) as settings.database:
        search_settings.load(settings.database.load_settings("SEARCH"))
        run(app, host=host, port=port,
            ssl_certfile=settings.ssl_cert,
            ssl_keyfile=str(settings.ssl_key) if settings.ssl_key else None,
            log_config=LOGGING_CONFIG)
