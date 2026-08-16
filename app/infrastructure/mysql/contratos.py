"""Adaptador MySQL del contexto CONTRATOS (PHONE / TWIST 1.0).

SQL copiado 1:1 del cliente original (candados_alotonic_repository). SOLO LECTURA.
Nombres de tabla/columna son literales fijos del catálogo; los valores van
parametrizados. Trampa central: los códigos de cuota ATRASADA difieren por familia
(PHONE=4, TWIST 1.0=3) — ver ``app.domain.catalogo``.
"""
from typing import Any

from app.config import Settings
from app.domain.catalogo import (
    ATRASADO_STATUS,
    DEVICE_FK,
    ESTADOS_NO_VIGENTES,
    placeholders,
)
from app.infrastructure.mysql.connection import conexion_legacy

_SQL_TITULAR_POR_IMEI = """
SELECT cu.dni          AS dni,
       cu.dni_type_id  AS dni_type_id,
       cu.email        AS email,
       v.contract_id   AS contract_id,
       v.imei          AS imei
FROM alocreditprod.view_contract_information v
JOIN alocreditprod.contract c    ON c.id = v.contract_id
JOIN alocreditprod.application a ON a.id = c.application_id
JOIN alocreditprod.customer cu   ON cu.id = a.customer_id
WHERE v.imei = %s
LIMIT 1
"""

# TWIST 1.0 es otra FAMILIA de contrato: view_contract_information no lo ve. OJO: la
# columna ``product`` de view_twist_contracts viene VACÍA (no distingue 1.0 de 2.0/3.0).
_SQL_TITULAR_TWIST_POR_IMEI = """
SELECT customer_dni          AS dni,
       customer_dni_type_id  AS dni_type_id,
       imei                  AS imei
FROM alocreditprod.view_twist_contracts
WHERE imei = %s
LIMIT 1
"""

# Titular por la cadena real candado -> application -> customer, por familia. Es el
# camino que NO depende de ninguna vista (las vistas no cubren todos los contratos).
_SQL_TITULAR_POR_APP = {
    "PHONE": """
        SELECT cu.dni, cu.dni_type_id, cu.email
        FROM alocreditprod.contract c
        JOIN alocreditprod.application a ON a.id = c.application_id
        JOIN alocreditprod.customer cu   ON cu.id = a.customer_id
        WHERE c.id = %s LIMIT 1
    """,
    "TWIST_1.0": """
        SELECT cu.dni, cu.dni_type_id, cu.email
        FROM alocreditprod.twist_contract tc
        JOIN alocreditprod.twist_application ta ON ta.id = tc.twist_application_id
        JOIN alocreditprod.customer cu          ON cu.id = ta.customer_id
        WHERE tc.id = %s LIMIT 1
    """,
}


def _contrato_vigente(cur, imei):
    """(familia, contract_id) del contrato VIGENTE más reciente del equipo, o
    ('', None). Gana el ACTIVO; a igualdad, el ``created_at`` más reciente.
    Considera todos los candados donde exista el IMEI."""
    candidatos = []  # (activo:int, created_at, familia, contract_id)
    for dev, col in DEVICE_FK:
        cur.execute(f"SELECT id FROM {dev} WHERE imei=%s", (imei,))
        for (did,) in cur.fetchall():
            cur.execute(
                f"SELECT c.id, CASE WHEN c.contracts_status_id NOT IN %s THEN 1 ELSE 0 END, "
                f"c.created_at FROM application a JOIN contract c ON c.application_id = a.id "
                f"WHERE a.{col} = %s ORDER BY 2 DESC, c.created_at DESC LIMIT 1",
                (ESTADOS_NO_VIGENTES, did),
            )
            r = cur.fetchone()
            if r and r[2] is not None:
                candidatos.append((r[1] or 0, r[2], "PHONE", r[0]))
            # twist_application NO tiene paytrigger_device_id (TWIST no usa ese candado).
            if col != "paytrigger_device_id":
                cur.execute(
                    f"SELECT tc.id, CASE WHEN tc.twist_contract_status_id NOT IN %s THEN 1 ELSE 0 END, "
                    f"tc.created_at FROM twist_application ta JOIN twist_contract tc "
                    f"ON tc.twist_application_id = ta.id WHERE ta.{col} = %s "
                    f"ORDER BY 2 DESC, tc.created_at DESC LIMIT 1",
                    (ESTADOS_NO_VIGENTES, did),
                )
                r = cur.fetchone()
                if r and r[2] is not None:
                    candidatos.append((r[1] or 0, r[2], "TWIST_1.0", r[0]))
    if not candidatos:
        return "", None
    candidatos.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidatos[0][2], candidatos[0][3]


def _reduce_prorroga_latest(rows, lockd, familia):
    """De filas (cid, lock_date, created_at) de prórrogas active=1, guarda en ``lockd``
    el lock_date de la MÁS RECIENTE por contrato (robusto ante >1 fila active=1)."""
    best = {}  # cid -> (created_at, lock_date)
    for cid, lock_date, created_at in rows:
        prev = best.get(cid)
        if prev is None or (created_at is not None and (prev[0] is None or created_at > prev[0])):
            best[cid] = (created_at, lock_date)
    for cid, (_, ld) in best.items():
        lockd[(familia, cid)] = ld


