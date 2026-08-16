"""Tests unitarios de los casos de uso (app/application/use_cases.py).

Dobles simples de los puertos: clases que graban los argumentos recibidos y
devuelven valores fijos, para asertar tanto la delegación exacta como los
retornos degenerados que NO deben tocar el repositorio.
"""
from datetime import datetime, timezone

import pytest

from app.application import use_cases
from app.domain import catalogo
from app.domain.exceptions import ErrorAcl, PeticionInvalida


# ---------------------------------------------------------------------------
# Dobles de puertos
# ---------------------------------------------------------------------------

class CandadosDoble:
    def __init__(self):
        self.llamadas = []
        self.respuesta_candados = [{"imei": "111", "estado": "vigente"}]
        self.respuesta_prorrogas = {
            "proximo_bloqueo": "2026-08-25", "estado_candado": "bloqueado",
            "vigente": True, "prorrogas": [{"tipo": "canoa"}],
        }

    def consultar_candados(self, imeis):
        self.llamadas.append(("consultar_candados", imeis))
        return self.respuesta_candados

    def prorrogas_credito_por_imei(self, imei, limite):
        self.llamadas.append(("prorrogas_credito_por_imei", imei, limite))
        return self.respuesta_prorrogas


class ContratosDoble:
    def __init__(self):
        self.llamadas = []

    def estado_pago_por_imei(self, imeis):
        self.llamadas.append(("estado_pago_por_imei", imeis))
        return {"111": "Al dia"}

    def productos_por_imei(self, imeis):
        self.llamadas.append(("productos_por_imei", imeis))
        return {"111": "PHONE"}

    def estado_efectivo(self, imeis):
        self.llamadas.append(("estado_efectivo", imeis))
        return {"111": [{"contrato": 7}]}

    def estado_release_por_imei(self, imei):
        self.llamadas.append(("estado_release_por_imei", imei))
        return ("Completado", 4, "PHONE")

    def titular_phone_por_imei(self, imei):
        self.llamadas.append(("titular_phone_por_imei", imei))
        return {"nombre": "Fulano PHONE"}

    def titular_twist_por_imei(self, imei):
        self.llamadas.append(("titular_twist_por_imei", imei))
        return {"nombre": "Fulana TWIST"}


class PertenenciaDoble:
    def __init__(self):
        self.llamadas = []
        self.presentes = {"333", "111", "222"}
        self.conteo = 41000

    def imeis_en_tabla(self, tabla, imeis):
        self.llamadas.append(("imeis_en_tabla", tabla, imeis))
        return set(self.presentes)

    def conteo_tabla(self, tabla):
        self.llamadas.append(("conteo_tabla", tabla))
        return self.conteo


class ProrrogasDoble:
    def __init__(self):
        self.llamadas = []
        self.respuesta_cortas = [{"imei": "111", "lock_date": "2026-08-25"}]
        self.respuesta_nuevas = ["111", "222"]

    def cortas_vencidas(self, sistema, horas_ventana, max_horas_rango, limite):
        self.llamadas.append(("cortas_vencidas", sistema, horas_ventana,
                              max_horas_rango, limite))
        return self.respuesta_cortas

    def imeis_con_prorroga_nueva(self, sistema, desde):
        self.llamadas.append(("imeis_con_prorroga_nueva", sistema, desde))
        return self.respuesta_nuevas


class PoblacionDoble:
    def __init__(self):
        self.llamadas = []

    def imeis_candado(self, sistema, limit, desde_imei):
        self.llamadas.append(("imeis_candado", sistema, limit, desde_imei))
        return ["111", "222"]

    def imei_modelo_candado(self, sistema, solo_vigentes):
        self.llamadas.append(("imei_modelo_candado", sistema, solo_vigentes))
        return [("111", "KM8"), ("222", "KN8")]


class ReferenciasDoble:
    def __init__(self):
        self.llamadas = []

    def referencias_por_tac(self, tacs, sistema):
        self.llamadas.append(("referencias_por_tac", tacs, sistema))
        return {"35123": {"referencia": "Moto G24", "marca": "motorola"}}


class InformesDoble:
    def __init__(self):
        self.llamadas = []

    def contratos_por_lock_system(self, lock_system):
        self.llamadas.append(("contratos_por_lock_system", lock_system))
        return [{"contract_id": 9, "lock_system": lock_system}]

    def catalogo_device_location(self):
        self.llamadas.append(("catalogo_device_location",))
        return [("KM8", "globetek"), ("SM-A155M", "knox")]


