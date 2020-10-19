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
from sqlite3 import Connection
from typing import Dict
from typing import List
from typing import Optional

from falocalrepo_database import connect_database
from falocalrepo_database import get_journal
from falocalrepo_database import get_submission
from falocalrepo_database import get_user
from falocalrepo_database import journals_indexes
from falocalrepo_database import journals_table
from falocalrepo_database import read_setting
from falocalrepo_database import search_journals as db_search_journals
from falocalrepo_database import search_submissions as db_search_submissions
from falocalrepo_database import select_all
from falocalrepo_database import submissions_indexes
from falocalrepo_database import submissions_table
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
    "results": [],
    "indexes": {}
}
db_path: str = "FA.db"


def clean_username(username: str) -> str:
    return str(re_sub(r"[^a-zA-Z0-9\-.~,]", "", username.lower().strip()))


@app.route("/favicon.ico")
def favicon():
    return redirect("https://www.furaffinity.net/favicon.ico")


@app.errorhandler(404)
def not_found(err: NotFound):
    return render_template(
        "not_found.html",
        title=f"{app.name} · Content not Found"
    ), 404


@app.route("/")
def root():
    db_temp: Connection = connect_database("FA.db")
    sub_n: int = int(read_setting(db_temp, "SUBN"))
    jrn_n: int = int(read_setting(db_temp, "JRNN"))
    usr_n: int = int(read_setting(db_temp, "USRN"))
    version: str = read_setting(db_temp, "VERSION")
    db_temp.close()

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
    global db_path

    user_entry: Optional[dict]
    with connect_database(db_path) as db_temp:
        user_entry = get_user(db_temp, clean_username(username))

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
        limit: int = 50
        offset: int = params.get("offset", 0)
        offset = 0 if offset < 0 else offset

        params["order"] = params.get("order", ["ID DESC"])
        if "limit" in params:
            del params["limit"]
        if "offset" in params:
            del params["offset"]

        if (last_search["table"], last_search["params"]) != (table, params):
            last_search["table"] = table
            last_search["params"] = deepcopy(params)
            with connect_database(db_path) as db_temp:
                if table == "submissions":
                    if list(params.keys()) == ["order"]:
                        last_search["results"] = select_all(db_temp, submissions_table, ["*"],
                                                            params["order"]).fetchall()
                    else:
                        last_search["results"] = db_search_submissions(db_temp, **params)
                    last_search["indexes"] = submissions_indexes
                elif table == "journals":
                    if list(params.keys()) == ["order"]:
                        last_search["results"] = select_all(db_temp, journals_table, ["*"], params["order"]).fetchall()
                    else:
                        last_search["results"] = db_search_journals(db_temp, **params)
                    last_search["indexes"] = journals_indexes

        return render_template(
            "search_results.html",
            title=f"{app.name} · {table.title()} Search Results",
            table=table,
            params=params,
            limit=limit,
            offset=offset,
            results=last_search["results"][offset:offset + limit],
            results_total=len(last_search["results"]),
            indexes=last_search["indexes"]
        )
    else:
        return render_template(
            "search.html",
            title=f"{app.name} · Search {table.title()}",
            table=table,
            params=json_dumps(last_search["params"])
        )


@app.route("/submission/<int:id_>/file/")
def submission_file(id_: int):
    global db_path

    db_temp: Connection = connect_database(db_path)
    sub_dir: str = join(dirname(db_path), read_setting(db_temp, "FILESFOLDER"), *split(tiered_path(id_)))
    sub: Optional[dict] = get_submission(db_temp, id_)
    db_temp.close()

    if sub is None:
        return abort(404)
    elif isfile(path := join(sub_dir, f"submission.{sub['FILEEXT']}")):
        return send_file(path)
    else:
        return abort(404)


@app.route("/journal/<int:id_>/")
def journal(id_: int):
    global db_path

    jrnl: Optional[dict]
    with connect_database(db_path) as db_temp:
        jrnl = get_journal(db_temp, id_)

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
    with connect_database(db_path) as db_temp:
        sub = get_submission(db_temp, id_)

    if sub is None:
        return abort(404)

    file_type: Optional[str] = ""
    if (ext := sub["FILEEXT"]) in ("jpg", "jpeg", "png", "gif"):
        file_type = "image"
    elif not ext:
        file_type = None

    return render_template(
        "submission.html",
        title=f"{app.name} · {sub['TITLE']} by {sub['AUTHOR']}",
        submission=sub,
        file_type=file_type
    )


def server(database_path: str, host: str = "0.0.0.0", port: int = 8080):
    global db_path

    chdir(path if (path := dirname(database_path)) else ".")

    db_path = join(abspath(getcwd()), basename(database_path))

    app.run(host=host, port=port)
