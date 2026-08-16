"""Tests del adaptador MySQL de CANDADOS (app/infrastructure/mysql/candados.py).

Se verifica el SQL emitido y el post-procesado con el arnés de dobles de
``tests/fakes.py``: ningún acceso a base real.
"""
from datetime import datetime

import app.infrastructure.mysql.candados as modulo_candados
from app.infrastructure.mysql.candados import RepositorioCandadosMysql
from tests.fakes import parchear_conexion, settings_prueba

AHORA_FIJO = datetime(2026, 8, 15, 12, 0, 0)


def _repo() -> RepositorioCandadosMysql:
    return RepositorioCandadosMysql(settings_prueba())


# ---------------------------------------------------------------------------
# consultar_candados
# ---------------------------------------------------------------------------

def test_consultar_candados_sin_imeis_trae_todos_sin_filtro(monkeypatch):
    def responder(sql, params):
        return (["ContratoId", "IMEI"], [(1, "111111111111111"), (2, "222222222222222")])

    conn = parchear_conexion(monkeypatch, modulo_candados, responder)

    resultado = _repo().consultar_candados(None)

    assert resultado == [
        {"ContratoId": 1, "IMEI": "111111111111111"},
        {"ContratoId": 2, "IMEI": "222222222222222"},
    ]
    assert len(conn.cursor_falso.ejecutadas) == 1
    sql, params = conn.cursor_falso.ejecutadas[0]
    assert "pt.imei IN" not in sql
    assert "{imei_filter}" not in sql
    assert params == []


def test_consultar_candados_lista_vacia_equivale_a_todos(monkeypatch):
    def responder(sql, params):
        return (["ContratoId"], [(9,)])

    conn = parchear_conexion(monkeypatch, modulo_candados, responder)

    resultado = _repo().consultar_candados([])

    assert resultado == [{"ContratoId": 9}]
    sql, params = conn.cursor_falso.ejecutadas[0]
    assert "pt.imei IN" not in sql
    assert params == []


def test_consultar_candados_con_imeis_filtra_parametrizado(monkeypatch):
    def responder(sql, params):
        return (
            ["ContratoId", "IMEI", "EstadoMora"],
            [(7, "111111111111111", "Atrasado")],
        )

    conn = parchear_conexion(monkeypatch, modulo_candados, responder)

    resultado = _repo().consultar_candados(["111111111111111", "222222222222222"])

    assert resultado == [
        {"ContratoId": 7, "IMEI": "111111111111111", "EstadoMora": "Atrasado"}
    ]
    assert len(conn.cursor_falso.ejecutadas) == 1
    sql, params = conn.cursor_falso.ejecutadas[0]
    assert "AND pt.imei IN (%s,%s)" in sql
    assert params == ["111111111111111", "222222222222222"]


# ---------------------------------------------------------------------------
# prorrogas_credito_por_imei
# ---------------------------------------------------------------------------

IMEI = "350000000000001"

# Filas de device por tabla: (id, next_lock_date, status)
_DEVICES = {
    "paytrigger_device": [(11, datetime(2026, 8, 20, 0, 0, 0), "activo")],
    "knox_device": [(22, datetime(2026, 8, 30, 23, 59, 59), " bloqueado ")],
    # next_lock_date NULL: no debe pisar el próximo bloqueo.
    "nuovo_device": [(33, None, "irrelevante")],
    # next_lock_date más temprano que el de knox: tampoco gana.
    "trustonic_device": [(44, datetime(2026, 8, 18, 0, 0, 0), "no gana")],
}

# Prórrogas PHONE por device id: (created_at, lock_date, type, user_id, note)
_PRORROGAS_PHONE = {
    11: [
        (datetime(2026, 8, 1, 10, 0, 0), datetime(2026, 8, 10, 10, 0, 0), 1, 7, "  "),
        (datetime(2026, 8, 3, 8, 0, 0), None, 1, 5, "seguimiento"),
    ],
    22: [
        (datetime(2026, 8, 5, 9, 30, 0), datetime(2026, 8, 25, 0, 0, 0), 2, 3, " con espacios "),
    ],
}

# Prórrogas TWIST 1.0 por device id: created_at NULL debe ordenar al final.
_PRORROGAS_TWIST = {
    22: [(None, datetime(2026, 9, 1, 0, 0, 0), 0, None, None)],
}


def _responder_prorrogas(sql, params):
    for tabla, filas in _DEVICES.items():
        if f"FROM {tabla} WHERE imei=%s" in sql:
            assert params == (IMEI,)
            return filas
    if "FROM contracts_user_prorroga p" in sql:
        return _PRORROGAS_PHONE.get(params[0], [])
    if "FROM twist_contracts_user_prorroga p" in sql:
        return _PRORROGAS_TWIST.get(params[0], [])
    raise AssertionError(f"SQL inesperado: {sql}")


