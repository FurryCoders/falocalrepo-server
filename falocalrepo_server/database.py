from functools import cache
from pathlib import Path
from re import match
from re import split
from re import sub
from typing import Optional

from falocalrepo_database import FADatabase
from falocalrepo_database import FADatabaseTable
from falocalrepo_database.selector import Selector
from falocalrepo_database.selector import SelectorBuilder as Sb
from falocalrepo_database.tables import journals_table
from falocalrepo_database.tables import submissions_table
from falocalrepo_database.tables import users_table
from falocalrepo_database.types import Entry

default_sort: dict[str, str] = {submissions_table: "id", journals_table: "id", users_table: "username"}
default_order: dict[str, str] = {submissions_table: "desc", journals_table: "desc", users_table: "asc"}


@cache
def clean_username(username: str, exclude: str = "") -> str:
    return sub(rf"[^a-zA-Z0-9\-.~{exclude}]", "", username.lower().strip())


def format_value(value: str, *, like: bool = False) -> str:
    value = sub(r"(?<!\\)((?:\\\\)+)?([%_^$])", r"\1\\\2", m.group(1)) if (m := match(r'^"(.*)"$', value)) else value
    value = value.lstrip("^") if match(r"^[%^].*", value) else "%" + value if like else value
    value = value.rstrip("$") if match(r".*(?<!\\)((?:\\\\)+)?[%$]$", value) else value + "%" if like else value
    return value


def query_to_sql(query: str, default_field: str, likes: list[str] = None, aliases: dict[str, str] = None
                 ) -> tuple[str, list[str]]:
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


class Database(FADatabase):
    def __init__(self, database_path: Path):
        FADatabase.check_connection(database_path)
        super(Database, self).__init__(database_path, make=False)

    @property
    def m_time(self):
        return self.database_path.stat().st_mtime

    @cache
    def _load_user_cached(self, user: str, *, _cache=None) -> Optional[Entry]:
        return self.users[user]

    @cache
    def _load_user_stats_cached(self, user: str, *, _cache=None) -> dict[str, int]:
        return {
            "gallery": self.submissions.select(
                Sb() & [Sb("replace(lower(author), '_', '')").__eq__(user), Sb("folder").__eq__("gallery")],
                columns=["count(ID)"]
            ).cursor.fetchone()[0],
            "scraps": self.submissions.select(
                Sb() & [Sb("replace(lower(author), '_', '')").__eq__(user), Sb("folder").__eq__("scraps")],
                columns=["count(ID)"]
            ).cursor.fetchone()[0],
            "favorites": self.submissions.select(
                Sb("favorite") % f"%|{user}|%", columns=["count(ID)"]
            ).cursor.fetchone()[0],
            "mentions": self.submissions.select(
                Sb("mentions") % f"%|{user}|%", columns=["count(ID)"]
            ).cursor.fetchone()[0],
            "journals": self.journals.select(
                Sb("replace(lower(author), '_', '')").__eq__(user), columns=["count(ID)"]
            ).cursor.fetchone()[0]
        }

    @cache
    def _load_submission_cached(self, submission_id: int, *, _cache=None) -> Optional[Entry]:
        return self.submissions[submission_id]

    @cache
    def _load_submission_files_cached(self, submission_id: int, *, _cache=None
                                      ) -> tuple[Optional[Path], Optional[Path]]:
        return self.submissions.get_submission_files(submission_id)

    @cache
    def _load_journal_cached(self, journal_id: int, *, _cache=None) -> Optional[Entry]:
        return self.journals[journal_id]

    @cache
    def _load_prev_next_cached(self, table: str, item_id: int, *, _cache=None) -> tuple[int, int]:
        table: FADatabaseTable = self[table]
        item: Optional[dict] = table[item_id]
        query: Selector = Sb("AUTHOR").__eq__(item["AUTHOR"])
        query = Sb() & [query, Sb("FOLDER").__eq__(item["FOLDER"])] if table == submissions_table else query
        return table.select(
            query,
            columns=["LAG(ID, 1, 0) over (order by ID)", "LEAD(ID, 1, 0) over (order by ID)"],
            order=[f"ABS(ID - {item_id})"],
            limit=1
        ).cursor.fetchone() if item else (0, 0)

    @cache
    def _load_search_cached(self, table: str, query: str, sort: str, order: str, *, force: bool = False, _cache=None):
        cols_results: list[str] = []
        default_field: str = "any"
        sort = sort or default_sort[table]
        order = order or default_order[table]

        if table in (submissions_table, journals_table):
            cols_results = ["ID", "AUTHOR", "DATE", "TITLE"]
        elif table == users_table:
            cols_results = ["USERNAME", "FOLDERS"]
            default_field = "username"

        db_table: FADatabaseTable = self[table]
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
    def _load_files_folder_cached(self, *, _cache=None) -> Path:
        return self.files_folder

    @cache
    def _load_info_cached(self, *, _cache=None) -> tuple[int, int, int, str]:
        return len(self.users), len(self.submissions), len(
            self.journals), self.version

    def load_user(self, user: str) -> Optional[Entry]:
        return self._load_user_cached(user, _cache=self.m_time)

    def load_user_stats(self, user: str) -> dict[str, int]:
        return self._load_user_stats_cached(user, _cache=self.m_time)

    def load_submission(self, submission_id: int) -> Optional[Entry]:
        return self._load_submission_cached(submission_id, _cache=self.m_time)

    def load_submission_files(self, submission_id: int) -> tuple[Optional[Path], Optional[Path]]:
        return self._load_submission_files_cached(submission_id, _cache=self.m_time)

    def load_journal(self, journal_id: int) -> Optional[Entry]:
        return self._load_journal_cached(journal_id, _cache=self.m_time)

    def load_prev_next(self, table: str, item_id: int) -> tuple[int, int]:
        return self._load_prev_next_cached(table, item_id, _cache=self.m_time)

    def load_search(self, table: str, query: str, sort: str, order: str, *, force: bool = False):
        return self._load_search_cached(table, query, sort, order, force=force, _cache=self.m_time)

    def load_files_folder(self) -> Path:
        return self._load_files_folder_cached(_cache=self.m_time)

    def load_info(self) -> tuple[int, int, int, str]:
        return self._load_info_cached(_cache=self.m_time)

    def load_user_uncached(self, user: str) -> Optional[Entry]:
        return self._load_user_cached.__wrapped__(user)

    def load_user_stats_uncached(self, user: str) -> dict[str, int]:
        return self._load_user_stats_cached.__wrapped__(user)

    def load_submission_uncached(self, submission_id: int) -> Optional[Entry]:
        return self._load_submission_cached.__wrapped__(submission_id)

    def load_submission_files_uncached(self, submission_id: int) -> tuple[Optional[Path], Optional[Path]]:
        return self._load_submission_files_cached.__wrapped__(submission_id)

    def load_journal_uncached(self, journal_id: int) -> Optional[Entry]:
        return self._load_journal_cached.__wrapped__(journal_id)

    def load_prev_next_uncached(self, table: str, item_id: int) -> tuple[int, int]:
        return self._load_prev_next_cached.__wrapped__(table, item_id)

    def load_search_uncached(self, table: str, query: str, sort: str, order: str, *, force: bool = False):
        return self._load_search_cached.__wrapped__(table, query, sort, order, force=force)

    def load_files_folder_uncached(self) -> Path:
        return self._load_files_folder_cached.__wrapped__()

    def load_info_uncached(self) -> tuple[int, int, int, str]:
        return self._load_info_cached.__wrapped__()
