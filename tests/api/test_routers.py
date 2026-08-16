"""Tests de los routers HTTP (app/presentation/api/routers/*), de las fábricas
de repos (app/presentation/api/repos.py) y de los manejadores de error de
app/main.py.

Los repos MySQL se sustituyen por dobles vía ``app.dependency_overrides`` sobre
``cliente.app`` (la app la crea la fixture ``cliente``); ningún test toca MySQL.
"""
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.config import get_settings
from app.domain.exceptions import BaseLegacyNoDisponible
from app.presentation.api import repos
from tests.conftest import ENTORNO_PRUEBA

# ---------------------------------------------------------------------------
# Dobles de los puertos: registran las llamadas y devuelven datos representativos
# (con datetime/date/Decimal donde el router aplica a_json).
# ---------------------------------------------------------------------------


class DobleCandados:
    def __init__(self):
        self.llamadas = []

    def consultar_candados(self, imeis):
        self.llamadas.append(("consultar_candados", imeis))
        return [{
            "imei": "350000000000001",
            "cuota": Decimal("123.45"),
            "proximo_bloqueo": datetime(2026, 8, 25, 0, 0, 0),
            "fecha_cuota": date(2026, 8, 20),
            "en_mora": True,
        }]

    def prorrogas_credito_por_imei(self, imei, limite):
        self.llamadas.append(("prorrogas_credito_por_imei", imei, limite))
        return {
            "proximo_bloqueo": "2026-08-25 00:00:00",
            "estado_candado": "prorrogado",
            "vigente": True,
            "prorrogas": [{"tipo": "canoa", "lock_date": "2026-08-25 00:00:00"}],
        }


class DobleContratos:
    def __init__(self):
        self.llamadas = []

    def estado_pago_por_imei(self, imeis):
        self.llamadas.append(("estado_pago_por_imei", imeis))
        return {"350000000000001": "en_mora", "350000000000002": "al_dia"}

    def productos_por_imei(self, imeis):
        self.llamadas.append(("productos_por_imei", imeis))
        return {"350000000000001": "PHONE", "350000000000002": "TWIST_1.0"}

    def estado_efectivo(self, imeis):
        self.llamadas.append(("estado_efectivo", imeis))
        return {"350000000000001": [{
            "familia": "PHONE",
            "contract_id": 77,
            "en_mora": True,
            "lock_date": datetime(2026, 8, 25, 23, 59, 59),
        }]}

    def estado_release_por_imei(self, imei):
        self.llamadas.append(("estado_release_por_imei", imei))
        return ("PHONE", 4, "Completado")

    def titular_phone_por_imei(self, imei):
        self.llamadas.append(("titular_phone_por_imei", imei))
        return {"dni": "123", "doctype": "CC", "email": "p@alocredit.co",
                "contract_id": 77, "imei": imei}

    def titular_twist_por_imei(self, imei):
        self.llamadas.append(("titular_twist_por_imei", imei))
        return {"dni": "999", "doctype": "CE", "email": "t@alocredit.co",
                "contract_id": 88, "imei": imei}


class DoblePertenencia:
    def __init__(self):
        self.llamadas = []

    def imeis_en_tabla(self, tabla, imeis):
        self.llamadas.append(("imeis_en_tabla", tabla, imeis))
        return {"350000000000002", "350000000000001"}

    def conteo_tabla(self, tabla):
        self.llamadas.append(("conteo_tabla", tabla))
        return 41234


class DobleProrrogas:
    def __init__(self):
        self.llamadas = []

    def cortas_vencidas(self, sistema, horas_ventana, max_horas_rango, limite):
        self.llamadas.append(("cortas_vencidas", sistema, horas_ventana,
                              max_horas_rango, limite))
        return [{"imei": "350000000000001", "lock_date": "2026-08-15 10:00:00"}]

    def imeis_con_prorroga_nueva(self, sistema, desde):
        self.llamadas.append(("imeis_con_prorroga_nueva", sistema, desde))
        return ["350000000000001", "350000000000002"]


