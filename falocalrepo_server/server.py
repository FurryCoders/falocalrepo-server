from functools import cache
from functools import lru_cache
from io import BytesIO
from json import dumps as json_dumps
from os import PathLike
from pathlib import Path
from typing import Optional
from typing import Union
from zipfile import ZipFile

from PIL import Image
from PIL import UnidentifiedImageError
from chardet import detect as detect_encoding
from falocalrepo_database.exceptions import DatabaseError
from flask import Flask
from flask import Response
from flask import abort
from flask import redirect
from flask import render_template
from flask import request
from flask import send_file
from flask import url_for
from gevent.pywsgi import WSGIServer
from htmlmin.main import minify
from werkzeug.exceptions import NotFound

from .__version__ import __version__
from .database import clean_username
from .database import default_order
from .database import default_sort
from .database import journals_table
from .database import load_info
from .database import load_journal
from .database import load_prev_next
from .database import load_search
from .database import load_submission
from .database import load_submission_files
from .database import load_user
from .database import load_user_stats
from .database import m_time
from .database import submissions_table
from .database import users_table

root: Path = Path(__file__).resolve().parent
app: Flask = Flask(
    "FurAffinity Local Repo",
    template_folder=str(root / "templates"),
    static_folder=str(root / "static")
)


# noinspection HttpUrlsUsage
def redirect_http_server(host: str, port: int) -> WSGIServer:
    app_redirect: Flask = Flask("Redirect HTTP")
    app_redirect.before_request(
        lambda: redirect(request.url.replace("http://", "https://", 1), 301) if not request.is_secure else None)
    app_redirect_server: WSGIServer = WSGIServer((host, port), app_redirect)
    return app_redirect_server


def button(href: str, text: str) -> str:
    return f'<button onclick="window.location = \'{href}\'">{text}</button>'


def serve_error(message: str, code: int):
    return render_template(
        "error.html",
        title=f"{app.name} · Content not Found",
        code=code,
        message=message
    ), code


@app.errorhandler(404)
def error_not_found(err: NotFound):
    return serve_error(err.description, 404)


@app.errorhandler(DatabaseError)
def error_database(err: DatabaseError):
    return serve_error(f"Database error: {err.__class__.__name__} {err.args[0] if err.args else ''}".strip(), 500)


@app.after_request
def response_minify(response: Response):
    if response.content_type == u'text/html; charset=utf-8':
        response.set_data(minify(response.get_data(as_text=True)))
    return response


@app.route("/apple-touch-icon-precomposed.png")
@app.route("/apple-touch-icon.png")
@app.route("/favicon.ico")
def serve_favicon():
    return serve_static_file("favicon.ico")


@app.route("/")
def serve_info():
    usr_n, sub_n, jrn_n, version = load_info(app.config["db_path"], _cache=m_time(app.config["db_path"]))
    return render_template(
        "info.html",
        title=app.name,
        submissions_total=sub_n,
        journals_total=jrn_n,
        users_total=usr_n,
        version_db=version,
        version=__version__
    )


@app.route("/user/<username>")
def serve_user(username: str):
    if username != (username_clean := clean_username(username)):
        return redirect(f"/user/{username_clean}")

    user_entry: Optional[dict] = load_user(app.config["db_path"], username, _cache=m_time(app.config["db_path"]))
    user_stats: dict[str, int] = load_user_stats(app.config["db_path"], username, _cache=m_time(app.config["db_path"]))

    return render_template(
        "user.html",
        title=f"{app.name} · {username}",
        user=username,
        folders=user_entry["FOLDERS"] if user_entry else [],
        gallery_length=user_stats["gallery"],
        scraps_length=user_stats["scraps"],
        favorites_length=user_stats["favorites"],
        mentions_length=user_stats["mentions"],
        journals_length=user_stats["journals"],
    )


@app.route("/browse/")
def redirect_browse_default():
    return redirect(url_for(serve_browse.__name__, table="submissions",
                            **{k: request.args.getlist(k) for k in request.args}))


@app.route("/browse/<string:table>/")
def serve_browse(table: str):
    return serve_search(table, title_=f"Browse {table.title()}")


@app.route("/search/")
def redirect_search_default():
    return redirect(url_for(serve_search.__name__, table="submissions",
                            **{k: request.args.getlist(k) for k in request.args}))


@app.route("/gallery/<username>")
@app.route("/search/gallery/<username>/")
def redirect_search_user_gallery(username: str):
    return serve_search(table="submissions", title_=f"Gallery {username}",
                        args={"query": f'@author "{clean_username(username)}" @folder "gallery"'})


@app.route("/scraps/<username>")
@app.route("/search/scraps/<username>/")
def redirect_search_user_scraps(username: str):
    return serve_search(table="submissions", title_=f"Scraps {username}",
                        args={"query": f'@author "{clean_username(username)}" @folder "scraps"'})


