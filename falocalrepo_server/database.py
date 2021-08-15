from functools import cache
from pathlib import Path
from re import match
from re import split
from re import sub
from typing import Any
from typing import Callable
from typing import Optional

from falocalrepo_database import FADatabase
from falocalrepo_database import FADatabaseTable
from falocalrepo_database.selector import Selector
from falocalrepo_database.selector import SelectorBuilder as S
from falocalrepo_database.tables import journals_table
from falocalrepo_database.tables import submissions_table
from falocalrepo_database.tables import users_table
from falocalrepo_database.types import Entry

m_time: Callable[[Path], float] = lambda f: f.stat().st_mtime
default_sort: dict[str, str] = {submissions_table: "id", journals_table: "id", users_table: "username"}
default_order: dict[str, str] = {submissions_table: "desc", journals_table: "desc", users_table: "asc"}
checked_cache: Any = None


class FADatabaseWrapper(FADatabase):
    def __init__(self, database_path: Path, _cache=None):
        global checked_cache
        if not _cache or _cache != checked_cache:
            FADatabase.check_connection(database_path)
            super().__init__(database_path, make=False)
            self.check_version(patch=False)
            checked_cache = _cache
        else:
            super().__init__(database_path, make=False)


@cache
def clean_username(username: str, exclude: str = "") -> str:
    return sub(rf"[^a-zA-Z0-9\-.~{exclude}]", "", username.lower().strip())


def format_value(value: str, *, like: bool = False) -> str:
    value = sub(r"(?<!\\)((?:\\\\)+)?([%_^$])", r"\1\\\2", m.group(1)) if (m := match(r'^"(.*)"$', value)) else value
    value = value.lstrip("^") if match(r"^[%^].*", value) else "%" + value if like else value
    value = value.rstrip("$") if match(r".*(?<!\\)((?:\\\\)+)?[%$]$", value) else value + "%" if like else value
    return value


def query_to_sql(query: str, default_field: str, likes: list[str] = None, aliases: dict[str, str] = None) -> tuple[str, list[str]]:
    if not query:
        return "", []
    likes, aliases = likes or [], aliases or {}
    sql_elements: list[str] = []
    values: list[str] = []

    query = sub(r"(^[&| ]+|((?<!\\)[&|]| )+$)", "", query)
    query = sub(r"( *[&|])+(?= *[&|] *[@()])", "", query)

    field, prev = default_field, ""
    for elem in filter(bool, map(str.strip, split(r'((?<!\\)(?:"|!")(?:[^"]|(?<=\\)")*"|(?<!\\)[()&|]| +)', query))):
        if m := match(r"^@(\w+)$", elem):
            field = m.group(1).lower()
            continue
        elif elem == "&":
            sql_elements.append("and")
        elif elem == "|":
            sql_elements.append("or")
        elif elem in ("(", ")"):
            sql_elements.append("and") if elem == "(" and prev not in ("", "&", "|", "(") else None
            sql_elements.append(elem)
        elif elem:
            not_, elem = match(r"^(!)?(.*)$", elem).groups()
            if not elem:
                continue
            sql_elements.append("and") if prev not in ("", "&", "|", "(") else None
            sql_elements.append(f"{aliases.get(field, field)}{' not' * bool(not_)} like ? escape '\\'")
            values.append(format_value(elem, like=field in likes))
        prev = elem

    return " ".join(sql_elements), values


@cache
def load_user(db_path: Path, user: str, _cache=None) -> Optional[Entry]:
    with FADatabaseWrapper(db_path, _cache=_cache) as db:
        return db.users[user]