class DoblePoblacion:
    def __init__(self):
        self.llamadas = []

    def imeis_candado(self, sistema, limit, desde_imei):
        self.llamadas.append(("imeis_candado", sistema, limit, desde_imei))
        return ["350000000000001", "350000000000002"]

    def imei_modelo_candado(self, sistema, solo_vigentes):
        self.llamadas.append(("imei_modelo_candado", sistema, solo_vigentes))
        return [("350000000000001", "SM-A125M"), ("350000000000002", "moto g24")]


class DobleReferencias:
    def __init__(self):
        self.llamadas = []

    def referencias_por_tac(self, tacs, sistema):
        self.llamadas.append(("referencias_por_tac", tacs, sistema))
        return {"35000000": {"referencia": "KN8", "marca": "KRONO",
                             "referencia_larga": "KRONO NET 8"}}


class DobleInformes:
    def __init__(self):
        self.llamadas = []

    def contratos_por_lock_system(self, lock_system):
        self.llamadas.append(("contratos_por_lock_system", lock_system))
        return [{"contract_id": 77, "saldo": Decimal("999.99"),
                 "fecha_corte": date(2026, 8, 15), "status": "Atrasado"}]

    def catalogo_device_location(self):
        self.llamadas.append(("catalogo_device_location",))
        return [("Bodega Norte", "KM8n,KM8"), ("Tienda 1", "KN8")]


class DobleContratosCaido:
    """Simula la base legacy caída: cualquier método revienta como el adaptador real."""

    def estado_pago_por_imei(self, imeis):
        raise BaseLegacyNoDisponible("timeout simulado del driver")


def _instalar(cliente, fabrica, doble):
    cliente.app.dependency_overrides[fabrica] = lambda: doble
    return doble


# ---------------------------------------------------------------------------
# /candados
# ---------------------------------------------------------------------------


def test_candados_consultar_con_imeis_sanea_y_etiqueta_tipos(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_candados, DobleCandados())
    r = cliente.post("/api/v1/candados/consultar", headers=cabeceras_auth,
                     json={"imeis": [" 350000000000001 ", "350000000000002"]})
    assert r.status_code == 200
    assert r.json() == {"filas": [{
        "imei": "350000000000001",
        "cuota": {"$tipo": "decimal", "$v": "123.45"},
        "proximo_bloqueo": {"$tipo": "datetime", "$v": "2026-08-25T00:00:00"},
        "fecha_cuota": {"$tipo": "date", "$v": "2026-08-20"},
        "en_mora": True,
    }]}
    # El router saneó (strip) y pasó la lista limpia al repo.
    assert doble.llamadas == [("consultar_candados",
                               ["350000000000001", "350000000000002"])]


def test_candados_consultar_sin_imeis_pide_el_listado_completo(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_candados, DobleCandados())
    r = cliente.post("/api/v1/candados/consultar", headers=cabeceras_auth, json={})
    assert r.status_code == 200
    # Sin imeis el repo recibe None (contrato original: listado completo).
    assert doble.llamadas == [("consultar_candados", None)]


def test_candados_prorrogas_credito_con_limite_explicito(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_candados, DobleCandados())
    r = cliente.get("/api/v1/candados/prorrogas-credito/350000000000001",
                    headers=cabeceras_auth, params={"limite": 3})
    assert r.status_code == 200
    assert r.json() == {
        "proximo_bloqueo": "2026-08-25 00:00:00",
        "estado_candado": "prorrogado",
        "vigente": True,
        "prorrogas": [{"tipo": "canoa", "lock_date": "2026-08-25 00:00:00"}],
    }
    assert doble.llamadas == [("prorrogas_credito_por_imei", "350000000000001", 3)]


def test_candados_prorrogas_credito_limite_por_defecto_es_8(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_candados, DobleCandados())
    r = cliente.get("/api/v1/candados/prorrogas-credito/350000000000001",
                    headers=cabeceras_auth)
    assert r.status_code == 200
    assert doble.llamadas == [("prorrogas_credito_por_imei", "350000000000001", 8)]


