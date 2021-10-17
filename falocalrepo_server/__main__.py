from argparse import ArgumentParser
from pathlib import Path

from .server import server


def main():
    argparser: ArgumentParser = ArgumentParser(description="Web interface for https://pypi.org/project/falocalrepo/.")
    argparser.add_argument("database", type=Path)
    argparser.add_argument("--host", type=str, default="0.0.0.0")
    argparser.add_argument("--port", type=int, default=None)
    argparser.add_argument("--ssl-cert", dest="ssl_cert", type=Path, default=None)
    argparser.add_argument("--ssl-key", dest="ssl_key", type=Path, default=None)

    args = argparser.parse_args()

    if not args.database.is_file():
        raise FileNotFoundError(args.database)

    server(args.database, host=args.host, port=args.port, ssl_cert=args.ssl_cert, ssl_key=args.ssl_key)


if __name__ == '__main__':
    main()