# ---------------------------------------------------------------------------
# sanear_imeis
# ---------------------------------------------------------------------------

def test_sanear_imeis_none_devuelve_lista_vacia():
    assert use_cases.sanear_imeis(None) == []


def test_sanear_imeis_lista_vacia_devuelve_lista_vacia():
    assert use_cases.sanear_imeis([]) == []


def test_sanear_imeis_filtra_vacios_y_espacios():
    assert use_cases.sanear_imeis(["", "  ", " 111 "]) == ["111"]


def test_sanear_imeis_convierte_numeros_a_texto():
    assert use_cases.sanear_imeis([869402081272963, 123]) == ["869402081272963", "123"]


def test_sanear_imeis_none_dentro_de_la_lista_no_se_vuelve_none_literal():
    # Bug histórico: str(None) = 'None' colaba un IMEI literal 'None'.
    saneados = use_cases.sanear_imeis([None, " 111 ", None])
    assert saneados == ["111"]
    assert "None" not in saneados


# ---------------------------------------------------------------------------
# consultar_candados
# ---------------------------------------------------------------------------

def test_consultar_candados_lista_vacia_llega_al_repo_como_none():
    repo = CandadosDoble()
    resultado = use_cases.consultar_candados(repo, [])
    assert resultado == [{"imei": "111", "estado": "vigente"}]
    assert repo.llamadas == [("consultar_candados", None)]


def test_consultar_candados_none_llega_al_repo_como_none():
    repo = CandadosDoble()
    use_cases.consultar_candados(repo, None)
    assert repo.llamadas == [("consultar_candados", None)]


def test_consultar_candados_imeis_saneados_llegan_limpios():
    repo = CandadosDoble()
    use_cases.consultar_candados(repo, [" 111 ", None, 222, ""])
    assert repo.llamadas == [("consultar_candados", ["111", "222"])]


# ---------------------------------------------------------------------------
# prorrogas_credito_por_imei
# ---------------------------------------------------------------------------

def test_prorrogas_credito_imei_vacio_devuelve_vacio_sin_llamar_al_repo():
    repo = CandadosDoble()
    resultado = use_cases.prorrogas_credito_por_imei(repo, "  ", 8)
    assert resultado == {"proximo_bloqueo": None, "estado_candado": None,
                         "vigente": None, "prorrogas": []}
    assert repo.llamadas == []


def test_prorrogas_credito_imei_none_devuelve_vacio_sin_llamar_al_repo():
    repo = CandadosDoble()
    assert use_cases.prorrogas_credito_por_imei(repo, None, 8) == \
        use_cases.VACIO_PRORROGAS_CREDITO
    assert repo.llamadas == []


def test_prorrogas_credito_vacio_es_copia_y_no_muta_el_global():
    resultado = use_cases.prorrogas_credito_por_imei(CandadosDoble(), "", 8)
    assert resultado is not use_cases.VACIO_PRORROGAS_CREDITO
    # Mutar la copia devuelta no debe contaminar las claves del global
    # (dict() es copia superficial: las CLAVES quedan protegidas).
    resultado["vigente"] = True
    resultado["estado_candado"] = "bloqueado"
    assert use_cases.VACIO_PRORROGAS_CREDITO["vigente"] is None
    assert use_cases.VACIO_PRORROGAS_CREDITO["estado_candado"] is None


@pytest.mark.parametrize("limite, esperado", [
    (None, 8),   # sin límite -> 8 por defecto
    (0, 8),      # 0 es falsy -> or 8
    (999, 50),   # techo en 50
    (-5, 1),     # piso en 1
    ("3", 3),    # string numérico se castea
])
def test_prorrogas_credito_clamps_de_limite(limite, esperado):
    repo = CandadosDoble()
    resultado = use_cases.prorrogas_credito_por_imei(repo, " 111 ", limite)
    assert resultado == repo.respuesta_prorrogas
    assert repo.llamadas == [("prorrogas_credito_por_imei", "111", esperado)]


# ---------------------------------------------------------------------------
# estado_pago / productos / estado_efectivo
# ---------------------------------------------------------------------------

def test_estado_pago_imeis_vacios_devuelve_dict_vacio_sin_repo():
    repo = ContratosDoble()
    assert use_cases.estado_pago_por_imei(repo, [None, "", "  "]) == {}
    assert repo.llamadas == []


