"""Servidor gRPC y base de visitas independientes del acortador."""
import logging
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

import grpc
from google.protobuf.empty_pb2 import Empty

import hits_pb2_grpc


class VisitLog(hits_pb2_grpc.VisitLogServicer):
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS hits (timestamp TEXT NOT NULL, url TEXT NOT NULL)")

    def Record(self, request, context):
        try:
            with closing(sqlite3.connect(self.path)) as db, db:
                db.execute("INSERT INTO hits VALUES (?, ?)", (request.timestamp.ToJsonString(), request.url))
        except sqlite3.Error:
            logging.exception("No se pudo guardar la visita")
            context.abort(grpc.StatusCode.UNAVAILABLE, "Registro de visitas no disponible")
        return Empty()


def serve():
    server = grpc.server(ThreadPoolExecutor(max_workers=8))
    hits_pb2_grpc.add_VisitLogServicer_to_server(VisitLog(os.getenv("LOG_DB", "data/hits.db")), server)
    server.add_insecure_port(os.getenv("LOG_BIND", "[::]:50051"))
    server.start()
    try:
        server.wait_for_termination()
    finally:
        server.stop(grace=1)


if __name__ == "__main__":
    serve()
