from copy import deepcopy
from json import dumps as json_dumps
from json import loads as json_loads
from os import chdir
from os import getcwd
from os.path import abspath
from os.path import basename
from os.path import dirname
from os.path import isfile
from os.path import join
from os.path import split
from re import sub as re_sub
from typing import Dict
from typing import List
from typing import Optional

from falocalrepo_database import FADatabase
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


@app.route("/favicon.ico")
def favicon():
    return redirect("https://www.furaffinity.net/favicon.ico")


@app.errorhandler(404)
def not_found(_err: NotFound):
    return render_template(
        "not_found.html",
        title=f"{app.name} · Content not Found"
    ), 404


@app.route("/")
def root():
    global db_path

    sub_n: int
    jrn_n: int
    usr_n: int
    version: str
    with FADatabase(db_path) as db:
        sub_n = int(db.settings["SUBN"])
        jrn_n = int(db.settings["JRNN"])
        usr_n = int(db.settings["USRN"])
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
        return abort(404)

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


@app.route("/search/submissions/")
def search_submissions():
    return search("submissions")


@app.route("/search/journals/")
def search_journals():
    return search("journals")


@app.route("/submissions/<username>/")
@app.route("/search/submissions/<username>/")
def search_user_submissions(username: str):
    return redirect(f'/search/submissions/?author=["{username}"]')


@app.route("/journals/<username>/")
@app.route("/search/journals/<username>/")
def search_user_journals(username: str):
    return redirect(f'/search/journals/?author=["{username}"]')


def search(table: str):
    global last_search
    global db_path

    if request.args:
        params: Dict[str, List[str]] = dict(map(
            lambda kv: (kv[0], json_loads(kv[1])),
            request.args.items()
        ))
        order: List[str] = params.get("order", ["ID DESC"])
        limit: int = 50
        offset: int = params.get("offset", 0)
        offset = 0 if offset < 0 else offset

        if "order" in params:
            del params["order"]
        if "limit" in params:
            del params["limit"]
        if "offset" in params:
            del params["offset"]

        if (last_search["table"], last_search["params"]) != (table, params):
            last_search["table"] = table
            last_search["params"] = deepcopy(params)
            with FADatabase(db_path) as db:
                if table == "submissions":
                    if list(params.keys()) == ["order"]:
                        last_search["results"] = list(db.submissions)
                    else:
                        last_search["results"] = list(db.submissions.cursor_to_dict(
                            db.submissions.select(params, like=True, order=order)))
                elif table == "journals":
                    if list(params.keys()) == ["order"]:
                        last_search["results"] = list(db.journals)
                    else:
                        last_search["results"] = list(db.journals.cursor_to_dict(
                            db.journals.select(params, like=True, order=order)))

        return render_template(
            "search_results.html",
            title=f"{app.name} · {table.title()} Search Results",
            table=table,
            params=params,
            limit=limit,
            offset=offset,
            results=last_search["results"][offset:offset + limit],
            results_total=len(last_search["results"])
        )
    else:
        return render_template(
            "search.html",
            title=f"{app.name} · Search {table.title()}",
            table=table,
            params=json_dumps(last_search["params"])
        )


@app.route("/journal/<int:id_>/")
def journal(id_: int):
    global db_path

    jrnl: Optional[dict]
    with FADatabase(db_path) as db:
        jrnl = db.journals[id_]

    if jrnl is None:
        return abort(404)

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
        return abort(404)

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
