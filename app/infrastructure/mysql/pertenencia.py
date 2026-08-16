"""Adaptador MySQL del contexto PERTENENCIA (membresía en tablas de candado).

Es el tramo MySQL del resolver de proveedores de AloTonic: SQL copiado 1:1 de
cola/infrastructure/acl_resolver.py. El schema ``alocreditprod.`` va HARDCODEADO
en la query igual que en el original (independiente de MYSQL_DB). SOLO LECTURA.
"""
from app.config import Settings
from app.domain.catalogo import TABLAS_PERTENENCIA
from app.infrastructure.mysql.connection import conexion_legacy

# Mismo troceo que el resolver original: rutas masivas de miles de IMEIs.
CHUNK = 1000


class RepositorioPertenenciaMysql:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def imeis_en_tabla(self, tabla: str, imeis: list[str]) -> set[str]:
        """IMEIs de ``imeis`` presentes en alocreditprod.<tabla> (consulta por chunks)."""
        tabla_real = TABLAS_PERTENENCIA[tabla]
        encontrados: set[str] = set()
        with conexion_legacy(self._settings) as conn:
            with conn.cursor() as cursor:
                for j in range(0, len(imeis), CHUNK):
                    ch = imeis[j:j + CHUNK]
                    ph = ",".join(["%s"] * len(ch))
                    cursor.execute(
                        f"SELECT DISTINCT imei FROM alocreditprod.{tabla_real} WHERE imei IN ({ph})",
                        ch,
                    )
                    encontrados |= {row[0] for row in cursor.fetchall()}
        return encontrados

    def conteo_tabla(self, tabla: str) -> int:
        tabla_real = TABLAS_PERTENENCIA[tabla]
        with conexion_legacy(self._settings) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM alocreditprod.{tabla_real}")
                return int(cursor.fetchone()[0])