# ---------------------------------------------------------------------------
# /contratos
# ---------------------------------------------------------------------------


def test_contratos_productos_devuelve_familia_por_imei(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_contratos, DobleContratos())
    r = cliente.post("/api/v1/contratos/productos", headers=cabeceras_auth,
                     json={"imeis": ["350000000000001", "350000000000002"]})
    assert r.status_code == 200
    assert r.json() == {"productos": {"350000000000001": "PHONE",
                                      "350000000000002": "TWIST_1.0"}}
    assert doble.llamadas == [("productos_por_imei",
                               ["350000000000001", "350000000000002"])]


def test_contratos_estado_pago_devuelve_mora_por_imei(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_contratos, DobleContratos())
    r = cliente.post("/api/v1/contratos/estado-pago", headers=cabeceras_auth,
                     json={"imeis": ["350000000000001", "350000000000002"]})
    assert r.status_code == 200
    assert r.json() == {"estados": {"350000000000001": "en_mora",
                                    "350000000000002": "al_dia"}}
    assert doble.llamadas == [("estado_pago_por_imei",
                               ["350000000000001", "350000000000002"])]


def test_contratos_estado_efectivo_etiqueta_lock_date_como_datetime(cliente, cabeceras_auth):
    _instalar(cliente, repos.get_repo_contratos, DobleContratos())
    r = cliente.post("/api/v1/contratos/estado-efectivo", headers=cabeceras_auth,
                     json={"imeis": ["350000000000001"]})
    assert r.status_code == 200
    assert r.json() == {"contratos": {"350000000000001": [{
        "familia": "PHONE",
        "contract_id": 77,
        "en_mora": True,
        "lock_date": {"$tipo": "datetime", "$v": "2026-08-25T23:59:59"},
    }]}}


def test_contratos_estado_release_expone_familia_y_status(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_contratos, DobleContratos())
    r = cliente.get("/api/v1/contratos/estado-release/350000000000001",
                    headers=cabeceras_auth)
    assert r.status_code == 200
    assert r.json() == {"familia": "PHONE", "status_id": 4,
                        "status_nombre": "Completado"}
    assert doble.llamadas == [("estado_release_por_imei", "350000000000001")]


def test_contratos_titular_sin_familia_entra_por_phone(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_contratos, DobleContratos())
    r = cliente.get("/api/v1/contratos/titular/350000000000001", headers=cabeceras_auth)
    assert r.status_code == 200
    assert r.json() == {"titular": {"dni": "123", "doctype": "CC",
                                    "email": "p@alocredit.co", "contract_id": 77,
                                    "imei": "350000000000001"}}
    assert doble.llamadas == [("titular_phone_por_imei", "350000000000001")]


def test_contratos_titular_con_familia_twist_entra_por_twist(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_contratos, DobleContratos())
    r = cliente.get("/api/v1/contratos/titular/350000000000001",
                    headers=cabeceras_auth, params={"familia": "TWIST_1.0"})
    assert r.status_code == 200
    assert r.json() == {"titular": {"dni": "999", "doctype": "CE",
                                    "email": "t@alocredit.co", "contract_id": 88,
                                    "imei": "350000000000001"}}
    assert doble.llamadas == [("titular_twist_por_imei", "350000000000001")]


# ---------------------------------------------------------------------------
# /dispositivos
# ---------------------------------------------------------------------------


def test_dispositivos_pertenencia_devuelve_presentes_ordenados_por_tabla(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_pertenencia, DoblePertenencia())
    r = cliente.post("/api/v1/dispositivos/pertenencia", headers=cabeceras_auth,
                     json={"tablas": ["knox", "nuovo"],
                           "imeis": ["350000000000001", "350000000000002"]})
    assert r.status_code == 200
    assert r.json() == {"pertenencia": {
        "knox": ["350000000000001", "350000000000002"],
        "nuovo": ["350000000000001", "350000000000002"],
    }}
    assert doble.llamadas == [
        ("imeis_en_tabla", "knox", ["350000000000001", "350000000000002"]),
        ("imeis_en_tabla", "nuovo", ["350000000000001", "350000000000002"]),
    ]