def _responder_sin_devices(sql, params):
    assert "WHERE imei=%s" in sql, f"SQL inesperado sin devices: {sql}"
    return []


def _fijar_ahora(monkeypatch):
    monkeypatch.setattr(modulo_candados, "ahora_local_legacy", lambda: AHORA_FIJO)


def test_prorrogas_arma_el_resumen_completo_ordenado_desc(monkeypatch):
    _fijar_ahora(monkeypatch)
    conn = parchear_conexion(monkeypatch, modulo_candados, _responder_prorrogas)

    resultado = _repo().prorrogas_credito_por_imei(IMEI, limite=10)

    # Gana el next_lock_date más lejano (knox), no el primero encontrado;
    # el status viaja stripeado.
    assert resultado["proximo_bloqueo"] == "2026-08-30 23:59:59"
    assert resultado["estado_candado"] == "bloqueado"

    assert resultado["prorrogas"] == [
        {
            "familia": "PHONE",
            "tipo": "canoa",
            "otorgada_en": "2026-08-05 09:30:00",
            "vence_en": "2026-08-25 00:00:00",
            "horas": 470.5,
            "vigente": True,
            "usuario_id": 3,
            "nota": "con espacios",
        },
        {
            "familia": "PHONE",
            "tipo": "salvavidas",
            "otorgada_en": "2026-08-03 08:00:00",
            "vence_en": None,
            "horas": None,
            "vigente": False,
            "usuario_id": 5,
            "nota": "seguimiento",
        },
        {
            "familia": "PHONE",
            "tipo": "salvavidas",
            "otorgada_en": "2026-08-01 10:00:00",
            "vence_en": "2026-08-10 10:00:00",
            "horas": 216.0,
            "vigente": False,
            "usuario_id": 7,
            "nota": None,
        },
        {
            "familia": "TWIST_1.0",
            "tipo": "otra",
            "otorgada_en": None,
            "vence_en": "2026-09-01 00:00:00",
            "horas": None,
            "vigente": True,
            "usuario_id": None,
            "nota": None,
        },
    ]
    # 'vigente' del dict superior = la PRIMERA prórroga vigente de la lista.
    assert resultado["vigente"] is resultado["prorrogas"][0]

    # Toda consulta de prórrogas lleva el límite parametrizado.
    consultas_prorroga = [
        (sql, params) for sql, params in conn.cursor_falso.ejecutadas
        if "_prorroga p" in sql
    ]
    assert consultas_prorroga, "no se consultó ninguna tabla de prórrogas"
    assert all(params[1] == 10 for _, params in consultas_prorroga)


def test_prorrogas_paytrigger_no_consulta_la_familia_twist(monkeypatch):
    _fijar_ahora(monkeypatch)
    conn = parchear_conexion(monkeypatch, modulo_candados, _responder_prorrogas)

    _repo().prorrogas_credito_por_imei(IMEI, limite=10)

    consultas_twist = [
        (sql, params) for sql, params in conn.cursor_falso.ejecutadas
        if "twist_contracts_user_prorroga" in sql
    ]
    # twist_application no tiene paytrigger_device_id: ni la columna ni el
    # device id de paytrigger (11) aparecen jamás en una consulta TWIST.
    assert consultas_twist, "las demás familias sí consultan TWIST"
    for sql, params in consultas_twist:
        assert "paytrigger_device_id" not in sql
        assert params[0] != 11
    # Y sí se consulta TWIST para knox (22), nuovo (33) y trustonic (44).
    assert sorted(params[0] for _, params in consultas_twist) == [22, 33, 44]


def test_prorrogas_respeta_el_limite_tras_ordenar(monkeypatch):
    _fijar_ahora(monkeypatch)
    parchear_conexion(monkeypatch, modulo_candados, _responder_prorrogas)

    resultado = _repo().prorrogas_credito_por_imei(IMEI, limite=3)

    # De las 4 filas totales, la de created_at NULL ordena al final y se corta.
    assert [p["otorgada_en"] for p in resultado["prorrogas"]] == [
        "2026-08-05 09:30:00",
        "2026-08-03 08:00:00",
        "2026-08-01 10:00:00",
    ]
    assert all(p["familia"] == "PHONE" for p in resultado["prorrogas"])
    assert resultado["vigente"] is resultado["prorrogas"][0]


def test_prorrogas_sin_filas_devuelve_el_dict_vacio(monkeypatch):
    conn = parchear_conexion(monkeypatch, modulo_candados, _responder_sin_devices)

    resultado = _repo().prorrogas_credito_por_imei(IMEI, limite=5)

    assert resultado == {
        "proximo_bloqueo": None,
        "estado_candado": None,
        "vigente": None,
        "prorrogas": [],
    }
    # Solo las 4 consultas de device (una por tabla), ninguna de prórrogas.
    assert len(conn.cursor_falso.ejecutadas) == 4
    assert all("WHERE imei=%s" in sql for sql, _ in conn.cursor_falso.ejecutadas)
