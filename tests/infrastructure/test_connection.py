from unittest.mock import MagicMock, patch

import pymysql
import pytest

from app.config import Settings
from app.domain.exceptions import BaseLegacyNoDisponible
from app.infrastructure.mysql.connection import _kwargs_conexion, conexion_legacy


def _settings(**extra) -> Settings:
    base = dict(
        mysql_host="mysql.prueba", mysql_user="usuario",
        mysql_password="secreto", mysql_db="alocreditprod",
    )
    base.update(extra)
    return Settings(_env_file=None, **base)


def test_kwargs_espejan_cliente_actual():
    kwargs = _kwargs_conexion(_settings())
    assert kwargs == dict(
        host="mysql.prueba", port=3306, user="usuario", password="secreto",
        database="alocreditprod", charset="utf8mb4",
        connect_timeout=15, read_timeout=60,
    )


def test_ssl_opt_in_con_y_sin_ca():
    con_ca = _kwargs_conexion(_settings(mysql_ssl_enabled=True, mysql_ssl_ca="/ruta/ca.pem"))
    assert con_ca["ssl"] == {"ssl_ca": "/ruta/ca.pem"}
    sin_ca = _kwargs_conexion(_settings(mysql_ssl_enabled=True))
    assert sin_ca["ssl"] == {}


def test_conexion_se_cierra_al_salir():
    conn = MagicMock()
    with patch("app.infrastructure.mysql.connection.pymysql.connect", return_value=conn):
        with conexion_legacy(_settings()) as c:
            assert c is conn
    conn.close.assert_called_once()


def test_error_de_conexion_se_traduce_a_dominio():
    with patch(
        "app.infrastructure.mysql.connection.pymysql.connect",
        side_effect=pymysql.OperationalError(2003, "can't connect"),
    ):
        with pytest.raises(BaseLegacyNoDisponible):
            with conexion_legacy(_settings()):
                pass  # pragma: no cover


def test_error_durante_la_consulta_se_traduce_y_cierra():
    conn = MagicMock()
    with patch("app.infrastructure.mysql.connection.pymysql.connect", return_value=conn):
        with pytest.raises(BaseLegacyNoDisponible):
            with conexion_legacy(_settings()):
                raise pymysql.ProgrammingError(1146, "table doesn't exist")
    conn.close.assert_called_once()


def test_error_ajeno_no_se_enmascara():
    conn = MagicMock()
    with patch("app.infrastructure.mysql.connection.pymysql.connect", return_value=conn):
        with pytest.raises(ValueError):
            with conexion_legacy(_settings()):
                raise ValueError("bug del llamador")
    conn.close.assert_called_once()
