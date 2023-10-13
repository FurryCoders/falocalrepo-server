from datetime import datetime
from functools import cache
from json import dumps
from json import loads
from logging import Logger
from os import W_OK
from os import access
from pathlib import Path
from re import match
from re import split
from re import sub
from sqlite3 import DatabaseError

from falocalrepo_database import Column
from falocalrepo_database import Database as _Database
from falocalrepo_database import Table
from falocalrepo_database.selector import Selector
from falocalrepo_database.selector import SelectorBuilder as Sb
from falocalrepo_database.tables import JournalsColumns
from falocalrepo_database.tables import SubmissionsColumns
from falocalrepo_database.tables import UsersColumns
from falocalrepo_database.tables import journals_table
from falocalrepo_database.tables import submissions_table
from falocalrepo_database.tables import users_table
from falocalrepo_database.util import compare_version, clean_username as _clean_username

default_sort: dict[str, str] = {submissions_table: "date", journals_table: "date", users_table: "username"}
default_order: dict[str, str] = {submissions_table: "desc", journals_table: "desc", users_table: "asc"}


@cache
def clean_username(username: str) -> str:
    return _clean_username(username)


def format_value(value: str, *, like: bool = False) -> str:
    value = sub(r"(?<!\\)((?:\\\\)+)?([%_^$])", r"\1\\\2", m.group(1)) if (m := match(r'^"(.*)"$', value)) else value
    value = value.lstrip("^") if match(r"^[%^].*", value) else "%" + value if like else value
    value = value.rstrip("$") if match(r".*(?<!\\)((?:\\\\)+)?[%$]$", value) else value + "%" if like else value
    return value


def query_to_sql(query: str, default_field: str, likes: list[str] = None, aliases: dict[str, str] = None,
                 score: bool = False) -> tuple[str, list[str]]:
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
            sql_elements.append("and" if not score else "*")
        elif elem == "|":
            sql_elements.append("or" if not score else "+")
        elif elem in ("(", ")"):
            sql_elements.append("and") if elem == "(" and prev not in ("", "&", "|", "(") else None
            sql_elements.append(elem)
        elif elem:
            not_, elem = match(r"^(!)?(.*)$", elem).groups()
            if not elem:
                continue
            sql_elements.append("and" if not score else "*") if prev not in ("", "&", "|", "(") else None
            sql_elements.append(f"({aliases.get(field, field)}{' not' * bool(not_)} like ? escape '\\')")
            values.append(format_value(elem, like=field in likes))
        prev = elem

    return " ".join(sql_elements), values


