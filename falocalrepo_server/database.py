from collections import namedtuple
from datetime import datetime
from functools import lru_cache
from os import PathLike
from pathlib import Path
from re import match
from re import split
from re import sub
from sqlite3 import Cursor, ProgrammingError
from sqlite3 import Row
from types import GenericAlias
from typing import Any
from typing import Callable
from typing import TypeVar
from typing import TypedDict
from typing import get_origin

from chardet import detect as detect_encoding
from falocalrepo_database import Database as FADatabase
from falocalrepo_database import Table
from falocalrepo_database.tables import CommentsColumns
from falocalrepo_database.tables import JournalsColumns
from falocalrepo_database.tables import SubmissionsColumns
from falocalrepo_database.tables import UsersColumns
from falocalrepo_database.tables import comments_table
from falocalrepo_database.tables import journals_table
from falocalrepo_database.tables import submissions_table
from falocalrepo_database.tables import users_table
from falocalrepo_database.util import clean_username
from filetype import get_type
from filetype import guess_mime
from orjson import dumps
from orjson import loads

from falocalrepo_server.functions import bbcode_to_html
from falocalrepo_server.functions import clean_html
from falocalrepo_server.functions import prepare_html

R = TypeVar("R")
SearchResults = namedtuple(
    "SearchResults",
    [
        "rows",
        "column_id",
        "columns_table",
        "columns_results",
        "columns_lists",
        "sort",
        "order",
    ],
)

default_sort: dict[str, str] = {
    submissions_table: "date",
    journals_table: "date",
    users_table: "username",
    comments_table: "date",
}
default_order: dict[str, str] = {
    submissions_table: "desc",
    journals_table: "desc",
    users_table: "asc",
    comments_table: "desc",
}


class Settings(TypedDict):
    view: dict[str, str]
    limit: dict[str, int]
    sort: dict[str, str]
    order: dict[str, str]


@lru_cache
def clean_username_cached(username: str) -> str:
    return clean_username(username)


def format_value(value: str, *, substring: bool = False) -> str:
    value = sub(r"(?<!\\)((?:\\\\)+)?([%_^$])", r"\1\\\2", m.group(1)) if (m := match(r'^"(.*)"$', value)) else value
    value = value.lstrip("^") if match(r"^[%^].*", value) else "%" + value if substring else value
    value = value.rstrip("$") if match(r".*(?<!\\)((?:\\\\)+)?[%$]$", value) else value + "%" if substring else value
    return value


def query_to_sql(
    query: str,
    default_field: str,
    available_columns: list[str],
    substring_columns: list[str] = None,
    lower_columns: list[str] = None,
    aliases: dict[str, str] = None,
    score: bool = False,
) -> tuple[str, list[str]]:
    if not query:
        return "", []
    substring_columns, aliases = substring_columns or [], aliases or {}
    sql_elements: list[str] = []
    values: list[str] = []

    query = sub(r"(^[&| ]+|((?<!\\)[&|]| )+$)", "", query)
    query = sub(r"( *[&|])+(?= *[&|] *[@()])", "", query)

    field, prev = default_field.lower(), ""
    exact: bool = False
    like: bool = default_field in substring_columns
    negation: bool = False
    comparison: int = 0
    tokens: list[str] = [
        t
        for t in split(r'((?<!\\)"(?:[^"]|(?<=\\)")*"|(?<!\\)(?:[()&|]|%=|[=!]=|[<>]=?|!)|\s+)', query)
        if t and t.strip()
    ]
    for token in tokens:
        if token == prev:
            continue
        elif token == "%=":
            exact, like, negation, comparison = False, True, False, 0
            continue
        elif token == "==":
            exact, like, negation, comparison = True, False, False, 0
            continue
        elif token == "!=":
            exact, like, negation, comparison = True, False, True, 0
            continue
        elif token == ">":
            exact, like, negation, comparison = False, False, False, 1
            continue
        elif token == ">=":
            exact, like, negation, comparison = True, False, False, 1
            continue
        elif token == "<":
            exact, like, negation, comparison = False, False, False, -1
            continue
        elif token == "<=":
            exact, like, negation, comparison = True, False, False, -1
            continue
        elif token == "!":
            negation = True
            continue
        elif token == "&":
            if prev in ("", "&", "|", "("):
                continue
            sql_elements.append("and" if not score else "*")
            negation = False
        elif token == "|":
            if prev in ("", "&", "|", "("):
                continue
            sql_elements.append("or" if not score else "+")
            negation = False
        elif token in ("(", ")"):
            if token == ")" and prev == "(":
                sql_elements.pop()
                prev = token
                continue
            elif token == ")" and prev in ("&", "|"):
                sql_elements.pop()
            sql_elements.append("and") if token == "(" and prev not in ("", "&", "|", "(") else None
            sql_elements.append(token)
            negation = False
        elif m := match(r"^@(\w+)$", token):
            field = m.group(1).lower()
            if field not in available_columns and field not in aliases:
                field = default_field
            exact, like, comparison = False, field in substring_columns, 0
            continue
        elif token:
            sql_elements.append("and" if not score else "*") if prev not in ("", "&", "|", "(") else None
            field_: str = aliases.get(field, field)
            if (exact or comparison) and field in lower_columns:
                field_ = f"lower({field_})"
            if comparison > 0:
                sql_elements.append(f"({field_} {'<' if negation else '>'}{'=' if exact != negation else ''} ?)")
            elif comparison < 0:
                sql_elements.append(f"({field_} {'>' if negation else '<'}{'=' if exact != negation else ''} ?)")
            elif exact:
                sql_elements.append(f"({field_} {'!=' if negation else '='} ?)")
            else:
                sql_elements.append(f"({field_}{' not' * negation} like ? escape '\\')")
            values.append(format_value(token, substring=False if exact or comparison else like))
            negation = False
        else:
            continue
        prev = token

    sql = " ".join(sql_elements)

    if sql.count("(") != sql.count(")"):
        raise ProgrammingError("Unmatched parentheses")

    return sql, values


