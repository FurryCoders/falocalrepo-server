from functools import lru_cache
from io import BytesIO
from json import dumps as json_dumps
from json import loads as json_loads
from os.path import abspath
from os.path import dirname
from os.path import isfile
from os.path import join
from os.path import split
from re import sub as re_sub
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union
from zipfile import ZipFile

from PIL import Image
from falocalrepo_database import FADatabase
from falocalrepo_database import FADatabaseTable
from falocalrepo_database import tiered_path
from falocalrepo_database.tables import journals_table
from falocalrepo_database.tables import submissions_table
from flask import Flask
from flask import abort
from flask import redirect
from flask import render_template
from flask import request
from flask import send_file
from flask import url_for
from htmlmin.main import minify
from werkzeug.exceptions import NotFound

app: Flask = Flask(
    "FurAffinity Local Repo",
    template_folder=join(abspath(dirname(__file__)), "templates"),
    static_folder=join(abspath(dirname(__file__)), "static")
)
db_path: str = "FA.db"


def clean_username(username: str, exclude: str = "") -> str:
    return str(re_sub(rf"[^a-zA-Z0-9\-.~,{exclude}]", "", username.lower().strip()))


def button(href: str, text: str) -> str:
    return f'<button onclick="window.location = \'{href}\'">{text}</button>'


@app.route("/favicon.ico")
def favicon():
    return redirect("https://www.furaffinity.net/favicon.ico")


@app.errorhandler(404)
def not_found(err: NotFound):
    return error(err.description, 404)


def error(message: str, code: int):
    return render_template(
        "error.html",
        title=f"{app.name} · Content not Found",
        message=f"{code} {message}"
    ), code


@app.route("/")
def root():
    global db_path

    sub_n: int
    jrn_n: int
    usr_n: int
    version: str
    with FADatabase(db_path) as db:
        sub_n = len(db.submissions)
        jrn_n = len(db.journals)
        usr_n = len(db.users)
        version = db.settings["VERSION"]

    return render_template(
        "root.html",
        title=app.name,
        submissions_total=sub_n,
        journals_total=jrn_n,
        users_total=usr_n,
        version_db=version,
    )


@lru_cache
def load_user(username: str) -> Optional[dict]:
    global db_path
    with FADatabase(db_path) as db:
        return db.users[username]


@lru_cache
def load_item(table: str, id_: int) -> Tuple[Dict[str, Union[str, int]], int, int]:
    global db_path

    item: Optional[dict]
    prev_id: int
    next_id: int
    with FADatabase(db_path) as db:
        db_table: FADatabaseTable = db[table]
        item = db_table[id_]
        prev_id, next_id = db_table.select(
            {"AUTHOR": item["AUTHOR"]},
            ["LAG(ID, 1, 0) over (order by ID)", "LEAD(ID, 1, 0) over (order by ID)"],
            order=[f"ABS(ID - {id_})"],
            limit=1
        ).fetchone() if item else (0, 0)

    return item, prev_id, next_id


@lru_cache
def load_submission_file(id_: int) -> Tuple[Optional[str], str]:
    global db_path

    sub, _, _ = load_item(submissions_table, id_)
    sub_dir: str
    with FADatabase(db_path) as db:
        sub_dir = join(dirname(db_path), db.settings["FILESFOLDER"], *split(tiered_path(id_)))

    return sub["FILEEXT"] if sub else None, sub_dir


@lru_cache
def search_table(table: str, sort: str, order: str, params_serialised: str = "{}", all_query: bool = False):
    global db_path

    cols_results: List[str] = []
    cols_list: List[str] = []
    col_id: str = ""
    params: Dict[str, List[str]] = json_loads(params_serialised)

    if table in ("submissions", "journals"):
        cols_results = ["ID", "AUTHOR", "DATE", "TITLE"]
        col_id = "ID"
        order = "DESC" if not order else order
    elif table == "users":
        cols_results = ["USERNAME", "FOLDERS"]
        cols_list = ["FOLDERS"]
        col_id = "USERNAME"
        order = "ASC" if not order else order

    sort = col_id if not sort else sort

    with FADatabase(db_path) as db:
        cols_table: List[str] = db[table].columns

        if not params and not all_query:
            return [], cols_table, cols_results, cols_list, col_id, sort, order

        params = {k: vs for k, vs in params.items() if k in map(str.lower, cols_table)}

        if "author" in params:
            params["replace(author, '_', '')"] = list(map(lambda u: clean_username(u, "%_"), params["author"]))
            del params["author"]
        if "username" in params:
            params["username"] = list(map(lambda u: clean_username(u, "%_"), params["username"]))

        db_table: FADatabaseTable = db[table]
        return (
            list(db_table.cursor_to_dict(
                db_table.select(params, cols_results, like=True, order=[f"{sort} {order}"]),
                cols_results)),
            cols_table,
            cols_results,
            cols_list,
            col_id,
            sort,
            order
        )


