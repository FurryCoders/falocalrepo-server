from base64 import b64decode
from base64 import b64encode
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from functools import reduce
from hashlib import sha256
from io import BytesIO
from logging import getLogger
from logging import Logger
from math import ceil
from os import PathLike
from pathlib import Path
from re import compile as re_compile
from re import IGNORECASE
from re import match
from re import MULTILINE
from re import Pattern
from re import sub as re_sub
from secrets import compare_digest
from traceback import format_exc
from typing import Any
from typing import Mapping
from webbrowser import open as open_browser
from zipfile import ZipFile
from shutil import copy2

from baize.asgi import FileResponse
from bs4 import BeautifulSoup
from chardet import detect as detect_encoding

# noinspection PyProtectedMember
from falocalrepo_database import __package__ as __package_database__
from falocalrepo_database import __version__ as __version_database__
from falocalrepo_database.tables import comments_table
from orjson import dumps
from orjson import loads
from PIL import Image
from PIL import UnidentifiedImageError
from starlette import status
from starlette.applications import Starlette
from starlette.authentication import AuthCredentials
from starlette.authentication import AuthenticationBackend
from starlette.authentication import AuthenticationError
from starlette.authentication import requires
from starlette.authentication import SimpleUser
from starlette.background import BackgroundTask
from starlette.convertors import register_url_convertor
from starlette.convertors import StringConvertor
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import HTTPConnection
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.responses import RedirectResponse
from starlette.responses import Response
from starlette.responses import StreamingResponse
from starlette.routing import BaseRoute
from starlette.routing import Mount
from starlette.routing import Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.types import ExceptionHandler
from uvicorn import run

from .__version__ import __version__
from .database import clean_username
from .database import Database
from .database import default_order
from .database import default_sort
from .database import journals_table
from .database import Settings
from .database import submissions_table
from .database import users_table

default_search_settings: Settings = {
    "view": {users_table: "grid", submissions_table: "grid", journals_table: "list", comments_table: "list"},
    "limit": {users_table: 48, submissions_table: 48, journals_table: 48, comments_table: 48},
    "sort": default_sort,
    "order": default_order,
}
mobile_user_agent_pattern_a = re_compile(
    r"(android|bb\\d+|meego).+mobile|avantgo|bada\\/|blackberry|blazer|compal|elaine|fennec|hiptop|iemobile|"
    r"ip(hone|od)|iris|kindle|lge |maemo|midp|mmp|mobile.+firefox|netfront|opera m(ob|in)i|palm( os)?|phone|p(ixi|re)"
    r"\\/|plucker|pocket|psp|series([46])0|symbian|treo|up\\.(browser|link)|vodafone|wap|windows ce|xda|xiino",
    IGNORECASE | MULTILINE,
)
mobile_user_agent_pattern_b = re_compile(
    r"1207|6310|6590|3gso|4thp|50[1-6]i|770s|802s|a wa|abac|ac(er|oo|s\\-)|ai(ko|rn)|al(av|ca|co)|amoi|an(ex|ny|yw)"
    r"|aptu|ar(ch|go)|as(te|us)|attw|au(di|\\-m|r |s )|avan|be(ck|ll|nq)|bi(lb|rd)|bl(ac|az)|br([ev])w|bumb|bw\\-([nu])"
    r"|c55\\/|capi|ccwa|cdm\\-|cell|chtm|cldc|cmd\\-|co(mp|nd)|craw|da(it|ll|ng)|dbte|dc\\-s|devi|dica|dmob|do([cp])o|"
    r"ds(12|\\-d)|el(49|ai)|em(l2|ul)|er(ic|k0)|esl8|ez([4-7]0|os|wa|ze)|fetc|fly(\\-|_)|g1 u|g560|gene|gf\\-5|g\\-mo"
    r"|go(\\.w|od)|gr(ad|un)|haie|hcit|hd\\-([mpt])|hei\\-|hi(pt|ta)|hp( i|ip)|hs\\-c|ht(c(\\-| |_|a|g|p|s|t)|tp)|"
    r"hu(aw|tc)|i\\-(20|go|ma)|i230|iac( |\\-|\\/)|ibro|idea|ig01|ikom|im1k|inno|ipaq|iris|ja([tv])a|jbro|jemu|jigs|"
    r"kddi|keji|kgt( |\\/)|klon|kpt |kwc\\-|kyo([ck])|le(no|xi)|lg( g|\\/([klu])|50|54|\\-[a-w])|libw|lynx|m1\\-w|m3ga|"
    r"m50\\/|ma(te|ui|xo)|mc(01|21|ca)|m\\-cr|me(rc|ri)|mi(o8|oa|ts)|mmef|mo(01|02|bi|de|do|t(\\-| |o|v)|zz)|"
    r"mt(50|p1|v )|mwbp|mywa|n10[0-2]|n20[2-3]|n30([02])|n50([025])|n7(0([01])|10)|ne(([cm])\\-|on|tf|wf|wg|wt)|"
    r"nok([6i])|nzph|o2im|op(ti|wv)|oran|owg1|p800|pan([adt])|pdxg|pg(13|\\-([1-8]|c))|phil|pire|pl(ay|uc)|pn\\-2|"
    r"po(ck|rt|se)|prox|psio|pt\\-g|qa\\-a|qc(07|12|21|32|60|\\-[2-7]|i\\-)|qtek|r380|r600|raks|rim9|ro(ve|zo)|s55\\/|"
    r"sa(ge|ma|mm|ms|ny|va)|sc(01|h\\-|oo|p\\-)|sdk\\/|se(c(\\-|0|1)|47|mc|nd|ri)|sgh\\-|shar|sie(\\-|m)|sk\\-0|"
    r"sl(45|id)|sm(al|ar|b3|it|t5)|so(ft|ny)|sp(01|h\\-|v\\-|v )|sy(01|mb)|t2(18|50)|t6(00|10|18)|ta(gt|lk)|tcl\\-|"
    r"tdg\\-|tel([im])|tim\\-|t\\-mo|to(pl|sh)|ts(70|m\\-|m3|m5)|tx\\-9|up(\\.b|g1|si)|utst|v400|v750|veri|vi(rg|te)|"
    r"vk(40|5[0-3]|\\-v)|vm40|voda|vulc|vx(52|53|60|61|70|80|81|83|85|98)|w3c(\\-| )|webc|whit|wi(g |nc|nw)|wmlb|wonu|"
    r"x700|yas\\-|your|zeto|zte\\-",
    IGNORECASE | MULTILINE,
)
logger: Logger = getLogger("uvicorn")
root: Path = Path(__file__).resolve().parent
templates: Jinja2Templates = Jinja2Templates(
    str(root / "templates"),
    context_processors=[
        lambda r: {
            "version": __version__,
            "is_mobile": is_request_mobile(r),
        },
    ],
)
templates.env.filters["clean_broken_tags"] = lambda text: re_sub(r"<[^>]*$", "", text)
templates.env.filters["prettify_html"] = lambda text: (
    (b := BeautifulSoup(text, "lxml")).select_one("body") or b
).decode_contents()