def test_dispositivos_pertenencia_tabla_desconocida_es_422_con_detalle(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_pertenencia, DoblePertenencia())
    r = cliente.post("/api/v1/dispositivos/pertenencia", headers=cabeceras_auth,
                     json={"tablas": ["knox", "globetek"], "imeis": ["350000000000001"]})
    assert r.status_code == 422
    assert r.json() == {"detail": "tablas desconocidas: globetek"}
    assert doble.llamadas == []


def test_dispositivos_conteo_de_tabla_conocida(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_pertenencia, DoblePertenencia())
    r = cliente.get("/api/v1/dispositivos/conteo/knox", headers=cabeceras_auth)
    assert r.status_code == 200
    assert r.json() == {"total": 41234}
    assert doble.llamadas == [("conteo_tabla", "knox")]


def test_dispositivos_conteo_tabla_desconocida_es_422_con_detalle(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_pertenencia, DoblePertenencia())
    r = cliente.get("/api/v1/dispositivos/conteo/globetek", headers=cabeceras_auth)
    assert r.status_code == 422
    assert r.json() == {"detail": "tabla desconocida: globetek"}
    assert doble.llamadas == []


# ---------------------------------------------------------------------------
# /prorrogas
# ---------------------------------------------------------------------------


def test_prorrogas_cortas_vencidas_pasa_los_parametros_al_repo(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_prorrogas, DobleProrrogas())
    r = cliente.get("/api/v1/prorrogas/cortas-vencidas", headers=cabeceras_auth,
                    params={"sistema": "knox", "horas_ventana": 2,
                            "max_horas_rango": 12, "limite": 100})
    assert r.status_code == 200
    assert r.json() == {"filas": [{"imei": "350000000000001",
                                   "lock_date": "2026-08-15 10:00:00"}]}
    assert doble.llamadas == [("cortas_vencidas", "knox", 2, 12, 100)]


def test_prorrogas_cortas_vencidas_sistema_invalido_devuelve_vacio_sin_tocar_repo(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_prorrogas, DobleProrrogas())
    r = cliente.get("/api/v1/prorrogas/cortas-vencidas", headers=cabeceras_auth,
                    params={"sistema": "comodin"})
    assert r.status_code == 200
    assert r.json() == {"filas": []}
    assert doble.llamadas == []


def test_prorrogas_nuevas_convierte_el_cursor_con_zona_a_hora_local_legacy(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_prorrogas, DobleProrrogas())
    r = cliente.get("/api/v1/prorrogas/nuevas", headers=cabeceras_auth,
                    params={"sistema": "trustonic", "desde": "2026-08-16T10:00:00Z"})
    assert r.status_code == 200
    assert r.json() == {"imeis": ["350000000000001", "350000000000002"]}
    # 10:00 UTC = 05:00 Bogotá, y llega NAIVE (escala guardada del legacy).
    assert doble.llamadas == [("imeis_con_prorroga_nueva", "trustonic",
                               datetime(2026, 8, 16, 5, 0, 0))]


def test_prorrogas_nuevas_desde_invalido_es_422_de_pydantic(cliente, cabeceras_auth):
    _instalar(cliente, repos.get_repo_prorrogas, DobleProrrogas())
    r = cliente.get("/api/v1/prorrogas/nuevas", headers=cabeceras_auth,
                    params={"sistema": "knox", "desde": "no-es-una-fecha"})
    assert r.status_code == 422
    detalle = r.json()["detail"]
    assert isinstance(detalle, list)  # formato de error de validación de pydantic
    assert detalle[0]["loc"] == ["query", "desde"]


