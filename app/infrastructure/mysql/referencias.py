"""Adaptador MySQL del contexto REFERENCIAS (referencia comercial por TAC).

SQL copiado 1:1 del cliente original. La cadena de enlace NO es directa:
``application.device_id`` apunta a ``device_prices`` (4,4M filas) y es
``device_prices.model_id`` el que apunta a ``devices`` (1.695 filas). Se usa
``devices.family`` (nombre comercial limpio) porque un mismo TAC cubre varias
variantes de almacenamiento que comparten ``family``. SOLO LECTURA y troceado:
nunca carga ``device_prices`` en memoria.
"""
from app.config import Settings
from app.domain.catalogo import MDM_CANDADO
from app.infrastructure.mysql.connection import conexion_legacy

_SQL_REF_POR_TAC = """
SELECT LEFT(dv.imei, 8) AS tac,
       d.family         AS referencia,
       d.manufactured   AS marca,
       d.description    AS referencia_larga,
       COUNT(*)         AS n
FROM {dev} dv
JOIN {app} ap        ON ap.{col} = dv.id
JOIN device_prices dp ON dp.id = ap.device_id
JOIN devices d        ON d.id = dp.model_id
WHERE ({likes})
  AND d.family IS NOT NULL AND d.family <> ''
GROUP BY tac, d.family, d.manufactured, d.description
ORDER BY tac, n DESC
"""

# Tope de TACs por consulta: cada TAC es un LIKE 'tac%' (rango de índice); con 50 el
# coste medido es ~234 ms y crece sublineal.
REF_TAC_CHUNK = 50


class RepositorioReferenciasMysql:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def referencias_por_tac(self, tacs: list[str], sistema: str) -> dict[str, dict[str, str]]:
        dev, col = MDM_CANDADO[sistema]
        # paytrigger (candado ALOTONIC) solo existe en PHONE; el resto también en TWIST 1.0.
        apps = ["application"] if col == "paytrigger_device_id" else ["application", "twist_application"]

        out: dict[str, dict] = {}
        with conexion_legacy(self._settings) as conn:
            with conn.cursor() as cur:
                for i in range(0, len(tacs), REF_TAC_CHUNK):
                    lote = tacs[i:i + REF_TAC_CHUNK]
                    likes = " OR ".join(["dv.imei LIKE %s"] * len(lote))
                    params = [f"{t}%" for t in lote]
                    for app in apps:
                        cur.execute(
                            _SQL_REF_POR_TAC.format(dev=dev, app=app, col=col, likes=likes),
                            params,
                        )
                        for tac, referencia, marca, larga, n in cur.fetchall():
                            prev = out.get(tac)
                            # ORDER BY n DESC deja la dominante primero DENTRO de cada
                            # familia; entre familias se compara el conteo.
                            if prev is None or n > prev["_n"]:
                                out[tac] = {"referencia": (referencia or "").strip(),
                                            "marca": (marca or "").strip(),
                                            "referencia_larga": (larga or "").strip(),
                                            "_n": n}
        for v in out.values():
            v.pop("_n", None)
        return out