def is_request_mobile(request: Request) -> bool | None:
    user_agent: str | None = request.headers.get("user-agent")
    return (
        None
        if not user_agent
        else bool(mobile_user_agent_pattern_a.search(user_agent) or mobile_user_agent_pattern_b.search(user_agent[:4]))
    )


class TemplateResponse(HTMLResponse):
    def __init__(
        self,
        request: Request,
        template_name: str,
        context: dict[str, Any],
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
        background: BackgroundTask | None = None,
    ):
        context |= reduce(lambda c, p: c | p(request), templates.context_processors, {}) | {"request": request}
        content: str = templates.get_template(template_name).render(context)
        super().__init__(content, status_code, headers, media_type, background)


class CacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.database.clear_cache()
        return await call_next(request)


class NoAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn: HTTPConnection):
        return AuthCredentials(["authenticated", "editor"]), SimpleUser("")


class BasicAuthBackend(AuthenticationBackend):
    def __init__(
        self,
        auth: tuple[tuple[str, str], ...],
        allowed_ips: tuple[str, ...] | None,
        editors: tuple[str, ...] | None,
    ):
        self.auth: dict[str, str] = dict(auth)
        self.allowed_ips: list[Pattern] = [
            re_compile(ip.replace(".", r"\.").replace("*", r".*")) for ip in allowed_ips or []
        ]
        self.editors: tuple[str, ...] | None = editors
        super().__init__()

    @staticmethod
    def on_auth_error(_req: Request, exc: Exception):
        return Response(
            ". ".join(map(str, exc.args)),
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Basic"},
        )

    async def authenticate(self, conn: HTTPConnection):
        if any(ip.match(conn.client.host) for ip in self.allowed_ips):
            return AuthCredentials(["authenticated", "editor", "whitelist"]), SimpleUser("")

        if conn.session.pop("logout", None):
            conn.session.pop("auth", None)
            raise AuthenticationError("Logged out")
        elif not (auth := conn.headers.get("Authorization", conn.session.get("auth"))):
            raise AuthenticationError("Missing credentials")

        try:
            scheme, credentials = auth.split()
            if scheme.lower() != "basic":
                return
            decoded = b64decode(credentials).decode("ascii")
        except Exception:
            raise AuthenticationError("Invalid basic auth credentials")

        username, _, password = decoded.partition(":")

        if username in self.auth and compare_digest(password, self.auth[username]):
            conn.session.update(auth=auth)
            credentials = AuthCredentials(["authenticated"])
            if username in self.editors:
                credentials.scopes.append("editor")
            return credentials, SimpleUser(username)

        conn.session.pop("auth", None)
        raise AuthenticationError("Invalid basic auth credentials")


class TableConvertor(StringConvertor):
    regex = f"({'|'.join([users_table, submissions_table, journals_table, comments_table])})".lower()


