"""Pruebas reproducibles con Litestar, SQLite temporal y un servidor gRPC real."""
import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import grpc
from litestar.testing import TestClient

import hits_pb2_grpc
from log_service import VisitLog
from shortener import create_app
from storage import FIRST_ID, Links, base62


DESTINATION = "https://usm.cl/postgrado/?campus=valparaiso&anio=2026#fechas"


class ShortenerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = self.root / "links.db"
        environment = patch.dict(os.environ, {
            "LINKS_DB": str(self.db), "PUBLIC_BASE_URL": "https://localhost:8443",
            "VERSION": "1", "RATE_PER_MINUTE": "60",
        })
        environment.start()
        self.addCleanup(environment.stop)

    def start_log(self):
        self.log_db = self.root / "hits.db"
        server = grpc.server(ThreadPoolExecutor(max_workers=2))
        hits_pb2_grpc.add_VisitLogServicer_to_server(VisitLog(str(self.log_db)), server)
        port = server.add_insecure_port("127.0.0.1:0")
        os.environ["LOG_TARGET"] = f"127.0.0.1:{port}"
        server.start()
        self.addCleanup(lambda: server.stop(0).wait())
        return server

    def create_link(self, client):
        response = client.post("/urls", json={"long_url": DESTINATION})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"short_url": "https://localhost:8443/eRgfR"})
        return response.json()["short_url"]

    def test_v1_two_gets_two_persisted_hits(self):
        self.start_log()
        with TestClient(create_app()) as client:
            url = self.create_link(client)
            for _ in range(2):
                response = client.get(url, follow_redirects=False)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["location"], DESTINATION)
                self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(client.get("/desconocido").status_code, 404)
        with closing(sqlite3.connect(self.log_db)) as db:
            rows = db.execute("SELECT timestamp,url FROM hits").fetchall()
        self.assertEqual([row[1] for row in rows], [url, url])
        self.assertTrue(all(row[0].endswith("Z") for row in rows))

    def test_v1_log_unavailable(self):
        self.start_log().stop(0).wait()
        with TestClient(create_app()) as client:
            result = client.get(self.create_link(client), follow_redirects=False)
            self.assertEqual(result.status_code, 503)
            self.assertNotIn("location", result.headers)

    def test_v2_cached_redirect_without_a_second_database_read(self):
        os.environ["VERSION"] = "2"
        with TestClient(create_app()) as client:
            url = self.create_link(client)
            first = client.get(url, follow_redirects=False)
            self.assertEqual(first.status_code, 301)
            self.assertEqual(first.headers["location"], DESTINATION)
            self.assertIn("max-age=300", first.headers["cache-control"])
            with patch.object(Links, "resolve", side_effect=AssertionError("Lectura adicional")):
                second = client.get(url, follow_redirects=False)
            self.assertEqual(second.status_code, 301)
            self.assertEqual(second.headers["location"], DESTINATION)
            self.assertEqual(client.get("/desconocido").status_code, 404)

    def test_v2_limit_also_applies_to_cached_gets(self):
        os.environ.update(VERSION="2", RATE_PER_MINUTE="3")
        with TestClient(create_app()) as client:
            url = self.create_link(client)
            self.assertEqual([client.get(url, follow_redirects=False).status_code for _ in range(3)], [301, 301, 429])

    def test_invalid_input_creates_no_links(self):
        os.environ["VERSION"] = "2"
        with TestClient(create_app()) as client:
            for url in ("javascript:alert(1)", "/sin-host", "https://usm.cl:abc/", "https://usm.cl/\r\nX"):
                self.assertEqual(client.post("/urls", json={"long_url": url}).status_code, 400)
            self.create_link(client)

    def test_concurrent_allocation_and_restart(self):
        links = Links(str(self.db))
        with ThreadPoolExecutor(max_workers=8) as pool:
            codes = list(pool.map(links.create, [DESTINATION] * 20))
        with closing(sqlite3.connect(self.db)) as db:
            rows = db.execute("SELECT id, hash, long_url FROM links ORDER BY id").fetchall()
        self.assertEqual(rows, [(i, base62(i), DESTINATION) for i in range(FIRST_ID, FIRST_ID + 20)])
        self.assertEqual(len(set(codes)), 20)
        reopened = Links(str(self.db))
        self.assertEqual(reopened.resolve("eRgfR"), DESTINATION)
        self.assertEqual(reopened.create(DESTINATION), base62(FIRST_ID + 20))


if __name__ == "__main__":
    unittest.main()
