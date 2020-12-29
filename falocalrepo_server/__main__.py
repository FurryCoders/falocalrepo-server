from os.path import isfile
from sys import argv

from .server import server


def main():
    if not isfile(argv[1]):
        raise FileNotFoundError(argv[1])

    host, port = argv[2].split(":") if argv[2:] else ("0.0.0.0", 8080)
    server(argv[1], host=host, port=int(port))


if __name__ == '__main__':
    main()