def merge_settings(a: Settings, b: dict[str, dict[str, str | int]]) -> Settings:
    return {
        "view": a["view"] | b.get("view", {}),
        "limit": a["limit"] | b.get("limit", {}),
        "sort": a["sort"] | b.get("sort", {}),
        "order": a["order"] | b.get("order", {}),
    }


def is_mobile(request: Request):
    user_agent: str | None = request.headers.get("user-agent")
    if not user_agent:
        request.state.is_mobile = None
    request.state.is_mobile = (
        mobile_user_agent_pattern_a.search(user_agent) or mobile_user_agent_pattern_b.search(user_agent[:4]),
    )


def encode_search_id(table_name: str, query: str, sort: str, order: str) -> str:
    return b64encode(dumps([table_name, query, sort, order])).decode()


def decode_search_id(encoded_search_id: str) -> tuple[str | None, tuple[str, str, str, str] | None, int | None]:
    search_terms: tuple[str, str, str, str] | None
    search_id: str | None
    search_index: int | None = None

    # noinspection PyBroadException
    try:
        search_index_, sep, search_id = encoded_search_id.partition(".")

        if sep and search_index_:
            search_index = int(search_index_)
        elif not sep and search_index_:
            search_id = search_index_

        t, q, s, o = loads(b64decode(search_id))
        assert isinstance(t, str)
        assert isinstance(q, str)
        assert isinstance(s, str)
        assert isinstance(o, str)
        search_terms = (t, q, s, o)
    except BaseException:
        return None, None, None

    return search_id, search_terms, search_index


def make_lifespan(
    database_path: Path,
    use_cache: bool,
    max_results: int | None,
    address: str,
    ssl: bool,
    authentication: bool,
    browser: bool,
):
    @asynccontextmanager
    async def _lifespan(_app: Starlette):
        logger.info(f"Using {__package__.replace('_', '-')}: {__version__}")
        logger.info(f"Using {__package_database__.replace('_', '-')}: {__version_database__}")
        with Database(database_path, use_cache, max_results) as database:
            logger.info(
                f"Using database: {database_path} ({database.database.version})"
                + (" (cache)" if use_cache else "")
                + (" (BBCode)" if database.database.settings.bbcode else "")
            )
            if ssl:
                logger.info("Using HTTPS")
            if authentication:
                logger.info("Using HTTP Basic authentication")
            if browser:
                open_browser(address)
            yield {"database": database, "authentication": bool(authentication)}

    return _lifespan


@requires(["authenticated"], redirect="/")
async def logout(request: Request):
    request.session["logout"] = True
    return RedirectResponse("/")


@requires(["authenticated"])
async def home(request: Request):
    database: Database = request.state.database
    stats = database.stats()
    return TemplateResponse(
        request,
        "pages/home.j2",
        {
            "users_total": stats[0],
            "submissions_total": stats[1],
            "journals_total": stats[2],
            "comments_total": stats[3],
            "last_update": stats[4] or datetime.fromtimestamp(database.path.stat().st_mtime),
        },
    )


# noinspection PyTypedDict
@requires(["authenticated"])
async def settings(request: Request):
    database: Database = request.state.database
    search_settings: Settings = merge_settings(default_search_settings, database.settings() or {})
    tables: dict[str, list[str]] = {
        users_table: [c.name for c in database.database.users.columns],
        submissions_table: [c.name for c in database.database.submissions.columns],
        journals_table: [c.name for c in database.database.journals.columns],
        comments_table: [c.name for c in database.database.comments.columns],
    }

    if request.method == "POST":
        form = await request.form()
        new_settings = deepcopy(search_settings)
        new_settings = merge_settings(new_settings, {"view": {journals_table: "list", comments_table: "list"}})

        for key, value in form.items():
            setting, _, table = key.partition(".")
            if setting in search_settings and table in search_settings.get(setting):
                new_settings[setting][table] = type(default_search_settings[setting][table])(value)
        if new_settings != search_settings:
            database.save_settings(new_settings)
            search_settings = new_settings

    search_settings = merge_settings(search_settings, {"view": {journals_table: "list", comments_table: "list"}})

    return TemplateResponse(request, "pages/settings.j2", {"settings": search_settings, "tables": tables})