def replies_count(comment: dict[str, Any]) -> int:
    return sum(map(replies_count, comment["REPLIES"]), len(comment["REPLIES"]))


def set_replies_count(comment: dict[str, Any]) -> dict[str, Any]:
    return comment | {
        "REPLIES": list(map(set_replies_count, comment["REPLIES"])),
        "REPLIES_COUNT": replies_count(comment),
    }


# noinspection DuplicatedCode,PyProtectedMember
class Database:
    def __init__(self, path: str | PathLike | None = None, use_cache: bool = True, max_results: int | None = None):
        self.path: Path | None = Path(path) if path else None
        self.use_cache: bool = use_cache
        self.max_results: int | None = max_results
        self.database: FADatabase | None = None
        self.m_time: int = self.path.stat().st_mtime_ns

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def connect(self, path: str | PathLike | None = None):
        if self.database and self.database.is_open:
            return
        del self.database
        if path:
            self.path = self.path
        self.database = FADatabase(self.path)
        return self.database

    def close(self):
        if self.database and self.database.is_open:
            self.database.close()
        del self.database
        self.database = None

    def call_cached_method(self, func: Callable[..., R], *args: Any) -> R:
        # noinspection PyUnresolvedReferences
        return func(*args) if self.use_cache else func.__wrapped__(self, *args)

    def clear_cache(self):
        self._clear_cache(self.path.stat().st_mtime_ns)

    @lru_cache(1)
    def _clear_cache(self, m_time: int):
        self.m_time = m_time
        for attr_name in dir(self):
            if hasattr(getattr(self, attr_name), "cache_clear"):
                self.__getattribute__(attr_name).cache_clear()

    @lru_cache
    def _settings(self) -> Settings | None:
        settings: dict[str, dict[str, str | int]] = loads(self.database.settings["SERVER.SEARCH"] or "{}")

        if not settings:
            return None

        return {
            "view": settings["view"],
            "limit": settings["limit"],
            "sort": settings["sort"],
            "order": settings["order"],
        }

    @lru_cache
    def _stats(self) -> tuple[int, int, int, int, datetime]:
        return (
            len(self.database.users),
            len(self.database.submissions),
            len(self.database.journals),
            len(self.database.comments),
            (
                event["TIME"]
                if (event := next(self.database.history.select(order=["time desc"], limit=1), None))
                else None
            ),
        )

    @lru_cache
    def _bbcode(self) -> bool:
        return bool(self.database.settings.bbcode)

    @lru_cache
    def _search(
        self,
        table_name: str,
        query: str,
        sort: str,
        order: str,
        limit: int | None,
    ) -> SearchResults:
        cols_results: list[str]
        cols_any: list[str]
        cols_substring: list[str]
        cols_lower: list[str]
        cols_aliases: dict[str, str]
        default_column: str = "any"
        sort = sort or default_sort[table_name]
        order = order if order in ("asc", "desc") else default_order[table_name]
        actual_sort: str = sort
        table: Table

        if (table_name := table_name.upper()) == users_table.upper():
            default_column = UsersColumns.USERNAME.name
            cols_any = [UsersColumns.USERNAME.name, UsersColumns.USERPAGE.name]
            cols_substring = [
                UsersColumns.USERNAME.name,
                UsersColumns.FOLDERS.name,
                UsersColumns.USERPAGE.name,
            ]
            cols_results = [
                UsersColumns.USERNAME.name,
                UsersColumns.FOLDERS.name,
                UsersColumns.ACTIVE.name,
            ]
            cols_lower = [
                UsersColumns.USERNAME.name,
                UsersColumns.FOLDERS.name,
            ]
            cols_aliases = {
                UsersColumns.USERNAME.name: f"lower({UsersColumns.USERNAME.name})",
                UsersColumns.FOLDERS.name: f"lower({UsersColumns.FOLDERS.name})",
            }
            table = self.database.users
        elif table_name == submissions_table.upper():
            cols_any = [
                SubmissionsColumns.AUTHOR.name,
                SubmissionsColumns.DATE.name,
                SubmissionsColumns.TITLE.name,
                SubmissionsColumns.CATEGORY.name,
                SubmissionsColumns.TAGS.name,
                SubmissionsColumns.SPECIES.name,
                SubmissionsColumns.DESCRIPTION.name,
            ]
            cols_substring = [
                SubmissionsColumns.AUTHOR.name,
                SubmissionsColumns.TITLE.name,
                SubmissionsColumns.DATE.name,
                SubmissionsColumns.DESCRIPTION.name,
                SubmissionsColumns.FOOTER.name,
                SubmissionsColumns.TAGS.name,
                SubmissionsColumns.CATEGORY.name,
                SubmissionsColumns.SPECIES.name,
                SubmissionsColumns.FILEURL.name,
                SubmissionsColumns.FILEEXT.name,
                SubmissionsColumns.FAVORITE.name,
                SubmissionsColumns.MENTIONS.name,
                SubmissionsColumns.FOLDER.name,
                "lower",
                "keywords",
                "message",
                "filename",
            ]
            cols_results = [
                SubmissionsColumns.ID.name,
                SubmissionsColumns.AUTHOR.name,
                SubmissionsColumns.DATE.name,
                SubmissionsColumns.TITLE.name,
                SubmissionsColumns.FILEEXT.name,
            ]
            cols_lower = [
                SubmissionsColumns.AUTHOR.name,
                SubmissionsColumns.TITLE.name,
                SubmissionsColumns.DATE.name,
                SubmissionsColumns.DESCRIPTION.name,
                SubmissionsColumns.FOOTER.name,
                SubmissionsColumns.TAGS.name,
                SubmissionsColumns.CATEGORY.name,
                SubmissionsColumns.SPECIES.name,
                SubmissionsColumns.GENDER.name,
                SubmissionsColumns.RATING.name,
                SubmissionsColumns.TYPE.name,
                SubmissionsColumns.FILEURL.name,
                SubmissionsColumns.FILEEXT.name,
                SubmissionsColumns.FAVORITE.name,
                SubmissionsColumns.MENTIONS.name,
                SubmissionsColumns.FOLDER.name,
                "lower",
                "keywords",
                "message",
                "filename",
            ]
            cols_aliases = {
                SubmissionsColumns.AUTHOR.name: f"replace({SubmissionsColumns.AUTHOR.name}, '_', '')",
                "lower": f"replace({SubmissionsColumns.AUTHOR.name}, '_', '')",
                "keywords": SubmissionsColumns.TAGS.name,
                "message": SubmissionsColumns.DESCRIPTION.name,
                "filename": SubmissionsColumns.FILEURL.name,
            }
            table = self.database.submissions
            actual_sort = SubmissionsColumns.ID.name if sort.lower() == SubmissionsColumns.DATE.name.lower() else sort
        elif table_name == journals_table.upper():
            cols_any = [
                JournalsColumns.AUTHOR.name,
                JournalsColumns.DATE.name,
                JournalsColumns.TITLE.name,
                JournalsColumns.CONTENT.name,
            ]
            cols_substring = [
                JournalsColumns.AUTHOR.name,
                JournalsColumns.TITLE.name,
                JournalsColumns.DATE.name,
                JournalsColumns.CONTENT.name,
                JournalsColumns.HEADER.name,
                JournalsColumns.FOOTER.name,
                JournalsColumns.MENTIONS.name,
                "lower",
                "message",
            ]
            cols_results = [
                JournalsColumns.ID.name,
                JournalsColumns.AUTHOR.name,
                JournalsColumns.DATE.name,
                JournalsColumns.TITLE.name,
            ]
            cols_lower = [
                JournalsColumns.AUTHOR.name,
                JournalsColumns.TITLE.name,
                JournalsColumns.DATE.name,
                JournalsColumns.CONTENT.name,
                JournalsColumns.HEADER.name,
                JournalsColumns.FOOTER.name,
                JournalsColumns.MENTIONS.name,
                "lower",
                "message",
            ]
            cols_aliases = {
                JournalsColumns.AUTHOR.name: f"replace({JournalsColumns.AUTHOR.name}, '_', '')",
                "lower": f"replace({JournalsColumns.AUTHOR.name}, '_', '')",
                "message": JournalsColumns.CONTENT.name,
            }
            table = self.database.journals
            actual_sort = JournalsColumns.ID.name if sort.lower() == JournalsColumns.DATE.name.lower() else sort
        elif table_name == comments_table:
            cols_any = [
                CommentsColumns.AUTHOR.name,
                CommentsColumns.TEXT.name,
            ]
            cols_substring = [
                CommentsColumns.AUTHOR.name,
                CommentsColumns.DATE.name,
                CommentsColumns.TEXT.name,
                "lower",
                "message",
            ]
            cols_results = [
                CommentsColumns.ID.name,
                CommentsColumns.PARENT_TABLE.name,
                CommentsColumns.PARENT_ID.name,
                CommentsColumns.REPLY_TO.name,
                CommentsColumns.AUTHOR.name,
                CommentsColumns.DATE.name,
                CommentsColumns.TEXT.name,
            ]
            cols_lower = [
                CommentsColumns.PARENT_TABLE.name,
                CommentsColumns.AUTHOR.name,
                CommentsColumns.DATE.name,
                CommentsColumns.TEXT.name,
                "lower",
                "message",
            ]
            cols_aliases = {
                CommentsColumns.AUTHOR.name: f"replace({CommentsColumns.AUTHOR.name}, '_', '')",
                "lower": f"replace({CommentsColumns.AUTHOR.name}, '_', '')",
                "message": CommentsColumns.TEXT.name,
            }
            table = self.database.comments
        else:
            raise KeyError(f"Unknown table {table_name!r}")

        col_id: str = table.key.name
        cols_table: list[str] = [c.name.lower() for c in table.columns]
        cols_any = [c.lower() for c in cols_any]
        cols_substring = [c.lower() for c in cols_substring]
        cols_lower = [c.lower() for c in cols_lower]
        cols_results = [c.lower() for c in cols_results]
        cols_list: list[str] = [
            c.name.lower()
            for c in table.columns
            if (get_origin(c.type) if type(c.type) is GenericAlias else c.type) in (list, set)
        ]
        cols_aliases = {c.lower(): a for c, a in cols_aliases.items()}
        if cols_any:
            cols_aliases["any"] = f"({'||'.join(cols_any)})"
            cols_substring.append("any")
        sort = sort if sort.lower() in cols_table else default_sort[table_name]

        sql, values = query_to_sql(
            query.lower(),
            default_column.lower(),
            cols_table,
            cols_substring,
            cols_lower,
            cols_aliases,
            score=sort.lower() == "relevance",
        )

        cursor: Cursor

        if sort.lower() == "relevance":
            cursor = table.select_sql(
                f"RELEVANCE > 0",
                values,
                [*cols_results, f"({sql if sql else 1}) as RELEVANCE"],
                [f"{actual_sort} {order}", f"{default_sort[table_name]} {default_order[table_name]}"],
                limit,
            ).cursor
            cols_results.append("RELEVANCE")
        else:
            cursor = table.select_sql(sql, values, cols_results, [f"{actual_sort} {order}"], limit).cursor

        cursor.row_factory = Row
        return SearchResults(
            cursor.fetchall(),
            col_id,
            cols_table + ["RELEVANCE"],
            cols_results,
            cols_list,
            sort,
            order,
        )

    @lru_cache
    def _user(self, username: str):
        bbcode = self.bbcode()
        user = self.database.users[clean_username(username)]
        if user:
            user["USERPAGE"] = prepare_html(user["USERPAGE"], bbcode)
            user["USERPAGE_BBCODE"] = user["USERPAGE"].strip() or None if bbcode else None
        return user

    @lru_cache
    def _user_stats(self, username: str) -> dict[str, int]:
        username = clean_username(username)
        stats: dict[str, int] = {}
        cur = self.database.execute(
            "select FOLDER, count(*) from SUBMISSIONS where replace(lower(AUTHOR), '_', '') = ? group by FOLDER",
            (username,),
        )
        stats |= dict(cur.fetchall())
        cur = self.database.execute(
            "select count(*) from JOURNALS where replace(lower(AUTHOR), '_', '') = ?", (username,)
        )
        stats["journals"] = cur.fetchone()[0]
        cur = self.database.execute(
            "select count(*) from SUBMISSIONS where FAVORITE like '%|' || ? || '|%'",
            (username,),
        )
        stats["favorites"] = cur.fetchone()[0]
        cur = self.database.execute(
            "select count(*) from COMMENTS where replace(lower(AUTHOR), '_', '') = ?",
            (username,),
        )
        stats["comments"] = cur.fetchone()[0]
        return stats

    @lru_cache
    def _submission(self, submission_id: int) -> dict[str, Any] | None:
        bbcode = self.bbcode()
        submission = self.database.submissions[submission_id]
        if submission:
            submission["DESCRIPTION_BBCODE"] = submission["DESCRIPTION"].strip() or None if bbcode else None
            submission["FOOTER_BBCODE"] = submission["FOOTER"].strip() or None if bbcode else None
            submission["DESCRIPTION"] = prepare_html(submission["DESCRIPTION"], bbcode)
            submission["FOOTER"] = prepare_html(submission["FOOTER"], bbcode)
        return submission

    @lru_cache
    def _submission_files(self, submission_id: int) -> tuple[list[Path] | None, Path | None]:
        return self.database.submissions.get_submission_files(submission_id)

    @lru_cache
    def _submission_files_text(self, *files: Path) -> list[str | None]:
        return [
            (
                bbcode_to_html(f.read_text(detect_encoding(f.read_bytes())["encoding"], "ignore"))
                if f.suffix == ".txt" and f.is_file()
                else ""
            )
            for f in files
        ]

    @lru_cache
    def _submission_files_mime(self, *files: Path) -> list[str | None]:
        return [
            guess_mime(f) if f.is_file() else t.mime if (t := get_type(ext=f.suffix.strip("."))) else None
            for f in files
        ]

    @lru_cache
    def _submission_comments(self, submission_id: int) -> list[dict[str, Any]]:
        bbcode = self.bbcode()
        comments = self.database.comments.get_comments(submissions_table, submission_id)
        comments = self.database.comments._make_comments_tree([c for c in comments if not c["REPLY_TO"]], comments)
        return [
            set_replies_count(c | {"TEXT": bbcode_to_html(c["TEXT"]) if bbcode else clean_html(c["TEXT"])})
            for c in comments
        ]

    @lru_cache
    def _submission_prev_next(
        self,
        submission_id: int,
        submission_author: str,
        submission_folder: str,
    ) -> tuple[str | int | None, str | int | None]:
        cur = self.database.execute(
            """
        select *
        from (select ID from SUBMISSIONS where ID > ? and AUTHOR = ? and FOLDER = ? order by ID limit 1)
        
        union
        
        select *
        from (select ID from SUBMISSIONS where ID < ? and AUTHOR = ? and FOLDER = ? order by ID desc limit 1);
        """,
            [submission_id, submission_author, submission_folder, submission_id, submission_author, submission_folder],
        )
        if not (ids := sorted(i for [i] in cur.fetchall())):
            return None, None
        return ids[0] if ids[0] < submission_id else None, ids[-1] if ids[-1] > submission_id else None

    @lru_cache
    def _journal(self, journal_id: int) -> dict[str, Any] | None:
        bbcode = self.bbcode()
        journal = self.database.journals[journal_id]
        if journal:
            journal["CONTENT_BBCODE"] = journal["CONTENT"].strip() or None if bbcode else None
            journal["FOOTER_BBCODE"] = journal["FOOTER"].strip() or None if bbcode else None
            journal["CONTENT"] = prepare_html(journal["CONTENT"], bbcode)
            journal["FOOTER"] = prepare_html(journal["FOOTER"], bbcode)
        return journal

    @lru_cache
    def _journal_comments(self, journal_id: int) -> list[dict[str, Any]]:
        bbcode = self.bbcode()
        comments = self.database.comments.get_comments(journals_table, journal_id)
        comments = self.database.comments._make_comments_tree([c for c in comments if not c["REPLY_TO"]], comments)
        return [
            set_replies_count(c | {"TEXT": bbcode_to_html(c["TEXT"]) if bbcode else clean_html(c["TEXT"])})
            for c in comments
        ]

    @lru_cache
    def _journal_prev_next(self, journal_id: int, journal_author: str) -> tuple[str | int | None, str | int | None]:
        cur = self.database.execute(
            """
        select *
        from (select ID from JOURNALS where ID > ? and AUTHOR = ? order by ID limit 1)
        
        union
        
        select *
        from (select ID from JOURNALS where ID < ? and AUTHOR = ? order by ID desc limit 1);
        """,
            [journal_id, journal_author, journal_id, journal_author],
        )
        if not (ids := sorted(i for [i] in cur.fetchall())):
            return None, None
        return ids[0] if ids[0] < journal_id else None, ids[-1] if ids[-1] > journal_id else None

    def settings(self) -> Settings | None:
        return self.call_cached_method(self._settings)

    def save_settings(self, settings: Settings):
        if self._settings.__wrapped__(self) != settings:
            self.database.settings["SERVER.SEARCH"] = dumps(settings).decode("utf-8")
            self.database.commit()
            self._settings.cache_clear()

    def stats(self) -> tuple[int, int, int, int, datetime]:
        return self.call_cached_method(self._stats)

    def bbcode(self) -> bool:
        return self.call_cached_method(self._bbcode)

    def search(self, table: str, query: str, sort: str, order: str) -> SearchResults:
        table, query, sort, order, limit = (
            table.lower().strip(),
            query.lower().strip(),
            sort.lower().strip(),
            order.lower().strip(),
            self.max_results + 1 if self.max_results else 0,
        )
        if self.max_results:
            return self.call_cached_method(self._search, table, query, sort, order, limit)
        elif order == "desc":
            return self.call_cached_method(self._search, table, query, sort, order, limit)
        else:
            results = self.call_cached_method(self._search, table, query, sort, "desc", limit)
            return SearchResults(
                list(reversed(results.rows)),
                results.column_id,
                results.columns_table,
                results.columns_results,
                results.columns_lists,
                results.sort,
                order,
            )

    def user(self, username: str) -> dict[str, Any] | None:
        return self.call_cached_method(self._user, username)

    def user_stats(self, username: str) -> dict[str, int]:
        return self.call_cached_method(self._user_stats, username)

    def submission(self, submission_id: int) -> dict[str, Any] | None:
        return self.call_cached_method(self._submission, submission_id)

    def submission_files(self, submission_id: int) -> tuple[list[Path] | None, Path | None]:
        return self.call_cached_method(self._submission_files, submission_id)

    def submission_files_text(self, *files: Path) -> list[str | None]:
        return self.call_cached_method(self._submission_files_text, *files)

    def submission_files_mime(self, *files: Path) -> list[str | None]:
        return self.call_cached_method(self._submission_files_mime, *files)

    def submission_comments(self, submission_id: int) -> list[dict[str, Any]]:
        return self.call_cached_method(self._submission_comments, submission_id)

    def submission_prev_next(
        self,
        submission_id: int,
        submission_author: str,
        submission_folder: str,
    ) -> tuple[int | None, int | None]:
        return self.call_cached_method(self._submission_prev_next, submission_id, submission_author, submission_folder)

    def journal(self, journal_id: int) -> dict[str, Any] | None:
        return self.call_cached_method(self._journal, journal_id)

    def journal_comments(self, journal_id: int) -> list[dict[str, Any]]:
        return self.call_cached_method(self._journal_comments, journal_id)

    def journal_prev_next(self, journal_id: int, journal_author: str) -> tuple[int | None, int | None]:
        return self.call_cached_method(self._journal_prev_next, journal_id, journal_author)