@cache
def load_user_stats(db_path: Path, user: str, _cache=None) -> dict[str, int]:
    with FADatabaseWrapper(db_path, _cache=_cache) as db:
        return {
            "gallery": db.submissions.select(
                S() & [S("replace(lower(author), '_', '')").__eq__(user), S("folder").__eq__("gallery")],
                columns=["count(ID)"]
            ).cursor.fetchone()[0],
            "scraps": db.submissions.select(
                S() & [S("replace(lower(author), '_', '')").__eq__(user), S("folder").__eq__("scraps")],
                columns=["count(ID)"]
            ).cursor.fetchone()[0],
            "favorites": db.submissions.select(
                S("favorite") % f"%|{user}|%", columns=["count(ID)"]
            ).cursor.fetchone()[0],
            "mentions": db.submissions.select(
                S("mentions") % f"%|{user}|%", columns=["count(ID)"]
            ).cursor.fetchone()[0],
            "journals": db.journals.select(
                S("replace(lower(author), '_', '')").__eq__(user), columns=["count(ID)"]
            ).cursor.fetchone()[0]
        }


@cache
def load_submission(db_path: Path, submission_id: int, _cache=None) -> Optional[Entry]:
    with FADatabaseWrapper(db_path, _cache=_cache) as db:
        return db.submissions[submission_id]


@cache
def load_submission_files(db_path: Path, submission_id: int, _cache=None) -> tuple[Optional[Path], Optional[Path]]:
    with FADatabaseWrapper(db_path, _cache=_cache) as db:
        return db.submissions.get_submission_files(submission_id)


@cache
def load_journal(db_path: Path, journal_id: int, _cache=None) -> Optional[Entry]:
    with FADatabaseWrapper(db_path, _cache=_cache) as db:
        return db.journals[journal_id]


@cache
def load_prev_next(db_path: Path, table: str, item_id: int, _cache=None) -> tuple[int, int]:
    with FADatabaseWrapper(db_path, _cache=_cache) as db:
        item: Optional[dict] = db[table][item_id]
        query: Selector = S("AUTHOR").__eq__(item["AUTHOR"])
        query = S() & [query, S("FOLDER").__eq__(item["FOLDER"])] if table == submissions_table else query
        return db[table].select(
            query,
            columns=["LAG(ID, 1, 0) over (order by ID)", "LEAD(ID, 1, 0) over (order by ID)"],
            order=[f"ABS(ID - {item_id})"],
            limit=1
        ).cursor.fetchone() if item else (0, 0)


@cache
def load_search(db_path: Path, table: str, query: str, sort: str, order: str, *, force: bool = False, _cache=None):
    cols_results: list[str] = []
    default_field: str = "any"
    sort = sort or default_sort[table]
    order = order or default_order[table]

    if table in (submissions_table, journals_table):
        cols_results = ["ID", "AUTHOR", "DATE", "TITLE"]
    elif table == users_table:
        cols_results = ["USERNAME", "FOLDERS"]
        default_field = "username"

    with FADatabaseWrapper(db_path, _cache=_cache) as db:
        db_table: FADatabaseTable = db[table]
        cols_table: list[str] = db_table.columns
        cols_list: list[str] = db_table.list_columns
        col_id: str = db_table.column_id

        if not query and not force:
            return [], cols_table, cols_results, cols_list, col_id, sort, order

        sql, values = query_to_sql(query,
                                   default_field,
                                   [*map(str.lower, {*cols_table, "any"} - {"ID", "AUTHOR", "USERNAME"})],
                                   {"author": "replace(author, '_', '')",
                                    "any": f"({'||'.join(cols_table)})"})

        return (
            list(db_table.select_sql(sql, values, columns=cols_results, order=[f"{sort} {order}"])),
            cols_table,
            cols_results,
            cols_list,
            col_id,
            sort,
            order
        )


@cache
def load_files_folder(db_path: Path, _cache=None) -> Path:
    with FADatabaseWrapper(db_path, _cache=_cache) as db:
        return db.files_folder


@cache
def load_info(db_path: Path, _cache=None) -> tuple[int, int, int, str]:
    with FADatabaseWrapper(db_path, _cache=_cache) as db:
        return len(db.users), len(db.submissions), len(db.journals), db.version