async def search_response(
    request: Request, table_name: str, query_prefix: str = "", title: str = "", username: str = ""
):
    if (table_name := table_name.upper()) not in (
        users_table,
        submissions_table,
        journals_table,
        comments_table,
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Table {table_name!r} not found.")

    database: Database = request.state.database
    search_settings: Settings = merge_settings(default_search_settings, database.settings() or {})

    query: str = request.query_params.get("query", request.query_params.get("q", "")).strip()
    page: int = p if (p := int(request.query_params.get("page", 1))) > 0 else 1
    limit: int = l_ if (l_ := int(request.query_params.get("limit", search_settings["limit"][table_name]))) > 0 else 48
    sort: str = request.query_params.get("sort", search_settings["sort"][table_name]).lower()
    order: str = request.query_params.get("order", search_settings["order"][table_name]).lower()

    if table_name in (users_table, submissions_table):
        view: str = (
            v
            if (v := request.query_params.get("view", search_settings["view"].get(table_name, "")).lower())
            in ("list", "grid")
            else "grid"
        )
    else:
        view = default_search_settings["view"][table_name]

    sql_query: str = query
    if query and query_prefix:
        sql_query = f"({query_prefix}) & (@any {query})"
    elif query_prefix:
        sql_query = query_prefix

    results = database.search(table_name, sql_query, sort, order)

    if (page - 1) * limit > len(results.rows):
        page = ceil(len(results.rows) / limit) or 1

    return TemplateResponse(
        request,
        "pages/search.j2",
        {
            "title": title,
            "username": username,
            "action": request.url.path,
            "table": table_name.lower(),
            "query": query,
            "sort": sort,
            "order": order,
            "view": view,
            "change_view": table_name in (users_table, submissions_table),
            "thumbnails": table_name in (users_table, submissions_table),
            "results": results,
            "page": page,
            "offset": (page - 1) * limit,
            "limit": limit,
            "max_results": database.max_results,
            "search_id": encode_search_id(table_name, sql_query, sort, order) if query and database.use_cache else "",
        },
    )


@requires(["authenticated"])
async def search(request: Request):
    if search_terms := decode_search_id(request.query_params.get("sid", ""))[1]:
        table, query, sort, order = search_terms
        return RedirectResponse(
            request.url_for("search", table=table.lower()).include_query_params(
                query=query,
                sort=sort,
                order=order,
            )
        )
    return await search_response(request, request.path_params["table"])


@requires(["authenticated"])
async def user(request: Request):
    database: Database = request.state.database
    usr = database.user(request.path_params["username"])
    stats = database.user_stats(request.path_params["username"])
    return TemplateResponse(
        request,
        "pages/user.j2",
        {
            "username": request.path_params["username"],
            "user": usr,
            "stats": stats,
        },
    )


@requires(["authenticated"])
async def user_edit(request: Request):
    if "editor" not in request.auth.scopes:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    elif request.path_params["username"] != (username := clean_username(request.path_params["username"])):
        return RedirectResponse(request.url_for("user_edit", username=username))

    database: Database = request.state.database
    if not (usr := database.user(request.path_params["username"])):
        return error_response(
            request,
            status.HTTP_404_NOT_FOUND,
            "The user is not in the database 😢",
            [("Open on FA", f"https://furaffinity.net/user/{clean_username(request.path_params['username'])}")],
        )

    return TemplateResponse(request, "pages/user_edit.j2", {"user": usr})


@requires(["authenticated", "editor"])
async def user_edit_save(request: Request):
    database: Database = request.state.database
    if not (usr := database.database.users[clean_username(request.path_params["username"])]):
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    new_usr = deepcopy(usr)

    async with request.form() as form:
        new_usr["USERPAGE"] = form.get("profile", "").strip()

    database.database.users[new_usr["USERNAME"]] = new_usr
    database.database.commit()

    return Response()


@requires(["authenticated", "editor"])
async def user_edit_delete(request: Request):
    database: Database = request.state.database
    if not (usr := database.user(request.path_params["username"])):
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    del database.database.users[usr["USERNAME"]]
    database.database.commit()
    return Response()


@requires(["authenticated"])
async def user_icon(request: Request):
    username: str = clean_username(request.path_params["username"])
    if not username:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "")
    server_time: datetime = datetime.now(timezone(timedelta(hours=-8)))
    return RedirectResponse(f"https://a.furaffinity.net/{server_time:%Y%m%d}/{username}.gif")


# noinspection DuplicatedCode
@requires(["authenticated"])
async def user_submissions(request: Request):
    return await search_response(
        request,
        submissions_table,
        f"@author == {clean_username(request.path_params['username'])}",
        f"Submissions by {request.path_params['username']}",
        request.path_params["username"],
    )


# noinspection DuplicatedCode
@requires(["authenticated"])
async def user_gallery(request: Request):
    return await search_response(
        request,
        submissions_table,
        f"@author == {clean_username(request.path_params['username'])} & @folder == gallery",
        f"Gallery by {request.path_params['username']}",
        request.path_params["username"],
    )


# noinspection DuplicatedCode
@requires(["authenticated"])
async def user_scraps(request: Request):
    return await search_response(
        request,
        submissions_table,
        f"@author == {clean_username(request.path_params['username'])} & @folder == scraps",
        f"Scraps by {request.path_params['username']}",
        request.path_params["username"],
    )


@requires(["authenticated"])
async def user_journals(request: Request):
    return await search_response(
        request,
        journals_table,
        f"@author == {clean_username(request.path_params['username'])}",
        f"Journals by {request.path_params['username']}",
        request.path_params["username"],
    )


@requires(["authenticated"])
async def user_favorites(request: Request):
    return await search_response(
        request,
        submissions_table,
        f'@favorite "|{clean_username(request.path_params["username"])}|"',
        f"Favorites of {request.path_params['username']}",
        request.path_params["username"],
    )


@requires(["authenticated"])
async def user_comments(request: Request):
    return await search_response(
        request,
        comments_table,
        f"@author == {clean_username(request.path_params['username'])}",
        f"Comments by {request.path_params['username']}",
        request.path_params["username"],
    )