# ---------------------------------------------------------------------------
# /poblacion
# ---------------------------------------------------------------------------


def test_poblacion_imeis_pasa_cursor_y_limite_al_repo(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_poblacion, DoblePoblacion())
    r = cliente.get("/api/v1/poblacion/imeis", headers=cabeceras_auth,
                    params={"sistema": "knox", "limit": 2,
                            "desde_imei": "350000000000000"})
    assert r.status_code == 200
    assert r.json() == {"imeis": ["350000000000001", "350000000000002"]}
    assert doble.llamadas == [("imeis_candado", "knox", 2, "350000000000000")]


def test_poblacion_imeis_sin_paginacion_manda_none(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_poblacion, DoblePoblacion())
    r = cliente.get("/api/v1/poblacion/imeis", headers=cabeceras_auth,
                    params={"sistema": "globetek"})
    assert r.status_code == 200
    assert doble.llamadas == [("imeis_candado", "globetek", None, None)]


def test_poblacion_imei_modelo_con_solo_vigentes(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_poblacion, DoblePoblacion())
    r = cliente.get("/api/v1/poblacion/imei-modelo", headers=cabeceras_auth,
                    params={"sistema": "globetek", "solo_vigentes": "true"})
    assert r.status_code == 200
    # Las tuplas del repo viajan como listas JSON.
    assert r.json() == {"filas": [["350000000000001", "SM-A125M"],
                                  ["350000000000002", "moto g24"]]}
    assert doble.llamadas == [("imei_modelo_candado", "globetek", True)]


def test_poblacion_imei_modelo_por_defecto_no_filtra_vigentes(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_poblacion, DoblePoblacion())
    r = cliente.get("/api/v1/poblacion/imei-modelo", headers=cabeceras_auth,
                    params={"sistema": "nuovo"})
    assert r.status_code == 200
    assert doble.llamadas == [("imei_modelo_candado", "nuovo", False)]


# ---------------------------------------------------------------------------
# /referencias
# ---------------------------------------------------------------------------


def test_referencias_por_tac_sanea_y_deduplica_los_tacs(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_referencias, DobleReferencias())
    r = cliente.post("/api/v1/referencias/por-tac", headers=cabeceras_auth,
                     json={"sistema": "knox", "tacs": [" 35000000 ", "35000000", ""]})
    assert r.status_code == 200
    assert r.json() == {"referencias": {"35000000": {
        "referencia": "KN8", "marca": "KRONO", "referencia_larga": "KRONO NET 8",
    }}}
    assert doble.llamadas == [("referencias_por_tac", ["35000000"], "knox")]


# ---------------------------------------------------------------------------
# /informes
# ---------------------------------------------------------------------------


def test_informes_contratos_lock_system_etiqueta_decimal_y_date(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_informes, DobleInformes())
    r = cliente.get("/api/v1/informes/contratos-lock-system", headers=cabeceras_auth,
                    params={"sistema": "ALOTONIC"})
    assert r.status_code == 200
    assert r.json() == {"filas": [{
        "contract_id": 77,
        "saldo": {"$tipo": "decimal", "$v": "999.99"},
        "fecha_corte": {"$tipo": "date", "$v": "2026-08-15"},
        "status": "Atrasado",
    }]}
    assert doble.llamadas == [("contratos_por_lock_system", "ALOTONIC")]


def test_informes_contratos_lock_system_vacio_es_422_con_detalle(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_informes, DobleInformes())
    r = cliente.get("/api/v1/informes/contratos-lock-system", headers=cabeceras_auth,
                    params={"sistema": "   "})
    assert r.status_code == 422
    assert r.json() == {"detail": "se requiere lock_system"}
    assert doble.llamadas == []


def test_informes_catalogo_device_location_devuelve_las_filas(cliente, cabeceras_auth):
    doble = _instalar(cliente, repos.get_repo_informes, DobleInformes())
    r = cliente.get("/api/v1/informes/catalogo-device-location", headers=cabeceras_auth)
    assert r.status_code == 200
    assert r.json() == {"filas": [["Bodega Norte", "KM8n,KM8"], ["Tienda 1", "KN8"]]}
    assert doble.llamadas == [("catalogo_device_location",)]