class Database(_Database):
    def __init__(self, database_path: Path, logger: Logger):
        _Database.check_connection(database_path)
        super().__init__(database_path, read_only=not access(database_path, W_OK), check_version=False)
        if not self.is_formatted:
            raise DatabaseError("Database not formatted")
        elif err := compare_version(self.version, patch=False):
            raise err
        self.logger: Logger = logger

    @cache
    def clear_cache(self, _m_time: float = None):
        self.use_bbcode.cache_clear()
        self._load_user_cached.cache_clear()
        self._load_user_stats_cached.cache_clear()
        self._load_submission_cached.cache_clear()
        self._load_submission_files_cached.cache_clear()
        self._load_submission_comments_cached.cache_clear()
        self._load_journal_cached.cache_clear()
        self._load_journal_comments_cached.cache_clear()
        self._load_prev_next_cached.cache_clear()
        self._load_search_cached.cache_clear()
        self._load_search_aux.cache_clear()
        self._load_files_folder_cached.cache_clear()
        self._load_info_cached.cache_clear()
        self.logger.info(f"Clearing cache for new m_time {datetime.fromtimestamp(_m_time)}")

    @property
    def m_time(self) -> float:
        return self.path.stat().st_mtime

    @cache
    def use_bbcode(self) -> bool:
        return self.settings.bbcode

    @cache
    def _load_user_cached(self, user: str) -> dict | None:
        return self.users[user]

    @cache
    def _load_user_stats_cached(self, user: str) -> dict[str, int]:
        return {
            "gallery": self.submissions.select(
                Sb() & [Sb("replace(lower(author), '_', '')").__eq__(user), Sb("folder").__eq__("gallery")],
                columns=[Column("count(ID)", int)]
            ).cursor.fetchone()[0],
            "scraps": self.submissions.select(
                Sb() & [Sb("replace(lower(author), '_', '')").__eq__(user), Sb("folder").__eq__("scraps")],
                columns=[Column("count(ID)", int)]
            ).cursor.fetchone()[0],
            "favorites": self.submissions.select(
                Sb("favorite") % f"%|{user}|%", columns=[Column("count(ID)", int)]
            ).cursor.fetchone()[0],
            "mentions": self.submissions.select(
                Sb("mentions") % f"%|{user}|%", columns=[Column("count(ID)", int)]
            ).cursor.fetchone()[0],
            "journals": self.journals.select(
                Sb("replace(lower(author), '_', '')").__eq__(user), columns=[Column("count(ID)", int)]
            ).cursor.fetchone()[0]
        }

    @cache
    def _load_submission_cached(self, submission_id: int) -> dict | None:
        return self.submissions[submission_id]

    @cache
    def _load_submission_files_cached(self, submission_id: int
                                      ) -> tuple[list[Path] | None, Path | None]:
        return self.submissions.get_submission_files(submission_id)

    @cache
    def _load_submission_comments_cached(self, submission_id: int) -> list[dict]:
        return self.comments.get_comments_tree(submissions_table, submission_id)

    @cache
    def _load_journal_cached(self, journal_id: int) -> dict | None:
        return self.journals[journal_id]

    @cache
    def _load_journal_comments_cached(self, journal_id: int) -> list[dict]:
        return self.comments.get_comments_tree(journals_table, journal_id)

    @cache
    def _load_prev_next_cached(self, table: str, item_id: int | str) -> tuple[int, int]:
        db_table: Table = self[table]

        if table in (submissions_table, journals_table):
            if not (item := db_table[item_id]):
                return 0, 0

            query: Selector = Sb("AUTHOR").__eq__(item["AUTHOR"])
            query = Sb() & [query, Sb("FOLDER").__eq__(item["FOLDER"])] if table.upper() == submissions_table else query
            return db_table.select(
                query,
                columns=[Column("LAG(ID, 1, 0) over (order by ID)", int),
                         Column("LEAD(ID, 1, 0) over (order by ID)", int)],
                order=[f"ABS(ID - {item_id})"],
                limit=1
            ).cursor.fetchone()
        elif table == users_table:
            if not (item := db_table[item_id]):
                return 0, 0

            query1: Selector = Sb("USERNAME").__gt__(item["USERNAME"])
            query2: Selector = Sb("USERNAME").__lt__(item["USERNAME"])
            return (
                next(db_table.select(query1, columns=["USERNAME"], order=["USERNAME ASC"], limit=1).cursor, [0])[0],
                next(db_table.select(query2, columns=["USERNAME"], order=["USERNAME DESC"], limit=1).cursor, [0])[0]
            )
        else:
            raise KeyError(f"Unknown table {table!r}")

    @cache
    def _load_search_cached(self, table: str, query: str, sort: str, order: str):
        cols_results: list[Column]
        default_field: str = "any"
        sort = sort or default_sort[table]
        order = order or default_order[table]
        db_table: Table

        if (table := table.upper()) == submissions_table.upper():
            cols_results = [SubmissionsColumns.ID, SubmissionsColumns.AUTHOR,
                            SubmissionsColumns.DATE, SubmissionsColumns.TITLE,
                            SubmissionsColumns.FILEEXT]
            db_table = self.submissions
        elif table == journals_table.upper():
            cols_results = [JournalsColumns.ID, JournalsColumns.AUTHOR,
                            JournalsColumns.DATE, JournalsColumns.TITLE]
            db_table = self.journals
        else:
            default_field = "username"
            cols_results = [UsersColumns.USERNAME, UsersColumns.FOLDERS, UsersColumns.ACTIVE]
            db_table = self.users

        cols_table: list[str] = [c.name for c in db_table.columns]
        cols_list: list[str] = [c.name for c in db_table.columns if c.type in (list, set)]
        col_id: Column = db_table.key

        sql, values = query_to_sql(
            query,
            default_field,
            [*map(str.lower,
                  {*cols_table, "any", "keywords", "message", "filename"} -
                  {"ID", "FILESAVED", "USERUPDATE", "ACTIVE"})],
            {"author": "replace(author, '_', '')",
             "lower": "replace(author, '_', '')",
             "keywords": "tags",
             "message": "description",
             "filename": "fileurl",
             "any": "(" +
                    '||'.join(set(cols_table) - {'FAVORITE', 'FILESAVED', 'USERUPDATE', 'ACTIVE'}) +
                    ")"},
            score=sort.lower() == "relevance")

        results: list[dict]
        if sort.lower() == "relevance":
            results = [
                dict(zip([c.name for c in cols_results] + ["RELEVANCE"], s)) for s in
                db_table.select_sql(f"RELEVANCE > 0", values,
                                    columns=[*cols_results, Column(f"({sql if sql else 1}) as RELEVANCE", int)],
                                    order=[f"{sort} {order}", f"{default_sort[table]} {default_order[table]}"]).tuples]
        else:
            results = list(db_table.select_sql(sql, values, columns=cols_results, order=[f"{sort} {order}"]))
        return (
            results,
            cols_table + ["RELEVANCE"],
            [c.name for c in cols_results] + (["RELEVANCE"] if sort == "relevance" else []),
            cols_list,
            col_id.name,
            sort,
            order
        )

    @cache
    def _load_files_folder_cached(self) -> Path:
        return self.settings.files_folder.resolve()

    @cache
    def _load_info_cached(self) -> tuple[int, int, int, str]:
        return len(self.users), len(self.submissions), len(
            self.journals), self.version

    def save_settings(self, name: str, settings: dict):
        if self.read_only:
            return

        self.settings[f"SERVER.{name}"] = dumps(settings)
        self.commit()

    def load_settings(self, name: str) -> dict:
        return loads(self.settings[f"SERVER.{name}"] or "{}")

    def load_user(self, user: str) -> dict | None:
        self.clear_cache(self.m_time)
        return self._load_user_cached(user)

    def load_user_stats(self, user: str) -> dict[str, int]:
        self.clear_cache(self.m_time)
        return self._load_user_stats_cached(user)

    def load_submission(self, submission_id: int) -> dict | None:
        self.clear_cache(self.m_time)
        return self._load_submission_cached(submission_id)

    def load_submission_files(self, submission_id: int) -> tuple[list[Path] | None, Path | None]:
        self.clear_cache(self.m_time)
        return self._load_submission_files_cached(submission_id)

    def load_submission_comments(self, submission_id: int) -> list[dict]:
        self.clear_cache(self.m_time)
        return self._load_submission_comments_cached(submission_id)

    def load_journal(self, journal_id: int) -> dict | None:
        self.clear_cache(self.m_time)
        return self._load_journal_cached(journal_id)

    def load_journal_comments(self, journal_id: int) -> list[dict]:
        self.clear_cache(self.m_time)
        return self._load_journal_comments_cached(journal_id)

    def load_prev_next(self, table: str, item_id: int | str) -> tuple[int, int]:
        self.clear_cache(self.m_time)
        return self._load_prev_next_cached(table, item_id)

    @cache
    def _load_search_aux(self, table: str, query: str, sort: str, order: str):
        if order.startswith("asc"):
            return self._load_search_cached(table.lower(), query.lower(), sort.lower(), order.lower())
        else:
            results, *rest, _ = self._load_search_cached(table.lower(), query.lower(), sort.lower(), "asc")
            return list(reversed(results)), *rest, order

    def load_search(self, table: str, query: str, sort: str, order: str):
        self.clear_cache(self.m_time)
        return self._load_search_aux(table.lower(), query.lower(), sort.lower(), order.lower())

    def load_files_folder(self) -> Path:
        self.clear_cache(self.m_time)
        return self._load_files_folder_cached()

    def load_info(self) -> tuple[int, int, int, str]:
        self.clear_cache(self.m_time)
        return self._load_info_cached()

    def load_user_uncached(self, user: str) -> dict | None:
        return self._load_user_cached.__wrapped__(self, user)

    def load_user_stats_uncached(self, user: str) -> dict[str, int]:
        return self._load_user_stats_cached.__wrapped__(self, user)

    def load_submission_uncached(self, submission_id: int) -> dict | None:
        return self._load_submission_cached.__wrapped__(self, submission_id)

    def load_submission_comments_uncached(self, submission_id: int) -> list[dict]:
        return self._load_submission_comments_cached.__wrapped__(self, submission_id)

    def load_submission_files_uncached(self, submission_id: int) -> tuple[list[Path] | None, Path | None]:
        return self._load_submission_files_cached.__wrapped__(self, submission_id)

    def load_journal_uncached(self, journal_id: int) -> dict | None:
        return self._load_journal_cached.__wrapped__(self, journal_id)

    def load_journal_comments_uncached(self, journal_id: int) -> list[dict]:
        return self._load_journal_comments_cached.__wrapped__(self, journal_id)

    def load_prev_next_uncached(self, table: str, item_id: int | str) -> tuple[int, int]:
        return self._load_prev_next_cached.__wrapped__(self, table, item_id)

    def load_search_uncached(self, table: str, query: str, sort: str, order: str):
        return self._load_search_cached.__wrapped__(self, table, query, sort, order)

    def load_files_folder_uncached(self) -> Path:
        return self._load_files_folder_cached.__wrapped__(self, )

    def load_info_uncached(self) -> tuple[int, int, int, str]:
        return self._load_info_cached.__wrapped__(self, )