@requires(["authenticated"])
async def submission(request: Request):
    database: Database = request.state.database

    if not (sub := database.submission(request.path_params["id"])):
        return error_response(
            request,
            status.HTTP_404_NOT_FOUND,
            "The submission is not in the database 😢",
            [("Open on FA", f"https://furaffinity.net/view/{request.path_params['id']}")],
        )

    fs, t = database.submission_files(sub["ID"])
    fst = database.submission_files_text(*fs) if fs else []
    fsm = database.submission_files_mime(*fs) if fs else []
    cs = database.submission_comments(sub["ID"])
    p, n = database.submission_prev_next(sub["ID"], sub["AUTHOR"], sub["FOLDER"])
    sp, sn = None, None
    search_id: str | None = None
    search_index: int = 0

    if search_id_param := request.query_params.get("sid"):
        search_id, search_terms, search_index = decode_search_id(search_id_param)
        if search_terms and search_index is not None:
            results = database.search(*search_terms)
            if 0 <= search_index < len(results.rows):
                sp = results.rows[search_index - 1]["ID"] if search_index > 0 else None
                sn = results.rows[search_index + 1]["ID"] if search_index < len(results.rows) - 1 else None

    return TemplateResponse(
        request,
        "pages/submission.j2",
        {
            "title": f"{sub['TITLE']} by {sub['AUTHOR']}",
            "submission": sub,
            "thumbnail": t,
            "files": list(zip(fs, fsm, fst)) if fs else [],
            "comments": cs,
            "prev": p,
            "next": n,
            "search_id": search_id,
            "search_index": search_index,
            "search_prev": sp,
            "search_next": sn,
        },
    )


@requires(["authenticated"])
async def submission_edit(request: Request):
    if "editor" not in request.auth.scopes:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    database: Database = request.state.database
    if not (sub := database.submission(request.path_params["id"])):
        return error_response(
            request,
            status.HTTP_404_NOT_FOUND,
            "The submission is not in the database 😢",
            [("Open on FA", f"https://furaffinity.net/view/{request.path_params['id']}")],
        )

    fs, t = database.submission_files(request.path_params["id"])

    return TemplateResponse(request, "pages/submission_edit.j2", {"submission": sub, "files": fs or [], "thumbnail": t})


@requires(["authenticated", "editor"])
async def submission_edit_save(request: Request):
    database: Database = request.state.database
    if not (sub := database.database.submissions[request.path_params["id"]]):
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    fs, t = database.submission_files(sub["ID"])
    new_sub = deepcopy(sub)

    async with request.form() as form:
        new_sub["AUTHOR"] = form.get("author", "").strip() or new_sub["AUTHOR"]
        new_sub["TITLE"] = form.get("title", "").strip()
        new_sub["DATE"] = datetime.fromisoformat(form.get("date")) if form.get("date") else new_sub["DATE"]
        new_sub["FOLDER"] = form.get("folder", "").strip() or new_sub["FOLDER"]
        new_sub["CATEGORY"] = form.get("category", "").strip() + " / " + form.get("theme", "").strip()
        new_sub["SPECIES"] = form.get("species", "").strip()
        new_sub["GENDER"] = form.get("gender", "").strip()
        new_sub["RATING"] = form.get("rating", "").strip()
        new_sub["TAGS"] = [t for t in form.get("tags", "").strip().split(" ") if t]
        new_sub["FAVORITE"] = {u for f in form.get("favorites", "").strip().split(" ") if (u := clean_username(f))}
        new_sub["DESCRIPTION"] = form.get("description", "").strip()
        new_sub["MENTIONS"] = {
            u
            for a in BeautifulSoup(new_sub["DESCRIPTION"], "lxml").select("a")
            if (m := match(r"^(?:(?:https?://)?(?:www\.)?furaffinity\.net)?/user/([^/#]+).*$", a.attrs["href"]))
            and (u := clean_username(m[1]))
        }

        form_files: dict[int, int | None] = {
            int(m[1]): int(m[2]) if m[3] == "true" else None
            for f in form.getlist("existing_file")
            if (m := match(r"(\d+):(\d+):(true|false)", f))
        }
        form_files = {
            i: None if j is None else j - len([i for i2, j2 in form_files.items() if j2 is None and i2 < j])
            for i, j in form_files.items()
        }
        files: dict[Path, int | None]

        if any(i != j for i, j in form_files.items()):
            files = {f: form_files.get(i, i) for i, f in enumerate(fs or [])}
            for file, new_index in files.items():
                if new_index is None:
                    continue
                copy2(file, file.with_stem(f".submission{new_index or ''}"))
            for file in files.keys():
                file.unlink(missing_ok=True)
            for file, new_index in files.items():
                if new_index is None:
                    continue
                file.with_stem(f".submission{new_index or ''}").replace(file.with_stem(f"submission{new_index or ''}"))

            files = {f: i for f, i in files.items() if i is not None}
            new_sub["FILEEXT"] = [f.suffix.strip(".") for f, i in sorted(files.items(), key=lambda fi: fi[1])]

        if t and form.get("thumbnail") == "false":
            t.unlink(missing_ok=True)
            new_sub["FILESAVED"] &= ~0b1
        if (t_new := form.get("new_thumbnail")) and t_new.size:
            if t:
                t.unlink(missing_ok=True)
            database.database.submissions.save_submission_thumbnail(new_sub["ID"], await t_new.read())
            new_sub["FILESAVED"] |= 0b1

        for f_new in form.getlist("new_file"):
            if not f_new.size:
                continue
            new_sub["FILEEXT"].append(
                database.database.submissions.save_submission_file(
                    new_sub["ID"],
                    await f_new.read(),
                    "submission",
                    Path(f_new.filename).suffix.strip("."),
                    len(new_sub["FILEEXT"]),
                )
            )

    database.database.submissions[new_sub["ID"]] = new_sub
    database.database.commit()

    return Response()