# ---------------------------------------------------------------------------
# Autenticación: TODOS los endpoints rechazan sin clave y con clave incorrecta.
# ---------------------------------------------------------------------------

RUTAS_PROTEGIDAS = [
    ("post", "/api/v1/candados/consultar", {"imeis": ["350000000000001"]}),
    ("get", "/api/v1/candados/prorrogas-credito/350000000000001", None),
    ("post", "/api/v1/contratos/productos", {"imeis": ["350000000000001"]}),
    ("post", "/api/v1/contratos/estado-pago", {"imeis": ["350000000000001"]}),
    ("post", "/api/v1/contratos/estado-efectivo", {"imeis": ["350000000000001"]}),
    ("get", "/api/v1/contratos/estado-release/350000000000001", None),
    ("get", "/api/v1/contratos/titular/350000000000001", None),
    ("post", "/api/v1/dispositivos/pertenencia",
     {"tablas": ["knox"], "imeis": ["350000000000001"]}),
    ("get", "/api/v1/dispositivos/conteo/knox", None),
    ("get", "/api/v1/prorrogas/cortas-vencidas?sistema=knox", None),
    ("get", "/api/v1/prorrogas/nuevas?sistema=knox&desde=2026-01-01T00:00:00", None),
    ("get", "/api/v1/poblacion/imeis?sistema=knox", None),
    ("get", "/api/v1/poblacion/imei-modelo?sistema=knox", None),
    ("post", "/api/v1/referencias/por-tac", {"sistema": "knox", "tacs": ["35000000"]}),
    ("get", "/api/v1/informes/contratos-lock-system?sistema=ALOTONIC", None),
    ("get", "/api/v1/informes/catalogo-device-location", None),
]


@pytest.mark.parametrize("metodo, ruta, cuerpo", RUTAS_PROTEGIDAS,
                         ids=[r[1] for r in RUTAS_PROTEGIDAS])
def test_endpoint_sin_api_key_es_401(cliente, metodo, ruta, cuerpo):
    r = getattr(cliente, metodo)(ruta, json=cuerpo) if cuerpo is not None \
        else getattr(cliente, metodo)(ruta)
    assert r.status_code == 401
    assert r.json() == {"detail": "API key invalida o ausente"}


@pytest.mark.parametrize("metodo, ruta, cuerpo", RUTAS_PROTEGIDAS,
                         ids=[r[1] for r in RUTAS_PROTEGIDAS])
def test_endpoint_con_api_key_incorrecta_es_401(cliente, metodo, ruta, cuerpo):
    cabeceras = {"X-Api-Key": "clave-equivocada"}
    r = getattr(cliente, metodo)(ruta, headers=cabeceras, json=cuerpo) \
        if cuerpo is not None else getattr(cliente, metodo)(ruta, headers=cabeceras)
    assert r.status_code == 401
    assert r.json() == {"detail": "API key invalida o ausente"}


# ---------------------------------------------------------------------------
# Manejadores de error de app/main.py
# ---------------------------------------------------------------------------


def test_base_legacy_caida_se_traduce_a_503_generico(cliente, cabeceras_auth):
    _instalar(cliente, repos.get_repo_contratos, DobleContratosCaido())
    r = cliente.post("/api/v1/contratos/estado-pago", headers=cabeceras_auth,
                     json={"imeis": ["350000000000001"]})
    assert r.status_code == 503
    assert r.json() == {"detail": "base legacy no disponible"}


def test_health_sigue_vivo_y_sin_api_key(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "alotonic-acl"}


# ---------------------------------------------------------------------------
# Tope de IMEIs por petición (validar_tope_imeis vía HTTP)
# ---------------------------------------------------------------------------


