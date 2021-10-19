from argparse import Action
from argparse import ArgumentError
from argparse import ArgumentParser
from pathlib import Path

from .server import server


def main():
    argparser: ArgumentParser = ArgumentParser(description="Web interface for https://pypi.org/project/falocalrepo/.")
    argparser.add_argument("database", type=Path,
                           help="path to FALocalRepo database file")
    argparser.add_argument("--host", type=str, default="0.0.0.0",
                           help="server host, defaults to 0.0.0.0")
    argparser.add_argument("--port", type=int, default=None,
                           help="server port, defaults to 80 for HTTP and 443 for HTTPS")
    ssl_cert_action: Action = argparser.add_argument("--ssl-cert", dest="ssl_cert", type=Path, default=None,
                                                     help="path to SSL certificate file for HTTPS")
    ssl_key_action: Action = argparser.add_argument("--ssl-key", dest="ssl_key", type=Path, default=None,
                                                    help="path to SSL key file for HTTPS")
    # noinspection HttpUrlsUsage
    argparser.add_argument("--redirect-http", dest="redirect_http", action="store_true", default=False,
                           help="redirect all traffic from http://HOST:80 to https://HOST:PORT")

    args = argparser.parse_args()

    if not args.database.is_file():
        raise FileNotFoundError(args.database)
    elif args.ssl_cert and not args.ssl_key:
        raise ArgumentError(ssl_key_action, "SSL certificate must be accompanied by a key")
    elif args.ssl_key and not args.ssl_cert:
        raise ArgumentError(ssl_cert_action, "SSL key must be accompanied by a certificate")

    server(args.database, args.host, args.port, args.ssl_cert, args.ssl_key, args.redirect_http)


if __name__ == '__main__':
    main()