@app.after_request
def response_minify(response):
    if response.content_type == u'text/html; charset=utf-8':
        response.set_data(minify(response.get_data(as_text=True)))

    return response


@app.route("/user/<username>")
def user(username: str):
    if username != (username_clean := clean_username(username)):
        return redirect(f"/user/{username_clean}")

    user_entry: Optional[dict] = load_user(username)

    if user_entry is None:
        return error(
            f"User not found.<br>{button(f'https://www.furaffinity.net/user/{username}', 'Open on Fur Affinity')}",
            404
        )

    return render_template(
        "user.html",
        title=f"{app.name} · {username}",
        user=username,
        folders=list(filter(bool, user_entry["FOLDERS"].split(","))),
        gallery_length=f.count(",") + 1 if (f := user_entry["GALLERY"]) else 0,
        scraps_length=f.count(",") + 1 if (f := user_entry["SCRAPS"]) else 0,
        favorites_length=f.count(",") + 1 if (f := user_entry["FAVORITES"]) else 0,
        mentions_length=f.count(",") + 1 if (f := user_entry["MENTIONS"]) else 0,
        journals_length=f.count(",") + 1 if (f := user_entry["JOURNALS"]) else 0
    )


@app.route("/browse/")
def browse_default():
    return redirect(url_for("browse", table="submissions", **{k: request.args.getlist(k) for k in request.args}))


@app.route("/browse/<string:table>/")
def browse(table: str):
    return search(table)


@app.route("/search/")
def search_default():
    return redirect(url_for("search", table="submissions", **{k: request.args.getlist(k) for k in request.args}))


@app.route("/submissions/<username>/")
@app.route("/search/submissions/<username>/")
def search_user_submissions(username: str):
    return redirect(url_for(
        "search", table="submissions", **{**{k: request.args.getlist(k) for k in request.args}, "author": username}))


@app.route("/journals/<username>/")
@app.route("/search/journals/<username>/")
def search_user_journals(username: str):
    return redirect(url_for(
        "search", table="journals", **{**{k: request.args.getlist(k) for k in request.args}, "author": username}))