@requires(["authenticated", "editor"])
async def submission_edit_delete(request: Request):
    database: Database = request.state.database
    if not (sub := database.submission(request.path_params["id"])):
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    fs, t = database.submission_files(sub["ID"])
    for f in fs or []:
        f.unlink(missing_ok=True)
    if t:
        t.unlink(missing_ok=True)
    del database.database.submissions[sub["ID"]]
    database.database.commit()
    return Response()


@requires(["authenticated"])
async def submission_thumbnail(request: Request):
    database: Database = request.state.database
    fs, t = database.submission_files(request.path_params["id"])
    x, y = request.path_params.get("x"), request.path_params.get("y")
    if t is not None and t.is_file():
        if not x and not y:
            return FileResponse(str(t))
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
            raise HTTPException(status.HTTP_404_NOT_FOUND, "")
    else:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "")


@requires(["authenticated"])
async def submission_file(request: Request):
    database: Database = request.state.database
    n = request.path_params.get("n", 0)
    fs, _ = database.submission_files(request.path_params["id"])
    content_type: str | None = None
    if not fs or n > len(fs) - 1:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "")
    elif not fs[n].is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "")
    if fs[n].suffix == ".txt" and database.submission_files_mime(fs[n])[0] in ("text/plain", None):
        with fs[n].open("rb") as fh:
            if encoding := detect_encoding(fh.read(1024))["encoding"]:
                content_type = f"text/plain; charset={encoding}"
    return FileResponse(str(fs[n]), content_type=content_type)


@requires(["authenticated"])
async def submission_zip(request: Request):
    database: Database = request.state.database
    if not (sub := database.submission(request.path_params["id"])):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "")

    fs, t = database.submission_files(request.path_params["id"])

    with ZipFile(f_obj := BytesIO(), "w") as z:
        for f in fs:
            if f.is_file():
                z.writestr(f.name, f.read_bytes())
        if t and t.is_file():
            z.writestr(t.name, t.read_bytes())
        if request.query_params.get("files-only") is None:
            z.writestr("description.txt" if database.bbcode() else "description.html", sub["DESCRIPTION"].encode())
            z.writestr("metadata.json", dumps(sub, default=lambda o: list(o) if isinstance(o, set) else str(o)))
            z.writestr("comments.json", dumps(database.submission_comments(request.path_params["id"])))

    f_obj.seek(0)

    return StreamingResponse(f_obj, media_type="application/zip")


@requires(["authenticated"])
async def journal(request: Request):
    database: Database = request.state.database
    if not (jrn := database.journal(request.path_params["id"])):
        return error_response(
            request,
            status.HTTP_404_NOT_FOUND,
            "The journal is not in the database 😢",
            [("Open on FA", f"https://furaffinity.net/journal/{request.path_params['id']}")],
        )

    cs = database.journal_comments(jrn["ID"])
    p, n = database.journal_prev_next(jrn["ID"], jrn["AUTHOR"])
    sp, sn = None, None
    search_id: str | None = None
    search_index: int = 0

    if search_id_param := request.query_params.get("sid"):
        search_id, search_terms, search_index = decode_search_id(search_id_param)
        if search_terms and search_index is not None:
            results = database.search(*search_terms)
            if 0 <= search_index < len(results.rows):
                sp = results.rows[search_index - 1]["ID"] if search_index > 0 else None
                sn = results.rows[search_index + 1]["ID"] if search_index < len(results.rows) - 1 else None

    return TemplateResponse(
        request,
        "pages/journal.j2",
        {
            "title": f"{jrn['TITLE']} by {jrn['AUTHOR']}",
            "journal": jrn,
            "comments": cs,
            "prev": p,
            "next": n,
            "search_id": search_id,
            "search_index": search_index,
            "search_prev": sp,
            "search_next": sn,
        },
    )


@requires(["authenticated"])
async def journal_edit(request: Request):
    if "editor" not in request.auth.scopes:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    database: Database = request.state.database
    if not (jrn := database.journal(request.path_params["id"])):
        return error_response(
            request,
            status.HTTP_404_NOT_FOUND,
            "The journal is not in the database 😢",
            [("Open on FA", f"https://furaffinity.net/journal/{request.path_params['id']}")],
        )

    return TemplateResponse(
        request,
        "pages/journal_edit.j2",
        {"journal": jrn},
    )


