from re import IGNORECASE
from re import Pattern
from re import compile as re_compile
from re import match
from re import sub

from bbcode import Parser as BBCodeParser
from bs4 import BeautifulSoup
from bs4.element import NavigableString
from bs4.element import Tag
from falocalrepo_database.util import clean_username


fa_link: Pattern = re_compile(r"(https?://)?(www.)?furaffinity.net", flags=IGNORECASE)
# noinspection SpellCheckingInspection
icons: list[str] = [
    "angel",
    "badhairday",
    "cd",
    "coffee",
    "cool",
    "crying",
    "derp",
    "dunno",
    "embarrassed",
    "evil",
    "gift",
    "huh",
    "lmao",
    "love",
    "nerd",
    "note",
    "oooh",
    "pleased",
    "rollingeyes",
    "sad",
    "sarcastic",
    "serious",
    "sleepy",
    "smile",
    "teeth",
    "tongue",
    "veryhappy",
    "whatever",
    "wink",
    "yelling",
    "zipped",
]


def flatten_comments(comments: list[dict]) -> list[dict]:
    return [*{c["ID"]: c for c in [r for c in comments for r in [c, *flatten_comments(c["REPLIES"])]]}.values()]


def comments_depth(comments: list[dict], depth: int = 0, root_comment: int = None) -> list[dict]:
    return [
        com
        | {
            "DEPTH": depth,
            "REPLIES": comments_depth(com.get("REPLIES", []), depth + 1, root_comment or com["ID"]),
            "ROOT": root_comment,
        }
        for com in comments
    ]


def prepare_comments(comments: list[dict], use_bbcode: bool) -> list[dict]:
    return [
        c | {"TEXT": bbcode_to_html(c["TEXT"]) if use_bbcode else clean_html(c["TEXT"])}
        for c in flatten_comments(comments_depth(comments, 0))
    ]


