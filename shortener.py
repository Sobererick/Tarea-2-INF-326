"""Endpoints Litestar. VERSION selecciona la arquitectura al iniciar el proceso."""
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from litestar import Litestar, Request, get, post
from litestar.config.response_cache import ResponseCacheConfig
from litestar.exceptions import HTTPException, NotFoundException, ValidationException
from litestar.middleware.rate_limit import RateLimitConfig
from litestar.response import Redirect

from hits_pb2 import UrlHit
from hits_pb2_grpc import VisitLogStub
from storage import Links, links_db_path


@dataclass
class NewLink:
    long_url: str


def validate_url(value: str) -> None:
    try:
        parts = urlsplit(value)
        if (parts.scheme in {"http", "https"} and parts.hostname
                and "\\" not in value and parts.port != 0
                and all(char.isprintable() and not char.isspace() for char in value)):
            return
    except ValueError:
        pass
    raise ValidationException(detail="Se requiere una URL absoluta con esquema http o https.")


def create_app() -> Litestar:
    version = os.getenv("VERSION", "1")
    if version not in {"1", "2"}:
        raise ValueError("VERSION debe ser 1 o 2")
    links = Links(links_db_path())
    port = "8443" if version == "1" else "8444"
    base = os.getenv("PUBLIC_BASE_URL", f"https://localhost:{port}").rstrip("/")

    @post("/urls", sync_to_thread=True, status_code=201)
    def shorten(data: NewLink) -> dict[str, str]:
        validate_url(data.long_url)
        code = links.create(data.long_url)
        return {"short_url": f"{base}/{code}"}

    def destination(code: str) -> str:
        result = links.resolve(code)
        if result is None:
            raise NotFoundException(detail="El enlace corto no existe.")
        return result

    if version == "1":
        channel = grpc.insecure_channel(os.getenv("LOG_TARGET", "localhost:50051"))
        log = VisitLogStub(channel)

        @get("/{code:str}", sync_to_thread=True)
        def temporary(code: str) -> Redirect:
            url = destination(code)
            timestamp = Timestamp()
            timestamp.GetCurrentTime()
            try:
                log.Record(UrlHit(timestamp=timestamp, url=f"{base}/{code}"), timeout=0.5)
            except grpc.RpcError as exc:
                raise HTTPException(status_code=503, detail="Registro de visitas no disponible.",
                                    headers={"Cache-Control": "no-store"}) from exc
            return Redirect(url, status_code=302, headers={"Cache-Control": "no-store"})

        return Litestar([shorten, temporary], on_shutdown=[channel.close], openapi_config=None)

    @get("/{code:str}", cache=60, sync_to_thread=True)
    def permanent(code: str) -> Redirect:
        return Redirect(destination(code), status_code=301, headers={"Cache-Control": "private, max-age=300"})

    def cache_key(request: Request) -> str:
        return request.url.path  # El destino depende únicamente del código.

    limiter = RateLimitConfig(rate_limit=("minute", int(os.getenv("RATE_PER_MINUTE", "60"))))
    return Litestar(
        [shorten, permanent],
        middleware=[limiter.middleware],
        response_cache_config=ResponseCacheConfig(key_builder=cache_key),
        openapi_config=None,
    )
