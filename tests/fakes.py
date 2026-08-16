"""Dobles de pymysql para los tests de infraestructura.

El patrón: cada test define un ``responder(sql, params) -> filas`` (o
``(columnas, filas)`` cuando el código lee ``cursor.description``) y parchea
``conexion_legacy`` en el MÓDULO del repositorio bajo prueba con
:func:`parchear_conexion`. Así se verifica el SQL emitido y el post-procesado
sin tocar ninguna base real.
"""
from contextlib import contextmanager


class CursorFalso:
    def __init__(self, responder):
        self._responder = responder
        self.ejecutadas = []          # [(sql, params), ...] para asertos sobre el SQL
        self._filas = []
        self.description = None

    def execute(self, sql, params=None):
        self.ejecutadas.append((sql, params))
        resultado = self._responder(sql, params)
        if isinstance(resultado, tuple) and len(resultado) == 2 and isinstance(resultado[0], (list, tuple)) \
                and resultado and all(isinstance(c, str) for c in resultado[0]):
            columnas, filas = resultado
            self.description = [(c,) for c in columnas]
            self._filas = list(filas)
        else:
            self.description = None
            self._filas = list(resultado or [])

    def fetchall(self):
        return list(self._filas)

    def fetchone(self):
        return self._filas[0] if self._filas else None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class ConexionFalsa:
    def __init__(self, responder):
        self.cursor_falso = CursorFalso(responder)
        self.cerrada = False

    def cursor(self, *args, **kwargs):
        return self.cursor_falso

    def close(self):
        self.cerrada = True


def parchear_conexion(monkeypatch, modulo, responder):
    """Sustituye ``conexion_legacy`` en ``modulo`` por una conexión falsa.

    Devuelve la ConexionFalsa para asertar sobre ``cursor_falso.ejecutadas``.
    """
    conn = ConexionFalsa(responder)

    @contextmanager
    def _cm(settings, read_timeout=None):
        yield conn

    monkeypatch.setattr(modulo, "conexion_legacy", _cm)
    return conn


def settings_prueba(**extra):
    from app.config import Settings
    base = dict(mysql_host="mysql.prueba", mysql_user="usuario",
                mysql_password="secreto", mysql_db="alocreditprod")
    base.update(extra)
    return Settings(_env_file=None, **base)