# noinspection SpellCheckingInspection
def bbcode_to_html(bbcode: str) -> str:
    def render_url(_tag_name, value: str, options: dict[str, str], _parent, _context) -> str:
        return f'<a class="auto_link named_url" href="{options.get("url", "#")}">{value}</a>'

    def render_color(_tag_name, value, options, _parent, _context) -> str:
        return f'<span class=bbcode style="color:{options.get("color", "inherit")};">{value}</span>'

    def render_quote(_tag_name, value: str, options: dict[str, str], _parent, _context) -> str:
        author: str = options.get("quote", "")
        author = f"<span class=bbcode_quote_name>{author} wrote:</span>" if author else ""
        return f'<span class="bbcode bbcode_quote">{author}{value}</span>'

    def render_tags(tag_name: str, value: str, options: dict[str, str], _parent, _context) -> str:
        if not options and tag_name.islower():
            return f"<{tag_name}>{value}</{tag_name}>"
        return f"[{tag_name} {' '.join(f'{k}={v}' if v else k for k, v in options.items())}]{value}"

    def render_tag(_tag_name, value: str, options: dict[str, str], _parent, _context) -> str:
        name, *classes = options["tag"].split(".")
        return f'<{name} class="{" ".join(classes)}">{value}</{name}>'

    # noinspection SpellCheckingInspection
    def parse_extra(page: BeautifulSoup) -> BeautifulSoup:
        child: NavigableString
        child_new: Tag
        has_match: bool = True
        while has_match:
            has_match = False
            for child in [c for e in page.select("*:not(a)") for c in e.children if isinstance(c, NavigableString)]:
                if m_ := match(r"(.*)(https?://(?:www\.)?((?:[\w/%#\[\]@*-]|[.,?!'()&~:;=](?! ))+))(.*)", child):
                    has_match = True
                    child_new = Tag(name="a", attrs={"class": f"auto_link_shortened", "href": m_[2]})
                    child_new.insert(0, m_[3].split("?", 1)[0])
                    child.replaceWith(m_[1], child_new, m_[4])
                elif m_ := match(rf"(.*):({'|'.join(icons)}):(.*)", child):
                    has_match = True
                    child_new = Tag(name="i", attrs={"class": f"smilie {m_[2]}"})
                    child.replaceWith(m_[1], child_new, m_[3])
                elif m_ := match(r"(.*)(?:@([a-zA-Z0-9.~_-]+)|:link([a-zA-Z0-9.~_-]+):)(.*)", child):
                    has_match = True
                    child_new = Tag(name="a", attrs={"class": "linkusername", "href": f"/user/{m_[2] or m_[3]}"})
                    child_new.insert(0, m_[2] or m_[3])
                    child.replaceWith(m_[1], child_new, m_[4])
                elif m_ := match(r"(.*):(?:icon([a-zA-Z0-9.~_-]+)|([a-zA-Z0-9.~_-]+)icon):(.*)", child):
                    has_match = True
                    user: str = m_[2] or m_[3] or ""
                    child_new = Tag(name="a", attrs={"class": "iconusername", "href": f"/user/{user}"})
                    child_new_img: Tag = Tag(
                        name="img", attrs={"alt": user, "title": user, "src": f"/user/{clean_username(user)}/icon"}
                    )
                    child_new.insert(0, child_new_img)
                    if m_[2]:
                        child_new.insert(1, f"\xA0{m_[2]}")
                    child.replaceWith(m_[1], child_new, m_[4])
                elif m_ := match(r"(.*)\[ *(?:(\d+)|-)?, *(?:(\d+)|-)? *, *(?:(\d+)|-)? *](.*)", child):
                    has_match = True
                    child_new = Tag(name="span", attrs={"class": "parsed_nav_links"})
                    child_new_1: Tag | str = "<<<\xA0PREV"
                    child_new_2: Tag | str = "FIRST"
                    child_new_3: Tag | str = "NEXT\xA0>>>"
                    if m_[2]:
                        child_new_1 = Tag(name="a", attrs={"href": f"/view/{m_[2]}"})
                        child_new_1.insert(0, "<<<\xA0PREV")
                    if m_[3]:
                        child_new_2 = Tag(name="a", attrs={"href": f"/view/{m_[3]}"})
                        child_new_2.insert(0, "<<<\xA0FIRST")
                    if m_[4]:
                        child_new_3 = Tag(name="a", attrs={"href": f"/view/{m_[4]}"})
                        child_new_3.insert(0, "NEXT\xA0>>>")
                    child_new.insert(0, child_new_1)
                    child_new.insert(1, "\xA0|\xA0")
                    child_new.insert(2, child_new_2)
                    child_new.insert(3, "\xA0|\xA0")
                    child_new.insert(4, child_new_3)
                    child.replaceWith(m_[1], child_new, m_[5])

        for p in page.select("p"):
            p.replaceWith(*p.children)

        return page

    parser: BBCodeParser = BBCodeParser(install_defaults=False, replace_links=False, replace_cosmetic=True)
    parser.REPLACE_ESCAPE = (
        ("&", "&amp;"),
        ("<", "&lt;"),
        (">", "&gt;"),
    )
    parser.REPLACE_COSMETIC = (
        ("(c)", "&copy;"),
        ("(r)", "&reg;"),
        ("(tm)", "&trade;"),
    )

    for tag in ("i", "b", "u", "s", "sub", "sup", "h1", "h2", "h3", "h3", "h4", "h5", "h6"):
        parser.add_formatter(tag, render_tags)
    for align in ("left", "center", "right"):
        parser.add_simple_formatter(align, f'<code class="bbcode bbcode_{align}">%(value)s</code>')

    parser.add_simple_formatter("spoiler", '<span class="bbcode bbcode_spoiler">%(value)s</span>')
    parser.add_simple_formatter("url", '<a class="auto_link named_link">%(value)s</a>')
    parser.add_simple_formatter(
        "iconusername",
        f'<a class=iconusername href="/user/%(value)s">'
        f'<img alt="%(value)s" title="%(value)s" src="/user/%(value)s/icon">'
        f"%(value)s"
        f"</a>",
    )
    parser.add_simple_formatter(
        "usernameicon",
        f'<a class=iconusername href="/user/%(value)s">'
        f'<img alt="%(value)s" title="%(value)s" src="/user/%(value)s/icon">'
        f"</a>",
    )
    parser.add_simple_formatter("linkusername", '<a class=linkusername href="/user/%(value)s">%(value)s</a>')
    parser.add_simple_formatter("hr", "<hr>", standalone=True)

    parser.add_formatter("url", render_url)
    parser.add_formatter("color", render_color)
    parser.add_formatter("quote", render_quote)
    parser.add_formatter("tag", render_tag)

    bbcode = sub(r"-{5,}", "[hr]", bbcode)

    result_page: BeautifulSoup = parse_extra(BeautifulSoup(parser.format(bbcode), "lxml"))
    return (result_page.select_one("html > body") or result_page).decode_contents()


# noinspection SpellCheckingInspection
def clean_html(html: str) -> str:
    html_parsed: BeautifulSoup = BeautifulSoup(html, "lxml")
    for icon in html_parsed.select("a.iconusername > img"):
        icon.attrs["onload"] = "this.classList.add('show')"
        icon.attrs["src"] = f"/user/{clean_username(icon.attrs['title'])}/icon/"
    for link in html_parsed.select("a[href*='furaffinity.net']"):
        link["href"] = "/" + fa_link.sub("", link.attrs["href"]).strip("/")
    return str(html_parsed)


def prepare_html(html: str, use_bbcode: bool) -> str:
    return clean_html(bbcode_to_html(html)) if use_bbcode else clean_html(html)