def test_estado_pago_con_datos_delega_saneado():
    repo = ContratosDoble()
    assert use_cases.estado_pago_por_imei(repo, [" 111 "]) == {"111": "Al dia"}
    assert repo.llamadas == [("estado_pago_por_imei", ["111"])]


def test_productos_imeis_vacios_devuelve_dict_vacio_sin_repo():
    repo = ContratosDoble()
    assert use_cases.productos_por_imei(repo, None) == {}
    assert repo.llamadas == []


def test_productos_con_datos_delega_saneado():
    repo = ContratosDoble()
    assert use_cases.productos_por_imei(repo, [111, " 222 "]) == {"111": "PHONE"}
    assert repo.llamadas == [("productos_por_imei", ["111", "222"])]


def test_estado_efectivo_imeis_vacios_devuelve_dict_vacio_sin_repo():
    repo = ContratosDoble()
    assert use_cases.estado_efectivo(repo, []) == {}
    assert repo.llamadas == []


def test_estado_efectivo_con_datos_delega_saneado():
    repo = ContratosDoble()
    assert use_cases.estado_efectivo(repo, ["111", None]) == {"111": [{"contrato": 7}]}
    assert repo.llamadas == [("estado_efectivo", ["111"])]


# ---------------------------------------------------------------------------
# estado_release_por_imei
# ---------------------------------------------------------------------------

def test_estado_release_imei_vacio_devuelve_tupla_degenerada_sin_repo():
    repo = ContratosDoble()
    assert use_cases.estado_release_por_imei(repo, "   ") == ("", None, "")
    assert use_cases.estado_release_por_imei(repo, None) == ("", None, "")
    assert repo.llamadas == []


def test_estado_release_con_imei_delega_con_strip():
    repo = ContratosDoble()
    assert use_cases.estado_release_por_imei(repo, " 111 ") == ("Completado", 4, "PHONE")
    assert repo.llamadas == [("estado_release_por_imei", "111")]


# ---------------------------------------------------------------------------
# titular_por_imei
# ---------------------------------------------------------------------------

def test_titular_familia_twist_1_0_va_por_titular_twist():
    repo = ContratosDoble()
    assert use_cases.titular_por_imei(repo, " 111 ", "TWIST_1.0") == \
        {"nombre": "Fulana TWIST"}
    assert repo.llamadas == [("titular_twist_por_imei", "111")]


@pytest.mark.parametrize("familia", ["PHONE", "", "TWIST_2.0"])
def test_titular_otras_familias_van_por_titular_phone(familia):
    repo = ContratosDoble()
    assert use_cases.titular_por_imei(repo, "111", familia) == \
        {"nombre": "Fulano PHONE"}
    assert repo.llamadas == [("titular_phone_por_imei", "111")]


def test_titular_imei_vacio_devuelve_dict_vacio_sin_repo():
    repo = ContratosDoble()
    assert use_cases.titular_por_imei(repo, "  ", "TWIST_1.0") == {}
    assert use_cases.titular_por_imei(repo, None, "PHONE") == {}
    assert repo.llamadas == []


# ---------------------------------------------------------------------------
# pertenencia
# ---------------------------------------------------------------------------

def test_pertenencia_tabla_desconocida_lanza_peticion_invalida_con_el_nombre():
    repo = PertenenciaDoble()
    with pytest.raises(PeticionInvalida) as exc:
        use_cases.pertenencia(repo, ["nuovo", "zzz", "aaa"], ["111"])
    assert str(exc.value) == "tablas desconocidas: aaa, zzz"
    assert repo.llamadas == []


def test_pertenencia_sin_tablas_lanza_peticion_invalida():
    repo = PertenenciaDoble()
    with pytest.raises(PeticionInvalida) as exc:
        use_cases.pertenencia(repo, [], ["111"])
    assert str(exc.value) == "se requiere al menos una tabla"
    with pytest.raises(PeticionInvalida):
        use_cases.pertenencia(repo, None, ["111"])
    assert repo.llamadas == []


def test_pertenencia_imeis_vacios_devuelve_listas_vacias_sin_repo():
    repo = PertenenciaDoble()
    assert use_cases.pertenencia(repo, ["knox", "nuovo"], []) == \
        {"knox": [], "nuovo": []}
    assert use_cases.pertenencia(repo, ["paytrigger"], [None, "  "]) == \
        {"paytrigger": []}
    assert repo.llamadas == []


