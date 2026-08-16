"""Adaptador MySQL del contexto INFORMES (vistas pesadas del legacy).

SQL copiado 1:1 de los accesos ad-hoc que vivían en dispositivos/tasks_scripts.py.
Estas vistas pueden tardar: usan el ``read_timeout`` amplio de informes. SOLO LECTURA.
"""
from typing import Any

import pymysql

from app.config import Settings
from app.infrastructure.mysql.connection import conexion_legacy

# Estados de contrato que consulta el informe de liberados (mismos del original).
_ESTADOS_INFORME = ("Activo", "Atrasado", "Default")


class RepositorioInformesMysql:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def contratos_por_lock_system(self, lock_system: str) -> list[dict[str, Any]]:
        with conexion_legacy(self._settings,
                             read_timeout=self._settings.mysql_read_timeout_informes) as conn:
            cur = conn.cursor(pymysql.cursors.DictCursor)
            cur.execute(
                """
                SELECT imei, contract_number, customer_dni, full_name, customer_phone, status_name, product
                FROM view_general_contracts
                WHERE lock_system COLLATE utf8mb4_unicode_ci = %s COLLATE utf8mb4_unicode_ci
                  AND status_name COLLATE utf8mb4_unicode_ci IN %s
                  AND imei IS NOT NULL AND imei != ''
                """,
                (lock_system, _ESTADOS_INFORME),
            )
            return list(cur.fetchall())

    def catalogo_device_location(self) -> list[tuple[str, str]]:
        with conexion_legacy(self._settings,
                             read_timeout=self._settings.mysql_read_timeout_informes) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT description, tags_model_device FROM view_device "
                    "WHERE description IS NOT NULL AND description <> ''"
                )
                return [(r[0], r[1]) for r in cur.fetchall()]
