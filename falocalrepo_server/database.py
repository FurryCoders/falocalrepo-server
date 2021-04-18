from functools import cache
from json import loads
from os import stat
from re import sub
from typing import Callable
from typing import Optional
from typing import Union

from falocalrepo_database import FADatabase
from falocalrepo_database import FADatabaseTable
from falocalrepo_database.database import Entry
from falocalrepo_database.tables import journals_table
from falocalrepo_database.tables import submissions_table
from falocalrepo_database.tables import users_table

m_time: Callable[[str], float] = lambda f: int(stat(f).st_mtime)
default_sort: dict[str, str] = {submissions_table: "id", journals_table: "id", users_table: "username"}
default_order: dict[str, str] = {submissions_table: "desc", journals_table: "desc", users_table: "asc"}


@cache
def clean_username(username: str, exclude: str = "") -> str:
    return sub(rf"[^a-zA-Z0-9\-.~{exclude}]", "", username.lower().strip())


@cache
def load_user(db_path: str, user: str, _cache=None) -> Optional[Entry]:
    with FADatabase(db_path) as db:
        return db.users[user]


@cache
def load_user_stats(db_path: str, user: str, _cache=None) -> dict[str, int]:
    with FADatabase(db_path) as db:
        stats: dict[str, int] = {
            "gallery": db.submissions.select(
                {"replace(lower(author), '_', '')": user, "folder": "gallery"}, ["count(ID)"]
            ).cursor.fetchone()[0],
            "scraps": db.submissions.select(
                {"replace(lower(author), '_', '')": user, "folder": "scraps"}, ["count(ID)"]
            ).cursor.fetchone()[0],
            "favorites": db.submissions.select(
                {"favorite": f"%|{user}|%"}, ["count(ID)"], like=True
            ).cursor.fetchone()[0],
            "mentions": db.submissions.select(
                {"mentions": f"%|{user}|%"}, ["count(ID)"], like=True
            ).cursor.fetchone()[0],
            "journals": db.journals.select(
                {"replace(lower(author), '_', '')": user}, ["count(ID)"]
            ).cursor.fetchone()[0]}
        return stats


@cache
def load_submission(db_path: str, submission_id: int, _cache=None) -> Optional[Entry]:
    with FADatabase(db_path) as db:
        return db.submissions[submission_id]


@cache
def load_submission_files(db_path: str, submission_id: int, _cache=None) -> tuple[Optional[bytes], Optional[bytes]]:
    with FADatabase(db_path) as db:
        return db.submissions.get_submission_files(submission_id)


@cache
def load_journal(db_path: str, journal_id: int, _cache=None) -> Optional[Entry]:
    with FADatabase(db_path) as db:
        return db.journals[journal_id]


@cache
def load_prev_next(db_path: str, table: str, item_id: int, _cache=None) -> tuple[int, int]:
    with FADatabase(db_path) as db:
        item: Optional[dict] = db[table][item_id]
        return db[table].select(
            {"AUTHOR": item["AUTHOR"], **({"folder": item["FOLDER"]} if table == submissions_table else {})},
            ["LAG(ID, 1, 0) over (order by ID)", "LEAD(ID, 1, 0) over (order by ID)"],
            order=[f"ABS(ID - {item_id})"],
            limit=1
        ).cursor.fetchone() if item else (0, 0)


@cache
def load_search(db_path: str, table: str, sort: str, order: str, params_: str = "{}", force: bool = False, _cache=None):
    cols_results: list[str] = []
    params: dict[str, list[str]] = loads(params_)
    order = order or default_order[table]
    sort = sort or default_sort[table]

    if table in (submissions_table, journals_table):
        cols_results = ["ID", "AUTHOR", "DATE", "TITLE"]
    elif table == users_table:
        cols_results = ["USERNAME", "FOLDERS"]

    with FADatabase(db_path) as db:
        db_table: FADatabaseTable = db[table]
        cols_table: list[str] = db_table.columns
        cols_list: list[str] = db_table.list_columns
        col_id: str = db_table.column_id

        if not params and not force:
            return [], cols_table, cols_results, cols_list, col_id, sort, order

        params = {k: vs for k, vs in params.items() if k in map(str.lower, cols_table + ["any", "sql"])}

        if "sql" in params:
            query: str = " or ".join(map(lambda p: f"({p})", params["sql"]))
            query = sub(r"any(?= +(!?=|(not +)?(like|glob)|[<>]=?))", f"({'||'.join(cols_table)})", query)
            return (
                list(db_table.select_sql(query, columns=cols_results, order=[f"{sort} {order}"])),
                cols_table,
                cols_results,
                cols_list,
                col_id,
                sort,
                order
            )
        if "author" in params:
            params["replace(author, '_', '')"] = list(map(lambda u: clean_username(u, "%_"), params["author"]))
            del params["author"]
        if "username" in params:
            params["username"] = list(map(lambda u: clean_username(u, "%_"), params["username"]))
        if "any" in params:
            params[f"({'||'.join(cols_table)})"] = params["any"]
            del params["any"]

        return (
            list(db_table.select(params, cols_results, like=True, order=[f"{sort} {order}"])),
            cols_table,
            cols_results,
            cols_list,
            col_id,
            sort,
            order
        )


@cache
def load_files_folder(db_path: str, _cache=None) -> str:
    with FADatabase(db_path) as db:
        return db.files_folder


@cache
def load_info(db_path: str, _cache=None) -> tuple[int, int, int, str]:
    with FADatabase(db_path) as db:
        return len(db.users), len(db.submissions), len(db.journals), db.version