@app.route("/submissions/<username>/")
@app.route("/search/submissions/<username>/")
def redirect_search_user_submissions(username: str):
    return serve_search(table="submissions", title_=f"Submissions {username}",
                        args={"query": f'@author "{clean_username(username)}"'})


@app.route("/journals/<username>/")
@app.route("/search/journals/<username>/")
def redirect_search_user_journals(username: str):
    return serve_search(table="journals", title_=f"Journals {username}",
                        args={"query": f'@author "{clean_username(username)}"'})


@app.route("/favorites/<username>")
@app.route("/search/favorites/<username>/")
def redirect_search_user_favorites(username: str):
    return serve_search(table="submissions", title_=f"Favorites {username}",
                        args={"query": f'@favorite "|{clean_username(username)}|"'})


@app.route("/mentions/<username>")
@app.route("/search/mentions/<username>/")
def redirect_search_user_mentions(username: str):
    return serve_search(table="submissions", title_=f"Mentions {username}",
                        args={"query": f'@mentions "|{clean_username(username)}|"'})


@app.route("/search/<string:table>/")
def serve_search(table: str, title_: str = "", args: dict[str, str] = None):
    if (table := table.upper()) not in (submissions_table, journals_table, users_table):
        return serve_error(f"Table {table.lower()} not found.", 404)

    args = {k.lower(): v for k, v in (args or {}).items()}
    args_req = {k.lower(): v for k, v in request.args.items()}
    query: str = " & ".join([f"({q})" for args_ in (args_req, args) if (q := args_.get("query", None))])
    args |= args_req

    if query and request.path.startswith("/browse/"):
        return redirect(url_for(serve_search.__name__, table=table.lower(), **args))

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

    results, columns_table, columns_results, columns_list, column_id, sort, order = load_search(
        app.config["db_path"],
        table,
        query.lower().strip(),
        sort,
        order,
        force=request.path.startswith("/browse/"),
        _cache=m_time(app.config["db_path"])
    )

    return render_template(
        "search.html",
        title=f"{app.name} · " + (title_.strip() or f"{table.title()} Search Results"),
        table=table.lower(),
        query=query,
        sort=sort,
        order=order,
        view=view,
        allow_view=table == submissions_table,
        thumbnails=table == submissions_table,
        columns_table=columns_table,
        columns_results=columns_results,
        columns_list=columns_list,
        column_id=column_id,
        limit=limit,
        page=(page := (len(results) // limit) + (1 * bool(len(results) % limit)) if page == -1 else page),
        offset=(offset := (page - 1) * limit),
        results=results[offset:offset + limit],
        results_total=len(results)
    )


@app.route("/journal/<int:id_>/")
def serve_journal(id_: int):
    if (jrnl := load_journal(app.config["db_path"], id_, _cache=(_cache := m_time(app.config["db_path"])))) is None:
        return serve_error(
            f"Journal not found.<br>{button(f'https://www.furaffinity.net/journal/{id_}', 'Open on Fur Affinity')}",
            404)

    p, n = load_prev_next(app.config["db_path"], journals_table, id_, _cache=_cache)
    return render_template(
        "journal.html",
        title=f"{app.name} · {jrnl['TITLE']} by {jrnl['AUTHOR']}",
        journal=jrnl,
        prev=p,
        next=n
    )


@lru_cache(maxsize=10)
@app.route("/journal/<int:id_>/zip/")
@app.route("/journal/<int:id_>/zip/<_filename>")
def serve_journal_zip(id_: int, _filename=None):
    if (jrn := load_journal(app.config["db_path"], id_, _cache=m_time(app.config["db_path"]))) is None:
        return serve_error(
            f"Journal not found.<br>{button(f'https://www.furaffinity.net/journal/{id_}', 'Open on Fur Affinity')}",
            404)

    f_obj: BytesIO = BytesIO()

    with ZipFile(f_obj, "w") as z:
        z.writestr("content.html", jrn["CONTENT"].encode())
        z.writestr("metadata.json", json_dumps({k: v for k, v in jrn.items() if k != "CONTENT"}).encode())

    f_obj.seek(0)
    return send_file(f_obj, mimetype="application/zip")


@app.route("/full/<int:id_>/")
@app.route("/view/<int:id_>/")
def redirect_submission_view(id_: int):
    return redirect(f"/submission/{id_}")


@app.route("/submission/<int:id_>/")
def serve_submission(id_: int):
    if (sub := load_submission(app.config["db_path"], id_, _cache=(_cache := m_time(app.config["db_path"])))) is None:
        return serve_error(
            f"Submission not found.<br>{button(f'https://www.furaffinity.net/view/{id_}', 'Open on Fur Affinity')}",
            404)

    f: Optional[Path] = None
    if sub["FILEEXT"] == "txt" and sub["FILESAVED"] >= 10:
        f = load_submission_files(app.config["db_path"], id_, _cache=_cache)[0]
    p, n = load_prev_next(app.config["db_path"], submissions_table, id_, _cache=_cache)
    return render_template(
        "submission.html",
        title=f"{app.name} · {sub['TITLE']} by {sub['AUTHOR']}",
        submission=sub,
        file_text=f.read_text(encoding=detect_encoding(f.read_bytes())["encoding"]) if f else None,
        filename=f"submission{('.' + sub['FILEEXT']) * bool(sub['FILEEXT'])}",
        filename_id=f"{sub['ID']:010d}{('.' + sub['FILEEXT']) * bool(sub['FILEEXT'])}",
        prev=p,
        next=n
    )


@lru_cache(maxsize=10)
@app.route("/submission/<int:id_>/file/")
@app.route("/submission/<int:id_>/file/<_filename>")
def serve_submission_file(id_: int, _filename=None):
    if (sub_file := load_submission_files(app.config["db_path"], id_, _cache=m_time(app.config["db_path"]))[0]) is None:
        return abort(404)
    return send_file(sub_file, attachment_filename=sub_file.name)


@cache
@app.route("/submission/<int:id_>/thumbnail/")
@app.route("/submission/<int:id_>/thumbnail/<_filename>")
@app.route("/submission/<int:id_>/thumbnail/<int:x>/")
@app.route("/submission/<int:id_>/thumbnail/<int:x>/<_filename>")
@app.route("/submission/<int:id_>/thumbnail/<int:x>x<int:y>/")
@app.route("/submission/<int:id_>/thumbnail/<int:x>x<int:y>/<_filename>")
def serve_submission_thumbnail(id_: int, x: int = None, y: int = None, _filename=None):
    sub_file, sub_thumb = load_submission_files(app.config["db_path"], id_, _cache=m_time(app.config["db_path"]))
    if sub_thumb is not None:
        if not x:
            return send_file(sub_thumb, attachment_filename=sub_thumb.name)
        with Image.open(sub_thumb) as img:
            img.thumbnail((x, y or x))
            img.save(f_obj := BytesIO(), img.format, quality=95)
            f_obj.seek(0)
            return send_file(f_obj, attachment_filename=sub_thumb.name)
    elif sub_file is not None:
        try:
            with Image.open(sub_file) as img:
                img.thumbnail((x or 400, y or x or 400))
                img.save(f_obj := BytesIO(), img.format, quality=95)
                f_obj.seek(0)
                return send_file(f_obj, attachment_filename=sub_file.name)
        except UnidentifiedImageError:
            return abort(404)
    else:
        return abort(404)


@lru_cache(maxsize=10)
@app.route("/submission/<int:id_>/zip/")
@app.route("/submission/<int:id_>/zip/<_filename>")
def serve_submission_zip(id_: int, _filename=None):
    if (sub := load_submission(app.config["db_path"], id_, _cache=(_cache := m_time(app.config["db_path"])))) is None:
        return abort(404)

    sub_file, sub_thumb = load_submission_files(app.config["db_path"], id_, _cache=_cache)
    f_obj: BytesIO = BytesIO()

    with ZipFile(f_obj, "w") as z:
        z.writestr(sub_file.name, sub_file.read_bytes()) if sub_file else None
        z.writestr(sub_thumb.name, sub_thumb.read_bytes()) if sub_thumb else None
        z.writestr("description.html", sub["DESCRIPTION"].encode())
        z.writestr("metadata.json", json_dumps({k: v for k, v in sub.items() if k != "DESCRIPTION"}).encode())

    f_obj.seek(0)
    return send_file(f_obj, mimetype="application/zip")


@lru_cache(maxsize=10)
@app.route("/static/<path:filename>")
def serve_static_file(filename: Union[str, PathLike]):
    filepath: Path = Path(app.static_folder, filename)
    return send_file(filepath, attachment_filename=filepath.name) if filepath.is_file() else abort(404)


# noinspection HttpUrlsUsage
def server(database_path: Union[str, PathLike], host: str = "0.0.0.0", port: int = None,
           ssl_cert: Union[str, PathLike] = None, ssl_key: Union[str, PathLike] = None, redirect_http: bool = False):
    app.config["db_path"] = Path(database_path).resolve()
    print("Using database", app.config['db_path'])
    if ssl := ssl_cert and ssl_key:
        port = port or 443
        ssl_cert, ssl_key = Path(ssl_cert), Path(ssl_key)
        print("Using SSL certificate", ssl_cert)
        print("Using SSL key", ssl_key)
    else:
        port = port or 80
        ssl_cert = ssl_key = None
    app_server: WSGIServer = WSGIServer((host, port), app, certfile=ssl_cert, keyfile=ssl_key)
    redirect_server: Optional[WSGIServer] = redirect_http_server(host, 80) if redirect_http and ssl and port != 80 else None
    print(f"Serving app on {'https' if ssl else 'http'}://{app_server.server_host}:{app_server.server_port}")
    if redirect_server:
        print(f"Redirecting from http://{redirect_server.server_host}:{redirect_server.server_port}")
    try:
        if redirect_server:
            redirect_server.start()
        app_server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if redirect_server:
            redirect_server.stop()
        app_server.stop()
