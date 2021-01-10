from functools import lru_cache
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

from falocalrepo_database import FADatabase
from falocalrepo_database import FADatabaseTable
from falocalrepo_database import tiered_path
from flask import Flask
from flask import abort
from flask import redirect
from flask import render_template
from flask import request
from flask import send_file
from werkzeug.exceptions import NotFound

app: Flask = Flask(
    "FurAffinity Local Repo",
    template_folder=join(abspath(dirname(__file__)), "templates")
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


@lru_cache()
def load_journal(id_: int) -> Optional[dict]:
    global db_path
    with FADatabase(db_path) as db:
        return db.journals[id_]


@lru_cache
def load_submission(id_: int) -> Tuple[Optional[dict], int, int]:
    global db_path

    sub: Optional[dict]
    prev_id: int
    next_id: int
    with FADatabase(db_path) as db:
        sub = db.submissions[id_]
        prev_id, next_id = db.submissions.select(
            {"AUTHOR": sub["AUTHOR"]},
            ["LAG(ID, 1, 0) over (order by ID)", "LEAD(ID, 1, 0) over (order by ID)"],
            order=[f"ABS(ID - {id_})"],
            limit=1
        ).fetchone() if sub else (0, 0)

    return sub, prev_id, next_id


@lru_cache
def load_submission_file(id_: int) -> Tuple[Optional[str], str]:
    global db_path

    sub, *_ = load_submission(id_)
    sub_dir: str
    with FADatabase(db_path) as db:
        sub_dir = join(dirname(db_path), db.settings["FILESFOLDER"], *split(tiered_path(id_)))

    return sub["FILEEXT"] if sub else None, sub_dir


@lru_cache
def search_table(table: str, **params):
    global db_path

    cols_results: List[str] = []
    cols_list: List[str] = []
    col_id: str = ""
    params = {p: json_loads(v) for p, v in params.items()}
    order: List[str] = params.get("order", None)

    if table in ("submissions", "journals"):
        cols_results = ["ID", "AUTHOR", "DATE", "TITLE"]
        cols_results += ["TAGS"] if table == "submissions" else []
        cols_list = ["TAGS"] if table == "submissions" else []
        col_id = "ID"
        order = [f"ID DESC"] if not order else order
    elif table == "users":
        cols_results = ["USERNAME", "FOLDERS"]
        cols_list = ["FOLDERS"]
        col_id = "USERNAME"
        order = [f"USERNAME ASC"] if not order else order

    with FADatabase(db_path) as db:
        cols_table: List[str] = db[table].columns

        if not params:
            return [], cols_table, cols_results, cols_list, col_id

        if "author" in params:
            params["replace(author, '_', '')"] = list(map(lambda u: clean_username(u, "%_"), params["author"]))
            del params["author"]
        if "username" in params:
            params["username"] = list(map(lambda u: clean_username(u, "%_"), params["username"]))
        if "order" in params:
            del params["order"]

        db_table: FADatabaseTable = db[table]
        return (
            list(db_table.cursor_to_dict(db_table.select(params, cols_results, like=True, order=order), cols_results)),
            cols_table,
            cols_results,
            cols_list,
            col_id
        )


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


@app.route("/search/")
def search_default():
    return redirect("/search/submissions/")


@app.route("/submissions/<username>/")
@app.route("/search/submissions/<username>/")
def search_user_submissions(username: str):
    return redirect(f'/search/submissions/?author=["{username}"]')


@app.route("/journals/<username>/")
@app.route("/search/journals/<username>/")
def search_user_journals(username: str):
    return redirect(f'/search/journals/?author=["{username}"]')


@app.route("/search/<string:table>/")
def search(table: str = "submissions"):
    table = table.lower()

    if table not in ("submissions", "journals", "users"):
        return error(f"Table {table} not found.", 404)

    params: Dict[str, str] = {k: request.args[k] for k in sorted(map(str.lower, request.args.keys()))}

    results: List[dict]
    columns_results: List[str]
    columns_list: List[str]
    column_id: str
    limit: int = 50
    offset: int = int(params.get("offset", 0))

    if "offset" in params:
        del params["offset"]

    results, columns_table, columns_results, columns_list, column_id = search_table(table, **params)

    return render_template(
        "search.html",
        title=f"{app.name} · {table.title()} Search Results",
        table=table,
        params={p: json_loads(v) for p, v in params.items()},
        columns_table=columns_table,
        columns_results=columns_results,
        columns_list=columns_list,
        column_id=column_id,
        limit=limit,
        offset=offset,
        results=results[offset:offset + limit],
        results_total=len(results)
    )


@app.route("/journal/<int:id_>/")
def journal(id_: int):
    jrnl: Optional[dict] = load_journal(id_)

    if jrnl is None:
        return error(
            f"Journal not found.<br>{button(f'https://www.furaffinity.net/journal/{id_}', 'Open on Fur Affinity')}",
            404
        )

    return render_template(
        "journal.html",
        title=f"{app.name} · {jrnl['TITLE']} by {jrnl['AUTHOR']}",
        journal=jrnl
    )


@app.route("/view/<int:id_>/")
def submission_view(id_: int):
    return redirect(f"/submission/{id_}")


@app.route("/submission/<int:id_>/")
def submission(id_: int):
    sub, prev_id, next_id = load_submission(id_)

    if sub is None:
        return error(
            f"Submission not found.<br>{button(f'https://www.furaffinity.net/view/{id_}', 'Open on Fur Affinity')}",
            404
        )

    file_type: Optional[str] = ""
    if (ext := sub["FILEEXT"]) in ("jpg", "jpeg", "png", "gif"):
        file_type = "image"
    elif ext == "mp3":
        file_type = "audio"
    elif not ext:
        file_type = None

    return render_template(
        "submission.html",
        title=f"{app.name} · {sub['TITLE']} by {sub['AUTHOR']}",
        submission=sub,
        file_type=file_type,
        prev=prev_id,
        next=next_id
    )


@app.route("/submission/<int:id_>/file/")
def submission_file(id_: int):
    sub_ext, sub_dir = load_submission_file(id_)

    if sub_ext is None:
        return abort(404)
    elif isfile(path := join(sub_dir, f"submission.{sub_ext}")):
        return send_file(path)
    else:
        return abort(404)


def server(database_path: str, host: str = "0.0.0.0", port: int = 8080):
    global db_path

    db_path = abspath(database_path)

    app.run(host=host, port=port)