def test_pertenencia_devuelve_los_presentes_ordenados_por_tabla():
    repo = PertenenciaDoble()
    resultado = use_cases.pertenencia(repo, ["trustonic", "knox"], [" 333 ", 111, "222"])
    assert resultado == {"trustonic": ["111", "222", "333"],
                         "knox": ["111", "222", "333"]}
    assert repo.llamadas == [
        ("imeis_en_tabla", "trustonic", ["333", "111", "222"]),
        ("imeis_en_tabla", "knox", ["333", "111", "222"]),
    ]


# ---------------------------------------------------------------------------
# conteo_tabla
# ---------------------------------------------------------------------------

def test_conteo_tabla_desconocida_lanza_peticion_invalida():
    repo = PertenenciaDoble()
    with pytest.raises(PeticionInvalida) as exc:
        use_cases.conteo_tabla(repo, "globetek")
    assert str(exc.value) == "tabla desconocida: globetek"
    assert repo.llamadas == []


def test_conteo_tabla_valida_delega_y_devuelve_el_conteo():
    repo = PertenenciaDoble()
    assert use_cases.conteo_tabla(repo, "knox") == 41000
    assert repo.llamadas == [("conteo_tabla", "knox")]


# ---------------------------------------------------------------------------
# prorrogas_cortas_vencidas
# ---------------------------------------------------------------------------

def test_prorrogas_cortas_sistema_invalido_devuelve_lista_vacia_sin_repo():
    repo = ProrrogasDoble()
    assert use_cases.prorrogas_cortas_vencidas(repo, "paytrigger", 6, 48, 10) == []
    assert use_cases.prorrogas_cortas_vencidas(repo, None, 6, 48, 10) == []
    assert repo.llamadas == []


@pytest.mark.parametrize("limite, esperado", [
    (None, 500),   # sin límite -> 500 por defecto
    (9999, 5000),  # techo en 5000
    (0, 500),      # 0 es falsy -> or 500
])
def test_prorrogas_cortas_clamps_de_limite(limite, esperado):
    repo = ProrrogasDoble()
    resultado = use_cases.prorrogas_cortas_vencidas(repo, "globetek", 6, 48, limite)
    assert resultado == repo.respuesta_cortas
    assert repo.llamadas == [("cortas_vencidas", "globetek", 6, 48, esperado)]


def test_prorrogas_cortas_castea_las_horas_a_int():
    repo = ProrrogasDoble()
    use_cases.prorrogas_cortas_vencidas(repo, "knox", "6", 48.9, 10)
    assert repo.llamadas == [("cortas_vencidas", "knox", 6, 48, 10)]
    assert isinstance(repo.llamadas[0][2], int)
    assert isinstance(repo.llamadas[0][3], int)


# ---------------------------------------------------------------------------
# imeis_con_prorroga_nueva
# ---------------------------------------------------------------------------

def test_imeis_con_prorroga_nueva_sistema_invalido_o_desde_none_devuelve_vacio():
    repo = ProrrogasDoble()
    assert use_cases.imeis_con_prorroga_nueva(repo, "motosafe",
                                              datetime(2026, 8, 16, 12, 0)) == []
    assert use_cases.imeis_con_prorroga_nueva(repo, "knox", None) == []
    assert repo.llamadas == []


def test_imeis_con_prorroga_nueva_convierte_aware_utc_a_bogota_naive():
    repo = ProrrogasDoble()
    desde_utc = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    resultado = use_cases.imeis_con_prorroga_nueva(repo, "trustonic", desde_utc)
    assert resultado == ["111", "222"]
    # Bogotá = UTC-5 sin DST: 12:00Z -> 07:00 local, SIN tzinfo.
    assert repo.llamadas == [
        ("imeis_con_prorroga_nueva", "trustonic", datetime(2026, 8, 16, 7, 0)),
    ]
    assert repo.llamadas[0][2].tzinfo is None


def test_imeis_con_prorroga_nueva_naive_pasa_tal_cual():
    repo = ProrrogasDoble()
    desde = datetime(2026, 8, 16, 7, 30)
    use_cases.imeis_con_prorroga_nueva(repo, "nuovo", desde)
    assert repo.llamadas == [("imeis_con_prorroga_nueva", "nuovo",
                              datetime(2026, 8, 16, 7, 30))]


# ---------------------------------------------------------------------------
# imeis_candado / imei_modelo_candado
# ---------------------------------------------------------------------------

def test_imeis_candado_sistema_invalido_devuelve_vacio_sin_repo():
    repo = PoblacionDoble()
    assert use_cases.imeis_candado(repo, "paytrigger", 100, None) == []
    assert repo.llamadas == []


