from .server import app


def main(host: str = "0.0.0.0", port: int = 8080):
    app.run(host=host, port=port)


if __name__ == '__main__':
    main()
