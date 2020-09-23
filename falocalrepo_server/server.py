from copy import deepcopy
from json import loads as json_loads
from os.path import abspath
from os.path import dirname
from os.path import isfile
from os.path import join
from os.path import split
from re import sub
from sqlite3 import Connection
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from falocalrepo_database import connect_database
from falocalrepo_database import journals_indexes
from falocalrepo_database import read_setting
from falocalrepo_database import search_journals
from falocalrepo_database import search_submissions
from falocalrepo_database import select
from falocalrepo_database import submissions_indexes
from falocalrepo_database import tiered_path
from falocalrepo_database import users_indexes
from flask import Flask
from flask import abort
from flask import redirect
from flask import render_template
from flask import request
from flask import send_file
from werkzeug.exceptions import NotFound

app: Flask = Flask(
    "FurAffinity Local Repo",
    template_folder=join(abspath(dirname(__file__)), "server_templates")
)
last_search: dict = {
    "table": "",
    "order": [],
    "params": {},
    "results": []
}


def clean_username(username: str) -> str:
    return str(sub(r"[^a-zA-Z0-9\-.~,]", "", username.lower().strip()))


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
    last_update: float = float(read_setting(db_temp, "LASTUPDATE"))
    version: str = read_setting(db_temp, "VERSION")
    db_temp.close()

    return render_template(
        "root.html",
        title=app.name,
        submissions_total=sub_n,
        journals_total=jrn_n,
        users_total=usr_n,
        last_update=last_update,
        version_db=version,
    )


@app.route("/user/<username>")
def user(username: str):
    db_temp: Connection = connect_database("FA.db")
    entry: Optional[tuple] = select(db_temp, "USERS", ["*"], "USERNAME", clean_username(username)).fetchone()

    if entry is None:
        db_temp.close()
        return abort(404)

    folders = entry[users_indexes["FOLDERS"]]
    gallery = entry[users_indexes["GALLERY"]]
    scraps = entry[users_indexes["SCRAPS"]]
    favorites = entry[users_indexes["FAVORITES"]]
    mentions = entry[users_indexes["MENTIONS"]]
    journals = entry[users_indexes["JOURNALS"]]

    db_temp.close()

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

    if request.args:
        params: Dict[str, List[str]] = dict(map(
            lambda kv: (kv[0], json_loads(kv[1])),
            request.args.items()
        ))
        order: List[str] = params.get("order", ["AUTHOR", "ID"])
        limit: int = 50
        offset: int = params.get("offset", 0)
        offset = 0 if offset < 0 else offset
        indexes: Dict[str, int] = {}

        if "order" in params:
            del params["order"]
        if "limit" in params:
            del params["limit"]
        if "offset" in params:
            del params["offset"]

        if (last_search["table"], last_search["order"], last_search["params"]) != (table, order, params):
            last_search["table"] = table
            last_search["order"] = deepcopy(order)
            last_search["params"] = deepcopy(params)
            db_temp: Connection = connect_database("FA.db")
            if table == "submissions":
                last_search["results"] = search_submissions(db_temp, order=order, **params)
                indexes = submissions_indexes
            elif table == "journals":
                last_search["results"] = search_journals(db_temp, order=order, **params)
                indexes = journals_indexes
            db_temp.close()

        return render_template(
            "search_results.html",
            title=f"{app.name} · {table.title()} Search Results",
            table=table,
            params=params,
            limit=limit,
            offset=offset,
            results=last_search["results"][offset:offset + limit],
            results_total=len(last_search["results"]),
            indexes=indexes
        )
    else:
        return render_template(
            "search.html",
            title=f"{app.name} · Search {table.title()}",
            table=table
        )


@app.route("/submission/<int:id_>/file/")
def submission_file(id_: int):
    db_temp: Connection = connect_database("FA.db")
    sub_dir: str = join(read_setting(db_temp, "FILESFOLDER"), *split(tiered_path(id_)))
    sub_ext: Optional[Tuple[str]] = select(db_temp, "SUBMISSIONS", ["FILEEXT"], "ID", id_).fetchone()
    db_temp.close()

    if isfile(path := join(sub_dir, f"submission.{sub_ext[0]}")):
        return send_file(path)
    else:
        return abort(404)


@app.route("/journal/<int:id_>/")
def journal(id_: int):
    db_temp: Connection = connect_database("FA.db")
    jrnl: Optional[tuple] = select(db_temp, "JOURNALS", ["*"], "ID", id_).fetchone()
    db_temp.close()

    if jrnl is None:
        return abort(404)

    return render_template(
        "journal.html",
        title=f"{app.name} · {jrnl[journals_indexes['TITLE']]} by {jrnl[journals_indexes['AUTHOR']]}",
        journal=jrnl,
        indexes=journals_indexes
    )


@app.route("/submission/<int:id_>/")
def submission(id_: int):
    db_temp: Connection = connect_database("FA.db")
    sub: Optional[tuple] = select(db_temp, "SUBMISSIONS", ["*"], "ID", id_).fetchone()
    db_temp.close()

    if sub is None:
        return abort(404)

    file_type: Optional[str] = ""
    if (ext := sub[submissions_indexes['FILEEXT']]) in ("jpg", "jpeg", "png", "gif"):
        file_type = "image"
    elif not ext:
        file_type = None

    return render_template(
        "submission.html",
        title=f"{app.name} · {sub[submissions_indexes['TITLE']]} by {sub[submissions_indexes['AUTHOR']]}",
        sub_id=id_,
        submission=sub,
        file_type=file_type,
        indexes=submissions_indexes
    )


def server(host: str = "0.0.0.0", port: int = 8080):
    app.run(host=host, port=port)