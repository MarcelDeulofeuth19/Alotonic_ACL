"""Fábrica de conexiones a la base legacy alocreditprod.

Espeja exactamente los kwargs del cliente actual de AloTonic
(core/infrastructure/db.py): mismos timeouts, charset y SSL opt-in, para que el
cambio de proceso no cambie el comportamiento frente a la base.
"""
from collections.abc import Iterator
from contextlib import contextmanager

import pymysql

from app.config import Settings
from app.domain.exceptions import BaseLegacyNoDisponible


def _kwargs_conexion(settings: Settings, read_timeout: int | None = None) -> dict:
    kwargs: dict = dict(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_db,
        charset="utf8mb4",
        connect_timeout=settings.mysql_connect_timeout,
        read_timeout=read_timeout or settings.mysql_read_timeout,
    )
    if settings.mysql_ssl_enabled:
        kwargs["ssl"] = {"ssl_ca": settings.mysql_ssl_ca} if settings.mysql_ssl_ca else {}
    return kwargs


@contextmanager
def conexion_legacy(settings: Settings,
                    read_timeout: int | None = None) -> Iterator[pymysql.connections.Connection]:
    """Abre una conexión por operación y garantiza su cierre.

    Una conexión por petición (sin pool) es deliberado: es el mismo patrón del
    cliente actual, el volumen lo tolera y evita estados a medias entre workers.
    """
    try:
        conn = pymysql.connect(**_kwargs_conexion(settings, read_timeout))
    except pymysql.MySQLError as exc:
        raise BaseLegacyNoDisponible(f"No se pudo conectar a la base legacy: {exc}") from exc
    try:
        yield conn
    except pymysql.MySQLError as exc:
        raise BaseLegacyNoDisponible(f"Fallo consultando la base legacy: {exc}") from exc
    finally:
        conn.close()