def test_imeis_candado_valido_delega_limit_y_cursor_tal_cual():
    repo = PoblacionDoble()
    assert use_cases.imeis_candado(repo, "globetek", 100, "555") == ["111", "222"]
    assert repo.llamadas == [("imeis_candado", "globetek", 100, "555")]


def test_imei_modelo_candado_sistema_invalido_devuelve_vacio_sin_repo():
    repo = PoblacionDoble()
    assert use_cases.imei_modelo_candado(repo, "samsung", 1) == []
    assert repo.llamadas == []


@pytest.mark.parametrize("solo_vigentes, esperado", [(1, True), ("", False), (None, False)])
def test_imei_modelo_candado_castea_solo_vigentes_a_bool(solo_vigentes, esperado):
    repo = PoblacionDoble()
    assert use_cases.imei_modelo_candado(repo, "knox", solo_vigentes) == \
        [("111", "KM8"), ("222", "KN8")]
    assert repo.llamadas == [("imei_modelo_candado", "knox", esperado)]
    assert repo.llamadas[0][2] is esperado


# ---------------------------------------------------------------------------
# referencias_por_tac
# ---------------------------------------------------------------------------

def test_referencias_por_tac_dedupe_y_orden_de_tacs():
    repo = ReferenciasDoble()
    resultado = use_cases.referencias_por_tac(
        repo, [" 35123 ", "35123", None, 351, "  "], "knox")
    assert resultado == {"35123": {"referencia": "Moto G24", "marca": "motorola"}}
    assert repo.llamadas == [("referencias_por_tac", ["351", "35123"], "knox")]


def test_referencias_por_tac_sistema_invalido_devuelve_vacio_sin_repo():
    repo = ReferenciasDoble()
    assert use_cases.referencias_por_tac(repo, ["35123"], "paytrigger") == {}
    assert repo.llamadas == []


def test_referencias_por_tac_tacs_vacios_devuelve_vacio_sin_repo():
    repo = ReferenciasDoble()
    assert use_cases.referencias_por_tac(repo, [], "knox") == {}
    assert use_cases.referencias_por_tac(repo, [None, "  "], "nuovo") == {}
    assert repo.llamadas == []


# ---------------------------------------------------------------------------
# contratos_por_lock_system / catalogo_device_location
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lock_system", [None, "", "   "])
def test_contratos_por_lock_system_vacio_lanza_peticion_invalida(lock_system):
    repo = InformesDoble()
    with pytest.raises(PeticionInvalida) as exc:
        use_cases.contratos_por_lock_system(repo, lock_system)
    assert str(exc.value) == "se requiere lock_system"
    assert repo.llamadas == []


def test_contratos_por_lock_system_valido_delega_con_strip():
    repo = InformesDoble()
    assert use_cases.contratos_por_lock_system(repo, " KNOX ") == \
        [{"contract_id": 9, "lock_system": "KNOX"}]
    assert repo.llamadas == [("contratos_por_lock_system", "KNOX")]


def test_catalogo_device_location_delega_en_el_repo():
    repo = InformesDoble()
    assert use_cases.catalogo_device_location(repo) == \
        [("KM8", "globetek"), ("SM-A155M", "knox")]
    assert repo.llamadas == [("catalogo_device_location",)]


# ---------------------------------------------------------------------------
# Dominio: catálogo y excepciones (helpers)
# ---------------------------------------------------------------------------

def test_tipo_prorroga_crm_resuelve_los_nombres_conocidos():
    assert catalogo.tipo_prorroga_crm(0) == "otra"
    assert catalogo.tipo_prorroga_crm(1) == "salvavidas"
    assert catalogo.tipo_prorroga_crm("2") == "canoa"


def test_tipo_prorroga_crm_id_desconocido_devuelve_tipo_n():
    assert catalogo.tipo_prorroga_crm(99) == "tipo_99"


@pytest.mark.parametrize("tipo", [None, "abc"])
def test_tipo_prorroga_crm_no_numerico_devuelve_desconocido(tipo):
    assert catalogo.tipo_prorroga_crm(tipo) == "desconocido"


def test_placeholders_genera_un_marcador_por_valor():
    assert catalogo.placeholders(["a", "b", "c"]) == "%s,%s,%s"
    assert catalogo.placeholders([]) == ""


def test_peticion_invalida_hereda_de_error_acl():
    assert issubclass(PeticionInvalida, ErrorAcl)
    assert issubclass(ErrorAcl, Exception)
