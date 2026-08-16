"""Adaptador MySQL del contexto PRÓRROGAS del CRM (vencidas cortas y delta).

SQL copiado 1:1 del cliente original (candados_alotonic_repository). SOLO LECTURA.
La vigencia de una prórroga se juzga SIEMPRE por ``lock_date``, jamás por la
columna ``active`` (el CRM la apaga al procesarla).
"""
from datetime import datetime
from typing import Any

from app.config import Settings
from app.domain.catalogo import (
    AMORTIZACION,
    ATRASADO_STATUS,
    ESTADOS_NO_VIGENTES,
    MDM_CANDADO,
    PRORROGA_CRM,
    placeholders,
    tipo_prorroga_crm,
)
from app.domain.tiempo import ahora_local_legacy
from app.infrastructure.mysql.connection import conexion_legacy


class RepositorioProrrogasMysql:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def cortas_vencidas(self, sistema: str, horas_ventana: int,
                        max_horas_rango: int, limite: int) -> list[dict[str, Any]]:
        dev, col = MDM_CANDADO[sistema]
        ahora = ahora_local_legacy()
        est_ph = placeholders(ESTADOS_NO_VIGENTES)
        salida: list[dict[str, Any]] = []
        with conexion_legacy(self._settings) as conn:
            with conn.cursor() as cur:
                for familia, tabla, fk_con, t_con, fk_app, t_app in PRORROGA_CRM:
                    # twist_application NO tiene paytrigger_device_id.
                    if familia == "TWIST_1.0" and col == "paytrigger_device_id":
                        continue
                    estado_col = "contracts_status_id" if familia == "PHONE" else "twist_contract_status_id"
                    amort, amort_fk, amort_estado = AMORTIZACION[familia]
                    cur.execute(
                        f"SELECT d.imei, c.id, p.type, p.created_at, p.lock_date, "
                        f"       TIMESTAMPDIFF(HOUR, p.created_at, p.lock_date) AS horas, "
                        f"       EXISTS(SELECT 1 FROM {amort} am WHERE am.{amort_fk} = c.id "
                        f"              AND am.{amort_estado} = %s) AS en_mora "
                        f"FROM {tabla} p "
                        f"JOIN {t_con} c ON c.id = p.{fk_con} "
                        f"JOIN {t_app} ap ON ap.id = c.{fk_app} "
                        f"JOIN {dev} d ON d.id = ap.{col} "
                        f"WHERE p.lock_date > DATE_SUB(%s, INTERVAL %s HOUR) AND p.lock_date <= %s "
                        f"  AND TIMESTAMPDIFF(HOUR, p.created_at, p.lock_date) BETWEEN 0 AND %s "
                        f"  AND c.{estado_col} NOT IN ({est_ph}) "
                        f"  AND d.imei IS NOT NULL AND d.imei <> '' "
                        # Sin otra prórroga con ventana AÚN abierta para el mismo contrato.
                        f"  AND NOT EXISTS(SELECT 1 FROM {tabla} p2 "
                        f"                 WHERE p2.{fk_con} = c.id AND p2.lock_date > %s) "
                        f"ORDER BY p.lock_date DESC LIMIT %s",
                        [ATRASADO_STATUS[familia], ahora, int(horas_ventana), ahora,
                         int(max_horas_rango)] + list(ESTADOS_NO_VIGENTES) + [ahora, limite],
                    )
                    for imei, cid, tipo, creado, lock_date, horas, en_mora in cur.fetchall():
                        salida.append({
                            "imei": imei,
                            "familia": familia,
                            "contract_id": cid,
                            "tipo": tipo_prorroga_crm(tipo),
                            "otorgada_en": creado.strftime("%Y-%m-%d %H:%M:%S") if creado else None,
                            "vencio_en": lock_date.strftime("%Y-%m-%d %H:%M:%S") if lock_date else None,
                            "horas": int(horas) if horas is not None else None,
                            "en_mora": bool(en_mora),
                        })
        # Un IMEI puede traer varias prórrogas cortas vencidas en la ventana: basta la última.
        vistos: set[str] = set()
        unicos: list[dict[str, Any]] = []
        for fila in salida:
            if fila["imei"] in vistos:
                continue
            vistos.add(fila["imei"])
            unicos.append(fila)
        return unicos

    def imeis_con_prorroga_nueva(self, sistema: str, desde: datetime) -> list[str]:
        dev, col = MDM_CANDADO[sistema]
        est_ph = placeholders(ESTADOS_NO_VIGENTES)
        est = list(ESTADOS_NO_VIGENTES)
        imeis: set[str] = set()
        with conexion_legacy(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT d.imei FROM contracts_user_prorroga p "
                    "JOIN contract co ON co.id=p.contract_id "
                    "JOIN application a ON a.id=co.application_id "
                    f"JOIN {dev} d ON d.id=a.{col} "
                    "WHERE p.active=1 AND p.created_at > %s "
                    "AND d.imei IS NOT NULL AND d.imei<>'' "
                    f"AND co.contracts_status_id NOT IN ({est_ph})",
                    [desde] + est,
                )
                imeis.update(r[0] for r in cur.fetchall())
                if col != "paytrigger_device_id":  # TWIST 1.0 no usa paytrigger
                    cur.execute(
                        "SELECT DISTINCT d.imei FROM twist_contracts_user_prorroga p "
                        "JOIN twist_contract tc ON tc.id=p.twist_contract_id "
                        "JOIN twist_application ta ON ta.id=tc.twist_application_id "
                        f"JOIN {dev} d ON d.id=ta.{col} "
                        "WHERE p.active=1 AND p.created_at > %s "
                        "AND d.imei IS NOT NULL AND d.imei<>'' "
                        f"AND tc.twist_contract_status_id NOT IN ({est_ph})",
                        [desde] + est,
                    )
                    imeis.update(r[0] for r in cur.fetchall())
        return sorted(imeis)
