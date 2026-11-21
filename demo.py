"""Ejecutar dentro de v1 o v2. Muestra las respuestas HTTPS sin seguir el destino."""
import argparse
from contextlib import closing
from http.client import HTTPSConnection
import json
from pathlib import Path
import sqlite3
import ssl
from urllib.parse import urlsplit

from storage import links_db_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", default="https://usm.cl/admision/")
    target = parser.parse_args().url
    connection = HTTPSConnection("localhost", 8443, context=ssl.create_default_context(cafile="/certs/tls.crt"))
    try:
        connection.request("POST", "/urls", json.dumps({"long_url": target}), {"Content-Type": "application/json"})
        created = connection.getresponse()
        body = created.read().decode()
        print(f"POST /urls → {created.status} {body}")
        if created.status != 201:
            raise SystemExit(1)
        path = urlsplit(json.loads(body)["short_url"]).path
        db_uri = Path(links_db_path()).resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(db_uri, uri=True)) as db:
            record = db.execute("SELECT id, hash, long_url FROM links WHERE hash = ?", (path[1:],)).fetchone()
        if record is None:
            raise SystemExit("No se encontró el enlace creado en la base de esta versión.")
        link_id, code, original_url = record
        print(f"SQLite → id={link_id}  hash={code}  long_url={original_url}")
        for _ in range(2):
            connection.request("GET", path)
            response = connection.getresponse()
            response.read()
            print(f"GET {path} → {response.status}  Location={response.getheader('Location')}  "
                  f"Cache-Control={response.getheader('Cache-Control')}")
            if response.status not in {301, 302} or response.getheader("Location") is None:
                raise SystemExit(1)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