@requires(["authenticated", "editor"])
async def journal_edit_save(request: Request):
    database: Database = request.state.database
    if not (jrn := database.database.journals[request.path_params["id"]]):
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    new_jrn = deepcopy(jrn)

    async with request.form() as form:
        new_jrn["AUTHOR"] = form.get("author", "").strip() or new_jrn["AUTHOR"]
        new_jrn["TITLE"] = form.get("title", "").strip()
        new_jrn["DATE"] = datetime.fromisoformat(form.get("date")) if form.get("date") else new_jrn["DATE"]
        new_jrn["CONTENT"] = form.get("description", "").strip()
        new_jrn["MENTIONS"] = {
            u
            for a in BeautifulSoup(new_jrn["CONTENT"], "lxml").select("a")
            if (m := match(r"^(?:(?:https?://)?(?:www\.)?furaffinity\.net)?/user/([^/#]+).*$", a.attrs["href"]))
            and (u := clean_username(m[1]))
        }

    database.database.journals[new_jrn["ID"]] = new_jrn
    database.database.commit()

    return Response()


@requires(["authenticated", "editor"])
async def journal_edit_delete(request: Request):
    database: Database = request.state.database
    if not (jrn := database.journal(request.path_params["id"])):
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    del database.database.journals[jrn["ID"]]
    database.database.commit()
    return Response()


@requires(["authenticated"])
async def journal_zip(request: Request):
    database: Database = request.state.database
    if not (jrn := database.journal(request.path_params["id"])):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "")

    with ZipFile(f_obj := BytesIO(), "w") as z:
        z.writestr("content.txt" if database.bbcode() else "content.html", jrn["CONTENT"].encode())
        z.writestr("metadata.json", dumps(jrn, default=lambda o: list(o) if isinstance(o, set) else str(o)))
        z.writestr("comments.json", dumps(database.journal_comments(request.path_params["id"])))

    f_obj.seek(0)

    return StreamingResponse(f_obj, media_type="application/zip")


@requires(["authenticated"])
async def comment(request: Request):
    parent_table, parent_id, comment_id = (
        request.path_params["parent_table"].lower(),
        request.path_params["parent_id"],
        request.path_params["comment_id"],
    )

    if parent_table == submissions_table.lower():
        return RedirectResponse(str(request.url_for("submission", id=parent_id)) + f"#cid:{comment_id}")
    elif parent_table == journals_table.lower():
        return RedirectResponse(str(request.url_for("journal", id=parent_id)) + f"#cid:{comment_id}")
    else:
        return error_response(request, status.HTTP_404_NOT_FOUND, f"{parent_table.title()!r} is not a page 😢")


def error_response(
    request: Request,
    status_code: int,
    message: str | None = None,
    buttons: list[tuple[str, str]] | None = None,
    traceback: str | None = None,
):
    return TemplateResponse(
        request,
        "pages/error.j2",
        {
            "code": status_code,
            "message": message,
            "buttons": buttons,
            "traceback": traceback,
        },
        status_code,
    )


@requires(["authenticated"])
async def http_error(request: Request, exc: HTTPException):
    if exc.detail:
        return error_response(request, exc.status_code, exc.detail)
    else:
        return Response(None, exc.status_code)


@requires(["authenticated"])
async def general_error(request: Request, exc: Exception):
    return error_response(
        request,
        500,
        f"{exc.__class__.__name__}{':' if exc.args else ''} " + " ".join(map(str, exc.args)),
        None,
        format_exc(),
    )


