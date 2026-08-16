"""Adaptador MySQL del contexto POBLACIÓN (inventario de equipos por candado).

SQL copiado 1:1 del cliente original. Paginación por CLAVE (``imei > cursor`` +
``ORDER BY imei`` obligatorio): estable entre corridas, a diferencia de OFFSET.
SOLO LECTURA.
"""
from app.config import Settings
from app.domain.catalogo import ESTADOS_NO_VIGENTES, MDM_CANDADO, placeholders
from app.infrastructure.mysql.connection import conexion_legacy


class RepositorioPoblacionMysql:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def imeis_candado(self, sistema: str, limit: int | None,
                      desde_imei: str | None) -> list[str]:
        dev, col = MDM_CANDADO[sistema]
        est_ph = placeholders(ESTADOS_NO_VIGENTES)
        est = list(ESTADOS_NO_VIGENTES)
        phone = (
            f"SELECT d.imei FROM {dev} d "
            f"JOIN application a ON a.{col}=d.id "
            "JOIN contract c ON c.application_id=a.id "
            f"WHERE d.imei IS NOT NULL AND d.imei<>'' AND c.contracts_status_id NOT IN ({est_ph})"
        )
        if col == "paytrigger_device_id":
            sql = f"SELECT DISTINCT imei FROM ({phone}) x"
            params = est
        else:
            twist = (
                f"SELECT d.imei FROM {dev} d "
                f"JOIN twist_application ta ON ta.{col}=d.id "
                "JOIN twist_contract tc ON tc.twist_application_id=ta.id "
                f"WHERE d.imei IS NOT NULL AND d.imei<>'' "
                f"AND tc.twist_contract_status_id NOT IN ({est_ph})"
            )
            sql = f"SELECT DISTINCT imei FROM ({phone} UNION {twist}) x"
            params = est + est
        # Paginación por CLAVE: la query externa no lleva WHERE propio.
        if desde_imei:
            sql += " WHERE imei > %s"
            params = params + [str(desde_imei)]
        sql += " ORDER BY imei"
        if limit:
            sql += f" LIMIT {int(limit)}"
        with conexion_legacy(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return [r[0] for r in cur.fetchall()]

    def imei_modelo_candado(self, sistema: str, solo_vigentes: bool) -> list[tuple[str, str]]:
        dev, col = MDM_CANDADO[sistema]
        with conexion_legacy(self._settings) as conn:
            with conn.cursor() as cur:
                if not solo_vigentes:
                    cur.execute(
                        f"SELECT imei, model FROM {dev} "
                        "WHERE imei IS NOT NULL AND imei<>'' AND model IS NOT NULL AND model<>''"
                    )
                    return [(r[0], r[1]) for r in cur.fetchall()]
                est_ph = placeholders(ESTADOS_NO_VIGENTES)
                est = list(ESTADOS_NO_VIGENTES)
                phone = (
                    f"SELECT d.imei, d.model FROM {dev} d "
                    f"JOIN application a ON a.{col}=d.id "
                    "JOIN contract c ON c.application_id=a.id "
                    f"WHERE d.imei IS NOT NULL AND d.imei<>'' AND d.model IS NOT NULL AND d.model<>'' "
                    f"AND c.contracts_status_id NOT IN ({est_ph})"
                )
                if col == "paytrigger_device_id":
                    cur.execute(f"SELECT DISTINCT imei, model FROM ({phone}) x", est)
                else:
                    twist = (
                        f"SELECT d.imei, d.model FROM {dev} d "
                        f"JOIN twist_application ta ON ta.{col}=d.id "
                        "JOIN twist_contract tc ON tc.twist_application_id=ta.id "
                        f"WHERE d.imei IS NOT NULL AND d.imei<>'' AND d.model IS NOT NULL AND d.model<>'' "
                        f"AND tc.twist_contract_status_id NOT IN ({est_ph})"
                    )
                    cur.execute(f"SELECT DISTINCT imei, model FROM ({phone} UNION {twist}) x", est + est)
                return [(r[0], r[1]) for r in cur.fetchall()]
