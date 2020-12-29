from copy import deepcopy
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
last_search: dict = {
    "table": "",
    "order": [],
    "params": {},
    "results": []
}
db_path: str = "FA.db"


def clean_username(username: str) -> str:
    return str(re_sub(r"[^a-zA-Z0-9\-.~,]", "", username.lower().strip()))


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


@app.route("/user/<username>")
def user(username: str):
    if username != (username_clean := clean_username(username)):
        return redirect(f"/user/{username_clean}")

    global db_path

    user_entry: Optional[dict]
    with FADatabase(db_path) as db:
        user_entry = db.users[username]

    if user_entry is None:
        return error(
            f"User not found.<br>{button(f'https://www.furaffinity.net/user/{username}', 'Open on Fur Affinity')}",
            404
        )

    folders: List[int] = list(filter(bool, user_entry["FOLDERS"].split(",")))
    gallery: List[int] = list(map(int, filter(bool, user_entry["GALLERY"].split(","))))
    scraps: List[int] = list(map(int, filter(bool, user_entry["SCRAPS"].split(","))))
    favorites: List[int] = list(map(int, filter(bool, user_entry["FAVORITES"].split(","))))
    mentions: List[int] = list(map(int, filter(bool, user_entry["MENTIONS"].split(","))))
    journals: List[int] = list(map(int, filter(bool, user_entry["JOURNALS"].split(","))))

    return render_template(
        "user.html",
        title=f"{app.name} · {username}",
        user=username,
        folders=folders,
        gallery=gallery,
        scraps=scraps,
        favorites=favorites,
        mentions=mentions,
        journals=journals
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
    global last_search
    global db_path

    table = table.lower()
    if table not in ("submissions", "journals", "users"):
        return error(f"Table {table} not found.", 404)

    with FADatabase(db_path) as db:
        if not request.args:
            return render_template(
                "search.html",
                title=f"{app.name} · Search {table.title()}",
                table=table,
                columns=db[table].columns,
                params=json_dumps(last_search["params"])
            )

        params: Dict[str, List[str]] = dict(map(
            lambda kv: (kv[0], json_loads(kv[1])),
            request.args.items()
        ))

        limit: int = 50
        offset: int = params.get("offset", 0)
        offset = 0 if offset < 0 else offset
        columns: List[str]
        columns_list: List[str]
        column_id: str
        order: List[str]

        if table in ("submissions", "journals"):
            columns = ["ID", "AUTHOR", "TITLE"]
            columns += ["TAGS"] if table == "submissions" else []
            columns_list = ["TAGS"] if table == "submissions" else []
            column_id = "ID"
            order: List[str] = params.get("order", [f"ID DESC"])
        elif table == "users":
            columns = ["USERNAME", "FOLDERS"]
            columns_list = ["FOLDERS"]
            column_id = "USERNAME"
            order: List[str] = params.get("order", [f"USERNAME ASC"])

        if "order" in params:
            del params["order"]
        if "limit" in params:
            del params["limit"]
        if "offset" in params:
            del params["offset"]

        if (last_search["table"], last_search["params"], last_search["order"]) != (table, params, order):
            last_search["table"] = table
            last_search["params"] = deepcopy(params)
            last_search["order"] = deepcopy(order)
            db_table: FADatabaseTable = db[table]
            if "author" in params:
                params["replace(author, '_', '')"] = list(map(clean_username, params["author"]))
                del params["author"]
            last_search["results"] = list(
                db_table.cursor_to_dict(db_table.select(params, columns, like=True, order=order), columns))

        return render_template(
            "search_results.html",
            title=f"{app.name} · {table.title()} Search Results",
            table=table,
            params=last_search["params"],
            columns=columns,
            columns_list=columns_list,
            column_id=column_id,
            limit=limit,
            offset=offset,
            results=last_search["results"][offset:offset + limit],
            results_total=len(last_search["results"])
        )


@app.route("/journal/<int:id_>/")
def journal(id_: int):
    global db_path

    jrnl: Optional[dict]
    with FADatabase(db_path) as db:
        jrnl = db.journals[id_]

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
    global db_path

    sub: Optional[dict]
    with FADatabase(db_path) as db:
        sub: Optional[dict] = db.submissions[id_]

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
        file_type=file_type
    )


@app.route("/submission/<int:id_>/file/")
def submission_file(id_: int):
    global db_path

    sub: Optional[dict]
    sub_dir: str
    with FADatabase(db_path) as db:
        sub = db.submissions[id_]
        sub_dir = join(dirname(db_path), db.settings["FILESFOLDER"], *split(tiered_path(id_)))

    if sub is None:
        return abort(404)
    elif isfile(path := join(sub_dir, f"submission.{sub['FILEEXT']}")):
        return send_file(path)
    else:
        return abort(404)


def server(database_path: str, host: str = "0.0.0.0", port: int = 8080):
    global db_path

    db_path = abspath(database_path)

    app.run(host=host, port=port)