class RepositorioContratosMysql:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def estado_pago_por_imei(self, imeis: list[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        with conexion_legacy(self._settings) as conn:
            with conn.cursor() as cur:
                for imei in imeis:
                    familia, cid = _contrato_vigente(cur, imei)
                    if not familia or cid is None:
                        continue
                    if familia == "PHONE":
                        cur.execute(
                            "SELECT COUNT(*) FROM contract_amortization "
                            "WHERE contract_id=%s AND contract_amortization_payment_status_id=%s",
                            (cid, ATRASADO_STATUS["PHONE"]),
                        )
                    else:  # TWIST_1.0
                        cur.execute(
                            "SELECT COUNT(*) FROM twist_contract_amortization "
                            "WHERE twist_contract_id=%s AND twist_contract_payment_status_id=%s",
                            (cid, ATRASADO_STATUS["TWIST_1.0"]),
                        )
                    atrasadas = cur.fetchone()[0]
                    out[imei] = "en_mora" if atrasadas else "al_dia"
        return out

    def productos_por_imei(self, imeis: list[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        with conexion_legacy(self._settings) as conn:
            with conn.cursor() as cur:
                for imei in imeis:
                    prod, _ = _contrato_vigente(cur, imei)
                    if prod:
                        out[imei] = prod
        return out

    def estado_efectivo(self, imeis: list[str]) -> dict[str, list[dict[str, Any]]]:
        est_ph = placeholders(ESTADOS_NO_VIGENTES)
        est_vals = list(ESTADOS_NO_VIGENTES)
        with conexion_legacy(self._settings) as conn:
            with conn.cursor() as cur:
                # 1) (familia, contract_id) -> imei, vía cada candado y ambas familias.
                contrato_imei: dict[tuple[str, int], str] = {}
                for dev, col in DEVICE_FK:
                    cur.execute(
                        f"SELECT imei, id FROM {dev} WHERE imei IN ({placeholders(imeis)})",
                        list(imeis),
                    )
                    did_imei = {did: imei for (imei, did) in cur.fetchall()}
                    if not did_imei:
                        continue
                    dids = list(did_imei)
                    dph = placeholders(dids)
                    cur.execute(
                        f"SELECT a.{col}, c.id FROM application a "
                        "JOIN contract c ON c.application_id=a.id "
                        f"WHERE a.{col} IN ({dph}) AND c.contracts_status_id NOT IN ({est_ph})",
                        dids + est_vals,
                    )
                    for did, cid in cur.fetchall():
                        contrato_imei.setdefault(("PHONE", cid), did_imei[did])
                    # twist_application NO tiene paytrigger_device_id.
                    if col != "paytrigger_device_id":
                        cur.execute(
                            f"SELECT ta.{col}, tc.id FROM twist_application ta "
                            "JOIN twist_contract tc ON tc.twist_application_id=ta.id "
                            f"WHERE ta.{col} IN ({dph}) AND tc.twist_contract_status_id NOT IN ({est_ph})",
                            dids + est_vals,
                        )
                        for did, tcid in cur.fetchall():
                            contrato_imei.setdefault(("TWIST_1.0", tcid), did_imei[did])
                if not contrato_imei:
                    return {}

                phone_ids = [cid for (fam, cid) in contrato_imei if fam == "PHONE"]
                twist_ids = [cid for (fam, cid) in contrato_imei if fam == "TWIST_1.0"]

                # 2) mora (batch, agrupado por contrato)
                mora: set[tuple[str, int]] = set()
                if phone_ids:
                    cur.execute(
                        "SELECT contract_id FROM contract_amortization "
                        f"WHERE contract_id IN ({placeholders(phone_ids)}) "
                        "AND contract_amortization_payment_status_id=%s GROUP BY contract_id",
                        phone_ids + [ATRASADO_STATUS["PHONE"]],
                    )
                    mora.update(("PHONE", cid) for (cid,) in cur.fetchall())
                if twist_ids:
                    cur.execute(
                        "SELECT twist_contract_id FROM twist_contract_amortization "
                        f"WHERE twist_contract_id IN ({placeholders(twist_ids)}) "
                        "AND twist_contract_payment_status_id=%s GROUP BY twist_contract_id",
                        twist_ids + [ATRASADO_STATUS["TWIST_1.0"]],
                    )
                    mora.update(("TWIST_1.0", cid) for (cid,) in cur.fetchall())

                # 3) prórroga activa lock_date (batch)
                lockd: dict[tuple[str, int], Any] = {}
                if phone_ids:
                    cur.execute(
                        "SELECT contract_id, lock_date, created_at FROM contracts_user_prorroga "
                        f"WHERE active=1 AND contract_id IN ({placeholders(phone_ids)})",
                        phone_ids,
                    )
                    _reduce_prorroga_latest(cur.fetchall(), lockd, "PHONE")
                if twist_ids:
                    cur.execute(
                        "SELECT twist_contract_id, lock_date, created_at "
                        "FROM twist_contracts_user_prorroga "
                        f"WHERE active=1 AND twist_contract_id IN ({placeholders(twist_ids)})",
                        twist_ids,
                    )
                    _reduce_prorroga_latest(cur.fetchall(), lockd, "TWIST_1.0")

                # 4) armar salida por imei
                out: dict[str, list[dict[str, Any]]] = {}
                for (fam, cid), imei in contrato_imei.items():
                    out.setdefault(imei, []).append({
                        "familia": fam,
                        "contract_id": cid,
                        "en_mora": (fam, cid) in mora,
                        "lock_date": lockd.get((fam, cid)),
                    })
                return out

    def estado_release_por_imei(self, imei: str) -> tuple[str, int | None, str]:
        with conexion_legacy(self._settings) as conn:
            with conn.cursor() as cur:
                candidatos = []  # (created_at, familia, status_id, nombre)
                for dev, col in DEVICE_FK:
                    cur.execute(f"SELECT id FROM {dev} WHERE imei=%s", (imei,))
                    for (did,) in cur.fetchall():
                        cur.execute(
                            "SELECT c.contracts_status_id, s.name, c.created_at "
                            "FROM application a JOIN contract c ON c.application_id=a.id "
                            "JOIN contracts_status s ON s.id=c.contracts_status_id "
                            f"WHERE a.{col}=%s ORDER BY c.created_at DESC LIMIT 1",
                            (did,),
                        )
                        r = cur.fetchone()
                        if r and r[2] is not None:
                            candidatos.append((r[2], "PHONE", r[0], r[1]))
                        if col != "paytrigger_device_id":
                            cur.execute(
                                "SELECT tc.twist_contract_status_id, s.name, tc.created_at "
                                "FROM twist_application ta "
                                "JOIN twist_contract tc ON tc.twist_application_id=ta.id "
                                "JOIN twist_contract_status s ON s.id=tc.twist_contract_status_id "
                                f"WHERE ta.{col}=%s ORDER BY tc.created_at DESC LIMIT 1",
                                (did,),
                            )
                            r = cur.fetchone()
                            if r and r[2] is not None:
                                candidatos.append((r[2], "TWIST_1.0", r[0], r[1]))
                if not candidatos:
                    return "", None, ""
                # A diferencia de _contrato_vigente NO prioriza activos: es la regla de
                # LIBERACIÓN y manda el contrato más reciente a secas.
                candidatos.sort(key=lambda x: x[0], reverse=True)
                _created, familia, sid, nombre = candidatos[0]
                return familia, sid, nombre

    def _query_dicts(self, sql: str, params=None) -> list[dict[str, Any]]:
        with conexion_legacy(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or [])
                cols = [desc[0] for desc in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

    def titular_phone_por_imei(self, imei: str) -> dict[str, Any]:
        filas = self._query_dicts(_SQL_TITULAR_POR_IMEI, [imei])
        if not filas:
            # La vista NO cubre todos los contratos: se entra por el contrato real,
            # que además trae el TIPO de documento (sin él, un titular PPT recibe 400).
            return self.titular_por_contrato_vigente(imei)
        fila = filas[0]
        dni = str(fila.get("dni") or "").strip()
        if not dni:
            return self.titular_por_contrato_vigente(imei)
        return {
            "dni": dni,
            "doctype": int(fila.get("dni_type_id") or 0) or None,
            "email": str(fila.get("email") or "").strip(),
            "contract_id": fila.get("contract_id"),
            "imei": str(fila.get("imei") or imei).strip(),
        }

    def titular_twist_por_imei(self, imei: str) -> dict[str, Any]:
        filas = self._query_dicts(_SQL_TITULAR_TWIST_POR_IMEI, [imei])
        dni = str(filas[0].get("dni") or "").strip() if filas else ""
        if not dni:
            # Misma razón que en PHONE: sin tipo de documento un titular con PPT o CE
            # recibe 400 "Contrato no encontrado", así que se entra por el contrato real.
            return self.titular_por_contrato_vigente(imei)
        return {
            "dni": dni,
            "doctype": int(filas[0].get("dni_type_id") or 0) or None,
            "email": "",
            "contract_id": None,
            "imei": str(filas[0].get("imei") or imei).strip(),
        }

    def titular_por_contrato_vigente(self, imei: str) -> dict[str, Any]:
        with conexion_legacy(self._settings) as conn:
            with conn.cursor() as cur:
                familia, contrato_id = _contrato_vigente(cur, imei)
                sql = _SQL_TITULAR_POR_APP.get(familia)
                if not sql or contrato_id is None:
                    return {}
                cur.execute(sql, (contrato_id,))
                fila = cur.fetchone()
        if not fila:
            return {}
        dni = str(fila[0] or "").strip()
        if not dni:
            return {}
        return {
            "dni": dni,
            "doctype": int(fila[1] or 0) or None,
            "email": str(fila[2] or "").strip(),
            "contract_id": contrato_id,
            "imei": imei,
        }
