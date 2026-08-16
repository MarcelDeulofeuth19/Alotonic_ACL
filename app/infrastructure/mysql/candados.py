"""Adaptador MySQL del contexto CANDADOS (candado ALOTONIC/GlobeTek + prórrogas CRM).

SQL copiado 1:1 del cliente original de AloTonic (candados_alotonic_repository):
la paridad byte a byte de las consultas es la garantía de no cambiar comportamiento.
SOLO LECTURA. Nombres de tabla/columna son literales fijos; los valores van
parametrizados.
"""
from typing import Any

from app.config import Settings
from app.domain.catalogo import DEVICE_FK, PRORROGA_CRM, tipo_prorroga_crm
from app.domain.tiempo import ahora_local_legacy
from app.infrastructure.mysql.connection import conexion_legacy

# Consulta base de clientes con candado ALOTONIC + info de cuota/mora. El
# ``{imei_filter}`` se sustituye por una cláusula IN opcional o por "" (traer todos).
# Ordena morosos primero.
_SQL_CANDADOS = """
SELECT
    c.id                                                                 AS ContratoId,
    CONCAT('PH-', c.id)                                                  AS NumeroContrato,
    cu.dni                                                               AS DNI,
    TRIM(CONCAT_WS(' ', cu.name, cu.name2, cu.last_name, cu.last_name2)) AS Cliente,
    cu.email                                                             AS Email,
    cu.phone                                                             AS Celular,
    cu.phone2                                                            AS CelularAlt,
    cs.name                                                              AS EstadoContrato,
    c.signed_date                                                        AS FechaFirma,
    CAST(c.credit_price AS DECIMAL(18,2))                                AS MontoCredito,
    c.fee_number                                                         AS NumeroCuotas,
    pt.imei                                                              AS IMEI,
    pt.model                                                             AS Modelo,
    pt.serial_number                                                     AS Serial,
    pt.status                                                            AS EstadoCandado,
    pt.next_lock_date                                                    AS ProximoBloqueo,
    pt.device_ready                                                      AS DeviceReady,
    pt.sync_date                                                         AS UltimaSincronizacion,
    'ALOTONIC'                                                           AS TipoCandado,
    amort.prox_vencimiento                                               AS FechaProximaCuota,
    amort.dias_mora                                                      AS DiasMora,
    amort.saldo_pendiente                                                AS SaldoPendiente,
    amort.cuotas_pagadas                                                 AS CuotasPagadas,
    amort.cuotas_no_pagadas                                              AS CuotasNoPagadas,
    CASE
        WHEN COALESCE(amort.cuotas_no_pagadas, 0) = 0 THEN 'Sin cuotas pendientes'
        WHEN amort.dias_mora > 0                       THEN 'Atrasado'
        ELSE                                                'Al dia'
    END                                                                  AS EstadoMora
FROM alocreditprod.contract c
JOIN alocreditprod.application a        ON a.id = c.application_id
JOIN alocreditprod.customer cu          ON cu.id = a.customer_id
JOIN alocreditprod.contracts_status cs  ON cs.id = c.contracts_status_id
JOIN alocreditprod.paytrigger_device pt ON pt.id = a.paytrigger_device_id
LEFT JOIN (
    SELECT
        contract_id,
        MIN(CASE WHEN contract_amortization_payment_status_id IN (3, 4)
                 THEN expiration_date END)                            AS prox_vencimiento,
        GREATEST(0, DATEDIFF(CURDATE(),
            MIN(CASE WHEN contract_amortization_payment_status_id = 4
                     THEN expiration_date END))
        )                                                             AS dias_mora,
        ROUND(SUM(CASE WHEN contract_amortization_payment_status_id IN (3, 4)
                       THEN COALESCE(total_fee, 0) - COALESCE(amount_payed, 0)
                       ELSE 0 END), 2)                                AS saldo_pendiente,
        SUM(CASE WHEN contract_amortization_payment_status_id IN (1, 5) THEN 1 ELSE 0 END) AS cuotas_pagadas,
        SUM(CASE WHEN contract_amortization_payment_status_id IN (3, 4) THEN 1 ELSE 0 END) AS cuotas_no_pagadas
    FROM alocreditprod.contract_amortization
    GROUP BY contract_id
) amort ON amort.contract_id = c.id
WHERE cs.id NOT IN (4, 5, 6, 7, 8, 9)
  AND a.paytrigger_device_id IS NOT NULL
  {imei_filter}
ORDER BY EstadoMora DESC, DiasMora DESC, c.id DESC
"""


