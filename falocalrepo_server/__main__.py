from pathlib import Path

from click import BadParameter
from click import Context
from click import IntRange
from click import Parameter
from click import Path as PathClick
from click import UsageError
from click import argument
from click import command
from click import help_option
from click import option
from click import pass_context
from click.core import ParameterSource
from click_help_colors import HelpColorsCommand
from falocalrepo_database import Database

from .__version__ import __version__
from .server import server

__prog__name__ = __package__.replace("_", "-")
_yellow: str = "\x1b[33m"
_reset: str = "\x1b[0m"


class CustomHelpColorsCommand(HelpColorsCommand):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.help_headers_color = "blue"
        self.help_options_color = "yellow"


def database_callback(ctx: Context, param: Parameter, value: Path) -> Path | None:
    if ctx.params.get("redirect_http", None):
        return value
    elif value is None:
        raise UsageError(f"Missing argument {param.name.upper()!r}.", ctx)
    elif ps := Database.check_connection(value, raise_for_error=False):
        raise BadParameter(f"Multiple connections to database {str(value)!r}: {ps}", ctx, param)
    return value


def port_callback(ctx: Context, param: Parameter, value: str) -> int | None:
    if ctx.get_parameter_source(param.name) == ParameterSource.DEFAULT:
        return None
    elif not value.isdigit():
        raise BadParameter(f"{value!r} is not a valid integer.", ctx, param)
    elif (port := int(value)) <= 0:
        raise BadParameter(f"{value!r} is not a valid port.", ctx, param)
    else:
        return port


def color_callback(ctx: Context, param: Parameter, value: bool) -> bool:
    if ctx.get_parameter_source(param.name) == ParameterSource.COMMANDLINE:
        ctx.color = value
    return value


def docstring_format(*args, **kwargs):
    def inner(obj: {__doc__}) -> {__doc__}:
        obj.__doc__ = (obj.__doc__ or "").format(*args, yellow=_yellow, reset=_reset, **kwargs)
        return obj

    return inner


# noinspection HttpUrlsUsage
@command(__prog__name__, cls=CustomHelpColorsCommand, no_args_is_help=True)
@argument(
    "database",
    callback=database_callback,
    required=False,
    default=None,
    type=PathClick(exists=True, dir_okay=False, resolve_path=True, path_type=Path),
)
@option("--host", metavar="HOST", type=str, default="0.0.0.0", show_default=True, help="Server host.")
@option(
    "--port",
    metavar="PORT",
    type=str,
    default="80, 443",
    show_default=True,
    callback=port_callback,
    help="Server port.",
)
@option(
    "--ssl-cert",
    type=PathClick(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to SSL certificate file for HTTPS",
)
@option(
    "--ssl-key",
    type=PathClick(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to SSL key file for HTTPS",
)
@option(
    "--redirect-http",
    metavar="PORT2",
    type=int,
    default=None,
    callback=port_callback,
    is_eager=True,
    help=f"Redirect all traffic from http://HOST:{_yellow}PORT{_reset} to " f"https://HOST:{_yellow}PORT2{_reset}",
)
@option(
    "--auth",
    metavar="<USERNAME PASSWORD>",
    type=(str, str),
    multiple=True,
    help=f"Username and password for authentication. [multiple]",
)
@option(
    "--auth-ignore",
    metavar="<IP>",
    type=str,
    multiple=True,
    help=f"Ignore authentication for IP addresses. [multiple]",
)
@option("--editor", type=str, multiple=True, help="Users with editing rights.")
@option("--max-results", type=IntRange(1000), default=None, help="Maximum number of results from queries.")
@option("--cache/--no-cache", is_flag=True, default=True, help="Use cache.")
@option("--browser/--no-browser", "browser", is_flag=True, default=True, help="Open browser on startup.")
@option(
    "--color/--no-color",
    is_flag=True,
    is_eager=True,
    default=None,
    expose_value=False,
    callback=color_callback,
    help="Toggle ANSI colors.",
)
@help_option("--help", "-h", is_eager=True, help="Show help message and exit.")
@pass_context
@docstring_format(server_name=__prog__name__, server_version=__version__)
def main(
    ctx: Context,
    database: Path | None,
    host: str,
    port: int | None,
    ssl_cert: Path | None,
    ssl_key: Path | None,
    redirect_http: int | None,
    auth: tuple[tuple[str, str], ...],
    auth_ignore: tuple[str, ...],
    editor: tuple[str, ...],
    max_results: int | None,
    cache: bool,
    browser: bool,
):
    """
    Start a server at {yellow}HOST{reset}:{yellow}PORT{reset} to navigate the database at {yellow}DATABASE{reset}. The
    {yellow}--ssl-cert{reset} and {yellow}--ssl-cert{reset} options allow serving with HTTPS. Setting
    {yellow}--redirect-http{reset} starts the server in HTTP to HTTPS redirection mode.

    {yellow}DATABASE{reset} can be omitted when using the {yellow}--redirect-http{reset} option.

    When the app has finished loading, it automatically opens a browser window. To avoid this, use the
    {yellow}--no-browser{reset} option.

    For more details on usage see https://pypi.org/project/{server_name}/{server_version}.
    """
    if ssl_cert and not ssl_key:
        raise BadParameter(
            f"'--ssl-cert' and '--ssl-key' must be set together.",
            ctx,
            next(_p for _p in ctx.command.params if _p.name == "ssl_key"),
        )
    elif ssl_key and not ssl_cert:
        raise BadParameter(
            f"'--ssl-cert' and '--ssl-key' must be set together.",
            ctx,
            next(_p for _p in ctx.command.params if _p.name == "ssl_cert"),
        )
    elif port is not None and port == redirect_http:
        raise BadParameter(
            "PORT and PORT2 cannot be identical.",
            ctx,
            next(_p for _p in ctx.command.params if _p.name == "redirect_http"),
        )

    server(
        database or Path(),
        host,
        port,
        ssl_cert,
        ssl_key,
        auth,
        auth_ignore,
        editor,
        max_results,
        cache,
        browser,
    )


if __name__ == "__main__":
    main()