def server(
    database_path: str | PathLike,
    host: str = "0.0.0.0",
    port: int = None,
    ssl_cert: Path | None = None,
    ssl_key: Path | None = None,
    authentication: tuple[tuple[str, str], ...] | None = None,
    authentication_ignore: tuple[str, ...] | None = None,
    editors: tuple[str, ...] | None = None,
    max_results: int | None = None,
    use_cache: bool = True,
    browser: bool = True,
):
    register_url_convertor("table", TableConvertor())

    routes: list[BaseRoute] = [
        Route("/", home),
        Route("/settings", settings, methods=["GET", "POST"]),
        Route("/user/{username}", user),
        Route("/user/{username}/edit", user_edit),
        Route("/user/{username}/edit", user_edit_save, methods=["POST"]),
        Route("/user/{username}/edit", user_edit_delete, methods=["DELETE"]),
        Route("/user/{username}/icon", user_icon),
        Route("/user/{username}/icon/{filename}", user_icon),
        Route(
            "/user/{username}/thumbnail",
            lambda r: RedirectResponse(r.url_for("user_icon", **r.path_params)),
        ),
        Route(
            "/user/{username}/thumbnail/{filename}",
            lambda r: RedirectResponse(r.url_for("user_icon", **r.path_params)),
        ),
        Route("/submissions/{username}", user_submissions),
        Route("/gallery/{username}", user_gallery),
        Route("/scraps/{username}", user_scraps),
        Route("/favorites/{username}", user_favorites),
        Route("/journals/{username}", user_journals),
        Route("/comments/{username}/", user_comments),
        Route(
            "/view/{id:int}",
            lambda r: RedirectResponse(r.url_for("submission", **r.path_params).include_query_params(**r.query_params)),
        ),
        Route(
            "/full/{id:int}",
            lambda r: RedirectResponse(r.url_for("submission", **r.path_params).include_query_params(**r.query_params)),
        ),
        Route("/submission/{id:int}", submission),
        Route("/submission/{id:int}/edit", submission_edit),
        Route("/submission/{id:int}/edit", submission_edit_save, methods=["POST"]),
        Route("/submission/{id:int}/edit", submission_edit_delete, methods=["DELETE"]),
        Route("/submission/{id:int}/file", submission_file),
        Route("/submission/{id:int}/file/{n:int}", submission_file),
        Route("/submission/{id:int}/file/{n:int}/{filename}", submission_file),
        Route("/submission/{id:int}/thumbnail", submission_thumbnail),
        Route("/submission/{id:int}/thumbnail/{x:int}x", submission_thumbnail),
        Route("/submission/{id:int}/thumbnail/x{y:int}", submission_thumbnail),
        Route("/submission/{id:int}/thumbnail/{x:int}x{y:int}", submission_thumbnail),
        Route("/submission/{id:int}/thumbnail/{x:int}x/{filename}", submission_thumbnail),
        Route("/submission/{id:int}/thumbnail/x{y:int}/{filename}", submission_thumbnail),
        Route("/submission/{id:int}/thumbnail/{x:int}x{y:int}/{filename}", submission_thumbnail),
        Route("/submission/{id:int}/thumbnail/{filename}", submission_thumbnail),
        Route("/submission/{id:int}/zip", submission_zip),
        Route("/submission/{id:int}/zip/{filename}", submission_zip),
        Route("/journal/{id:int}", journal),
        Route("/journal/{id:int}/edit", journal_edit),
        Route("/journal/{id:int}/edit", journal_edit_save, methods=["POST"]),
        Route("/journal/{id:int}/edit", journal_edit_delete, methods=["DELETE"]),
        Route("/journal/{id:int}/zip", journal_zip),
        Route("/journal/{id:int}/zip/{filename}", journal_zip),
        Route("/comment/{parent_table}/{parent_id:int}/{comment_id:int}", comment),
        Route(
            "/search",
            lambda r: RedirectResponse(r.url_for("search", table="submissions").include_query_params(**r.query_params)),
        ),
        Route(
            "/search/{table}",
            lambda r: RedirectResponse(r.url_for("search", **r.path_params).include_query_params(**r.query_params)),
        ),
        Route("/{table:table}", search),
        Route("/logout", logout),
        Mount("/static", app=StaticFiles(directory=Path(__file__).parent / "static")),
    ]
    middleware: list[Middleware] = []
    # noinspection PyTypeChecker
    exception_handlers: dict[Any, ExceptionHandler] = {
        HTTPException: http_error,
        Exception: general_error,
    }

    if authentication:
        # noinspection PyTypeChecker
        middleware.extend(
            [
                Middleware(
                    SessionMiddleware,
                    session_cookie=__package__,
                    secret_key=sha256("\0".join(":".join(a) for a in authentication).encode()).hexdigest(),
                ),
                Middleware(
                    AuthenticationMiddleware,
                    backend=BasicAuthBackend(authentication, authentication_ignore, editors),
                    on_error=BasicAuthBackend.on_auth_error,
                ),
            ]
        )
    else:
        # noinspection PyTypeChecker
        middleware.append(Middleware(AuthenticationMiddleware, backend=NoAuthBackend()))

    if use_cache:
        # noinspection PyTypeChecker
        middleware.append(Middleware(CacheMiddleware))

    if ssl_cert and ssl_key:
        if not ssl_cert or not ssl_cert.is_file():
            raise FileNotFoundError(f"SSL certificate {ssl_cert}")
        elif not ssl_key or not ssl_key.is_file():
            raise FileNotFoundError(f"SSL private key {ssl_key}")
        port = port or 443

    database_path = Path(database_path).resolve()
    address: str = (
        f"{'https' if ssl_cert and ssl_key else 'http'}://"
        f"{'localhost' if host == '0.0.0.0' else host}"
        f"{f':{port}' if port else ''}"
    )

    run(
        Starlette(
            routes=routes,
            middleware=middleware,
            exception_handlers=exception_handlers,
            lifespan=make_lifespan(
                database_path,
                use_cache,
                max_results,
                address,
                bool(ssl_cert and ssl_key),
                bool(authentication),
                browser,
            ),
        ),
        host=host,
        port=port,
        ssl_certfile=str(ssl_cert) if ssl_cert and ssl_key else None,
        ssl_keyfile=str(ssl_key) if ssl_cert and ssl_key else None,
    )