class RepositorioCandadosMysql:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _query_dicts(self, sql: str, params=None) -> list[dict[str, Any]]:
        with conexion_legacy(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or [])
                cols = [desc[0] for desc in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

    def consultar_candados(self, imeis: list[str] | None) -> list[dict[str, Any]]:
        if imeis:
            placeholders = ",".join(["%s"] * len(imeis))
            sql = _SQL_CANDADOS.format(imei_filter=f"AND pt.imei IN ({placeholders})")
            return self._query_dicts(sql, imeis)
        return self._query_dicts(_SQL_CANDADOS.format(imei_filter=""))

    def prorrogas_credito_por_imei(self, imei: str, limite: int) -> dict[str, Any]:
        with conexion_legacy(self._settings) as conn:
            with conn.cursor() as cur:
                filas = []  # (created_at, familia, lock_date, tipo, user_id, nota)
                prox_bloqueo = None
                estado_candado = None
                for dev, col in DEVICE_FK:
                    cur.execute(f"SELECT id, next_lock_date, status FROM {dev} WHERE imei=%s", (imei,))
                    for did, next_lock, estado in cur.fetchall():
                        # Gana el next_lock_date más lejano: es el bloqueo que realmente rige.
                        if next_lock is not None and (prox_bloqueo is None or next_lock > prox_bloqueo):
                            prox_bloqueo, estado_candado = next_lock, estado
                        for familia, tabla, fk_con, t_con, fk_app, t_app in PRORROGA_CRM:
                            # twist_application NO tiene paytrigger_device_id.
                            if familia == "TWIST_1.0" and col == "paytrigger_device_id":
                                continue
                            cur.execute(
                                f"SELECT p.created_at, p.lock_date, p.type, p.user_id, p.note "
                                f"FROM {tabla} p "
                                f"JOIN {t_con} c ON c.id = p.{fk_con} "
                                f"JOIN {t_app} ap ON ap.id = c.{fk_app} "
                                f"WHERE ap.{col} = %s ORDER BY p.created_at DESC LIMIT %s",
                                (did, limite),
                            )
                            for creado, lock_date, tipo, uid, nota in cur.fetchall():
                                filas.append((creado, familia, lock_date, tipo, uid, nota))

                ahora = ahora_local_legacy()
                filas.sort(key=lambda f: (f[0] is not None, f[0]), reverse=True)
                prorrogas = []
                for creado, familia, lock_date, tipo, uid, nota in filas[:limite]:
                    horas = None
                    if creado and lock_date:
                        horas = round((lock_date - creado).total_seconds() / 3600, 1)
                    prorrogas.append({
                        "familia": familia,
                        "tipo": tipo_prorroga_crm(tipo),
                        "otorgada_en": creado.strftime("%Y-%m-%d %H:%M:%S") if creado else None,
                        "vence_en": lock_date.strftime("%Y-%m-%d %H:%M:%S") if lock_date else None,
                        "horas": horas,
                        # Vigencia por lock_date, NUNCA por 'active' (el CRM lo apaga al procesar).
                        "vigente": bool(lock_date and ahora and lock_date > ahora),
                        "usuario_id": uid,
                        "nota": (nota or "").strip() or None,
                    })
                vigente = next((p for p in prorrogas if p["vigente"]), None)
                return {
                    "proximo_bloqueo": prox_bloqueo.strftime("%Y-%m-%d %H:%M:%S") if prox_bloqueo else None,
                    "estado_candado": (estado_candado or "").strip() or None,
                    "vigente": vigente,
                    "prorrogas": prorrogas,
                }