@app.route("/search/<string:table>/")
def search(table: str):
    table = table.lower()

    if table not in ("submissions", "journals", "users"):
        return error(f"Table {table} not found.", 404)

    params: Dict[str, List[str]] = {
        k: request.args.getlist(k) for k in sorted(map(str.lower, request.args.keys()))
        if k not in ("page", "limit", "sort", "order", "view")
    }

    if params and request.path.startswith("/browse/"):
        return redirect(url_for("search", table=table, **{k: request.args.getlist(k) for k in request.args}))

    results: List[dict]
    columns_results: List[str]
    columns_list: List[str]
    column_id: str
    limit: int = int(request.args.get("limit", 50))
    page: int = int(request.args.get("page", 1))
    sort: str = request.args.get("sort", "").lower()
    order: str = request.args.get("order", "").lower()
    view: str = v if (v := request.args.get("view", "list").lower()) in ("list", "grid") else "list"

    results, columns_table, columns_results, columns_list, column_id, sort, order = search_table(
        table,
        sort,
        order,
        json_dumps(params),
        all_query=request.path.startswith("/browse/")
    )

    return render_template(
        "search.html",
        title=f"{app.name} · {table.title()} Search Results",
        table=table,
        params=params,
        sort=sort.lower(),
        order=order.lower(),
        view=view,
        allow_view=table == "submissions",
        thumbnails=table == "submissions",
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
def journal(id_: int):
    jrnl, prev_id, next_id = load_item(journals_table, id_)

    if jrnl is None:
        return error(
            f"Journal not found.<br>{button(f'https://www.furaffinity.net/journal/{id_}', 'Open on Fur Affinity')}",
            404
        )

    return render_template(
        "journal.html",
        title=f"{app.name} · {jrnl['TITLE']} by {jrnl['AUTHOR']}",
        journal=jrnl,
        prev=prev_id,
        next=next_id
    )


@app.route("/journal/<int:id_>/zip/")
@app.route("/journal/<int:id_>/zip/<filename>")
def journal_zip(id_: int, filename: str = ""):
    jrn, _, _ = load_item(journals_table, id_)

    if jrn is None:
        return abort(404)

    f_obj: BytesIO = BytesIO()

    with ZipFile(f_obj, "w") as z:
        z.writestr("content.html", jrn["CONTENT"].encode())
        z.writestr("metadata.json", json_dumps({k: v for k, v in jrn.items() if k != "CONTENT"}).encode())

    f_obj.seek(0)
    return send_file(f_obj, mimetype="application/zip", attachment_filename=filename if filename else None)


@app.route("/full/<int:id_>/")
@app.route("/view/<int:id_>/")
def submission_view(id_: int):
    return redirect(f"/submission/{id_}")


@app.route("/submission/<int:id_>/")
def submission(id_: int):
    sub, prev_id, next_id = load_item(submissions_table, id_)

    if sub is None:
        return error(
            f"Submission not found.<br>{button(f'https://www.furaffinity.net/view/{id_}', 'Open on Fur Affinity')}",
            404
        )

    return render_template(
        "submission.html",
        title=f"{app.name} · {sub['TITLE']} by {sub['AUTHOR']}",
        submission=sub,
        prev=prev_id,
        next=next_id
    )


@app.route("/submission/<int:id_>/file/")
@app.route("/submission/<int:id_>/file/<filename>")
def submission_file(id_: int, filename: str = ""):
    sub_ext, sub_dir = load_submission_file(id_)

    if sub_ext is None:
        return abort(404)
    elif isfile(path := join(sub_dir, f"submission.{sub_ext}")):
        return send_file(path, attachment_filename=filename if filename else None)
    else:
        return abort(404)


@app.route("/submission/<int:id_>/thumbnail/")
@app.route("/submission/<int:id_>/thumbnail/<string:filename>")
@app.route("/submission/<int:id_>/thumbnail/<int:size>/")
@app.route("/submission/<int:id_>/thumbnail/<int:size>/<string:filename>")
def submission_thumbnail(id_: int, size: int = 150, filename: str = None):
    sub_ext, sub_dir = load_submission_file(id_)

    if sub_ext is None:
        return abort(404)
    elif sub_ext.lower() not in ("jpg", "jpeg", "png", "gif"):
        return abort(404)
    elif isfile(path := join(sub_dir, f"submission.{sub_ext}")):
        sub_ext = sub_ext.lower()
        sub_ext = "jpeg" if sub_ext == "jpg" else sub_ext
        f_obj: BytesIO = BytesIO()
        with Image.open(path) as img:
            img.thumbnail((size, size))
            img.save(f_obj, sub_ext)
        f_obj.seek(0)
        return send_file(f_obj, attachment_filename=filename, mimetype=f"image/{sub_ext}")
    else:
        return abort(404)


@app.route("/submission/<int:id_>/zip/")
@app.route("/submission/<int:id_>/zip/<filename>")
def submission_zip(id_: int, filename: str = ""):
    sub, _, _ = load_item(submissions_table, id_)

    if sub is None:
        return abort(404)

    sub_ext, sub_dir = load_submission_file(id_)
    f_obj: BytesIO = BytesIO()

    with ZipFile(f_obj, "w") as z:
        if isfile(path := join(sub_dir, f"submission.{sub_ext}")):
            z.writestr(f"submission.{sub_ext}", open(path, "rb").read())
        z.writestr("description.html", sub["DESCRIPTION"].encode())
        z.writestr("metadata.json", json_dumps({k: v for k, v in sub.items() if k != "DESCRIPTION"}).encode())

    f_obj.seek(0)
    return send_file(f_obj, mimetype="application/zip", attachment_filename=filename if filename else None)


@app.route("/static/<filename>")
def static_files(filename: str):
    return send_file(path) if isfile(path := join(app.static_folder, filename)) else abort(404)


def server(database_path: str, host: str = "0.0.0.0", port: int = 8080):
    global db_path

    db_path = abspath(database_path)

    app.run(host=host, port=port)