def test_tope_de_imeis_configurado_rechaza_el_exceso_con_422(cliente, cabeceras_auth, monkeypatch):
    doble = _instalar(cliente, repos.get_repo_candados, DobleCandados())
    monkeypatch.setenv("MAX_IMEIS_POR_PETICION", "3")
    get_settings.cache_clear()
    r = cliente.post("/api/v1/candados/consultar", headers=cabeceras_auth,
                     json={"imeis": ["1", "2", "3", "4"]})
    assert r.status_code == 422
    assert r.json() == {"detail": "maximo 3 IMEIs por peticion"}
    assert doble.llamadas == []


def test_tope_de_imeis_justo_en_el_limite_pasa(cliente, cabeceras_auth, monkeypatch):
    doble = _instalar(cliente, repos.get_repo_candados, DobleCandados())
    monkeypatch.setenv("MAX_IMEIS_POR_PETICION", "3")
    get_settings.cache_clear()
    r = cliente.post("/api/v1/candados/consultar", headers=cabeceras_auth,
                     json={"imeis": ["1", "2", "3"]})
    assert r.status_code == 200
    assert doble.llamadas == [("consultar_candados", ["1", "2", "3"])]


# ---------------------------------------------------------------------------
# Cuerpos inválidos -> 422 de pydantic
# ---------------------------------------------------------------------------


def test_body_invalido_en_consultar_es_422_de_pydantic(cliente, cabeceras_auth):
    _instalar(cliente, repos.get_repo_candados, DobleCandados())
    r = cliente.post("/api/v1/candados/consultar", headers=cabeceras_auth,
                     json={"imeis": "no-es-una-lista"})
    assert r.status_code == 422
    detalle = r.json()["detail"]
    assert isinstance(detalle, list)
    assert detalle[0]["loc"][:2] == ["body", "imeis"]


def test_body_sin_campos_obligatorios_en_pertenencia_es_422(cliente, cabeceras_auth):
    _instalar(cliente, repos.get_repo_pertenencia, DoblePertenencia())
    r = cliente.post("/api/v1/dispositivos/pertenencia", headers=cabeceras_auth,
                     json={})
    assert r.status_code == 422
    campos_faltantes = {tuple(e["loc"]) for e in r.json()["detail"]}
    assert ("body", "tablas") in campos_faltantes
    assert ("body", "imeis") in campos_faltantes


# ---------------------------------------------------------------------------
# Fábricas de repos (repos.py): construyen su adaptador sin abrir conexión.
# ---------------------------------------------------------------------------


def test_fabricas_de_repos_construyen_el_adaptador_mysql_correcto(monkeypatch):
    from app.infrastructure.mysql.candados import RepositorioCandadosMysql
    from app.infrastructure.mysql.contratos import RepositorioContratosMysql
    from app.infrastructure.mysql.informes import RepositorioInformesMysql
    from app.infrastructure.mysql.pertenencia import RepositorioPertenenciaMysql
    from app.infrastructure.mysql.poblacion import RepositorioPoblacionMysql
    from app.infrastructure.mysql.prorrogas import RepositorioProrrogasMysql
    from app.infrastructure.mysql.referencias import RepositorioReferenciasMysql

    for clave, valor in ENTORNO_PRUEBA.items():
        monkeypatch.setenv(clave, valor)
    get_settings.cache_clear()
    try:
        assert isinstance(repos.get_repo_candados(), RepositorioCandadosMysql)
        assert isinstance(repos.get_repo_contratos(), RepositorioContratosMysql)
        assert isinstance(repos.get_repo_pertenencia(), RepositorioPertenenciaMysql)
        assert isinstance(repos.get_repo_prorrogas(), RepositorioProrrogasMysql)
        assert isinstance(repos.get_repo_poblacion(), RepositorioPoblacionMysql)
        assert isinstance(repos.get_repo_referencias(), RepositorioReferenciasMysql)
        assert isinstance(repos.get_repo_informes(), RepositorioInformesMysql)
    finally:
        get_settings.cache_clear()
