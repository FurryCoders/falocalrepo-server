from os.path import isfile
from sys import argv

from .server import app


def main():
    assert isfile("FA.db")
    host, port = argv[1].split(":") if argv[1:] else ("0.0.0.0", 8080)
    app.run(host=host, port=int(port))


if __name__ == '__main__':
    main()
