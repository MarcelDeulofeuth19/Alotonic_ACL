"""Tests del adaptador MySQL del contexto CONTRATOS (app/infrastructure/mysql/contratos.py).

Cada test define un ``responder(sql, params)`` (ver tests/fakes.py) que simula la
base legacy: se verifica el SQL/params emitidos (los códigos de mora POR FAMILIA,
qué tablas se consultan) y el post-procesado exacto de las filas.
"""
from datetime import date, datetime

from app.domain.catalogo import ATRASADO_STATUS, ESTADOS_NO_VIGENTES
from app.infrastructure.mysql import contratos
from app.infrastructure.mysql.contratos import (
    RepositorioContratosMysql,
    _contrato_vigente,
    _reduce_prorroga_latest,
)
from tests.fakes import CursorFalso, parchear_conexion, settings_prueba


def _repo() -> RepositorioContratosMysql:
    return RepositorioContratosMysql(settings_prueba())


# ---------------------------------------------------------------------------
# _contrato_vigente (directo, con CursorFalso)
# ---------------------------------------------------------------------------

def test_contrato_vigente_phone_activo_gana_sobre_twist_viejo():
    """Un PHONE ACTIVO gana aunque el TWIST cerrado tenga created_at más reciente."""
    def responder(sql, params):
        if sql.startswith("SELECT id FROM knox_device"):
            return [(10,)]
        if sql.startswith("SELECT id FROM"):
            return []
        if "FROM application a JOIN contract c" in sql:
            return [(100, 1, datetime(2024, 1, 1))]
        if "FROM twist_application ta JOIN twist_contract tc" in sql:
            return [(200, 0, datetime(2026, 1, 1))]
        raise AssertionError(f"SQL inesperado: {sql}")

    cur = CursorFalso(responder)
    assert _contrato_vigente(cur, "356111") == ("PHONE", 100)


def test_contrato_vigente_empate_activo_gana_created_at_mas_reciente():
    """Dos PHONE activos (dos devices con el mismo IMEI): gana el más reciente."""
    def responder(sql, params):
        if sql.startswith("SELECT id FROM knox_device"):
            return [(10,), (11,)]
        if sql.startswith("SELECT id FROM"):
            return []
        if "FROM application a JOIN contract c" in sql:
            did = params[1]
            if did == 10:
                return [(100, 1, datetime(2024, 1, 1))]
            return [(101, 1, datetime(2025, 6, 1))]
        if "FROM twist_application ta JOIN twist_contract tc" in sql:
            return []
        raise AssertionError(f"SQL inesperado: {sql}")

    cur = CursorFalso(responder)
    assert _contrato_vigente(cur, "356111") == ("PHONE", 101)


def test_contrato_vigente_sin_candidatos_devuelve_vacio():
    cur = CursorFalso(lambda sql, params: [])
    assert _contrato_vigente(cur, "356999") == ("", None)
    # Consultó las 4 tablas de candado y nada más (sin devices no hay contratos).
    tablas = [s.split("FROM ")[1].split(" ")[0] for s, _ in cur.ejecutadas]
    assert tablas == ["paytrigger_device", "knox_device", "nuovo_device", "trustonic_device"]


def test_contrato_vigente_descarta_filas_con_created_at_none():
    """created_at None se descarta en AMBAS familias; sobrevive el TWIST válido."""
    def responder(sql, params):
        if sql.startswith("SELECT id FROM knox_device"):
            return [(10,)]
        if sql.startswith("SELECT id FROM nuovo_device"):
            return [(30,)]
        if sql.startswith("SELECT id FROM"):
            return []
        if "FROM application a JOIN contract c" in sql:
            # knox: PHONE con created_at None (descartado); nuovo: sin contrato.
            return [(100, 1, None)] if params[1] == 10 else []
        if "FROM twist_application ta JOIN twist_contract tc" in sql:
            # knox: TWIST válido; nuovo: TWIST con created_at None (descartado).
            if params[1] == 10:
                return [(200, 0, datetime(2024, 3, 3))]
            return [(300, 1, None)]
        raise AssertionError(f"SQL inesperado: {sql}")

    cur = CursorFalso(responder)
    assert _contrato_vigente(cur, "356111") == ("TWIST_1.0", 200)


def test_contrato_vigente_paytrigger_no_consulta_twist():
    """twist_application no tiene paytrigger_device_id: con paytrigger NO se toca TWIST."""
    def responder(sql, params):
        if sql.startswith("SELECT id FROM paytrigger_device"):
            return [(5,)]
        if sql.startswith("SELECT id FROM"):
            return []
        if "FROM application a JOIN contract c" in sql:
            assert "a.paytrigger_device_id = %s" in sql
            assert params == (ESTADOS_NO_VIGENTES, 5)
            return [(100, 1, datetime(2026, 2, 2))]
        raise AssertionError(f"SQL inesperado: {sql}")

    cur = CursorFalso(responder)
    assert _contrato_vigente(cur, "356111") == ("PHONE", 100)
    assert not any("twist" in s for s, _ in cur.ejecutadas)


# ---------------------------------------------------------------------------
# _reduce_prorroga_latest (directo)
# ---------------------------------------------------------------------------

def test_reduce_prorroga_latest_gana_created_at_mas_reciente_incluso_con_none():
    lockd = {}
    filas = [
        (200, date(2026, 8, 25), None),                  # primera fila (sin created_at)
        (200, date(2026, 9, 1), datetime(2026, 8, 10)),  # la más reciente: GANA
        (200, date(2026, 7, 1), datetime(2026, 8, 1)),   # más vieja: pierde
        (200, date(2026, 6, 1), None),                   # None tardío: pierde
        (300, date(2026, 5, 5), datetime(2026, 1, 1)),   # otro contrato, independiente
    ]
    _reduce_prorroga_latest(filas, lockd, "TWIST_1.0")
    assert lockd == {
        ("TWIST_1.0", 200): date(2026, 9, 1),
        ("TWIST_1.0", 300): date(2026, 5, 5),
    }


# ---------------------------------------------------------------------------
# estado_pago_por_imei
# ---------------------------------------------------------------------------

def test_estado_pago_phone_en_mora_usa_codigo_4(monkeypatch):
    def responder(sql, params):
        if sql.startswith("SELECT id FROM knox_device"):
            return [(10,)]
        if sql.startswith("SELECT id FROM"):
            return []
        if "FROM application a JOIN contract c" in sql:
            return [(100, 1, datetime(2026, 1, 5))]
        if "FROM twist_application ta JOIN twist_contract tc" in sql:
            return []
        if "FROM contract_amortization" in sql:
            return [(2,)]
        raise AssertionError(f"SQL inesperado: {sql}")

    conn = parchear_conexion(monkeypatch, contratos, responder)
    assert _repo().estado_pago_por_imei(["356111"]) == {"356111": "en_mora"}
    conteos = [(s, p) for s, p in conn.cursor_falso.ejecutadas
               if "FROM contract_amortization" in s]
    assert len(conteos) == 1
    assert conteos[0][1] == (100, ATRASADO_STATUS["PHONE"])   # PHONE: atrasado = 4
    assert conteos[0][1][1] == 4


def test_estado_pago_twist_al_dia_usa_codigo_3(monkeypatch):
    def responder(sql, params):
        if sql.startswith("SELECT id FROM trustonic_device"):
            return [(20,)]
        if sql.startswith("SELECT id FROM"):
            return []
        if "FROM application a JOIN contract c" in sql:
            return []
        if "FROM twist_application ta JOIN twist_contract tc" in sql:
            return [(200, 1, datetime(2026, 2, 2))]
        if "FROM twist_contract_amortization" in sql:
            return [(0,)]
        raise AssertionError(f"SQL inesperado: {sql}")

    conn = parchear_conexion(monkeypatch, contratos, responder)
    assert _repo().estado_pago_por_imei(["356222"]) == {"356222": "al_dia"}
    ejecutadas = conn.cursor_falso.ejecutadas
    conteos = [(s, p) for s, p in ejecutadas if "FROM twist_contract_amortization" in s]
    assert len(conteos) == 1
    assert conteos[0][1] == (200, ATRASADO_STATUS["TWIST_1.0"])   # TWIST 1.0: atrasado = 3
    assert conteos[0][1][1] == 3
    # Jamás la tabla de cuotas de PHONE para un contrato TWIST.
    assert not any("FROM contract_amortization" in s for s, _ in ejecutadas)


def test_estado_pago_imei_sin_contrato_no_aparece(monkeypatch):
    def responder(sql, params):
        if sql.startswith("SELECT id FROM knox_device"):
            return [(10,)] if params == ("356111",) else []
        if sql.startswith("SELECT id FROM"):
            return []
        if "FROM application a JOIN contract c" in sql:
            return [(100, 1, datetime(2026, 1, 5))]
        if "FROM twist_application ta JOIN twist_contract tc" in sql:
            return []
        if "FROM contract_amortization" in sql:
            return [(0,)]
        raise AssertionError(f"SQL inesperado: {sql}")

    parchear_conexion(monkeypatch, contratos, responder)
    assert _repo().estado_pago_por_imei(["356111", "356999"]) == {"356111": "al_dia"}


# ---------------------------------------------------------------------------
# productos_por_imei
# ---------------------------------------------------------------------------

def test_productos_por_imei_mapea_familia_y_omite_sin_contrato(monkeypatch):
    def responder(sql, params):
        if sql.startswith("SELECT id FROM trustonic_device"):
            return [(20,)] if params == ("356222",) else []
        if sql.startswith("SELECT id FROM"):
            return []
        if "FROM application a JOIN contract c" in sql:
            return []
        if "FROM twist_application ta JOIN twist_contract tc" in sql:
            return [(200, 1, datetime(2026, 2, 2))]
        raise AssertionError(f"SQL inesperado: {sql}")

    parchear_conexion(monkeypatch, contratos, responder)
    assert _repo().productos_por_imei(["356222", "356999"]) == {"356222": "TWIST_1.0"}


# ---------------------------------------------------------------------------
# estado_efectivo
# ---------------------------------------------------------------------------

def test_estado_efectivo_flujo_batch_completo(monkeypatch):
    """Devices por tabla, contratos PHONE+TWIST vigentes, mora batch con el código
    por familia y prórroga active=1 reducida a la más reciente por contrato."""
    def responder(sql, params):
        if sql.startswith("SELECT imei, id FROM paytrigger_device"):
            assert params == ["356111", "356222"]
            return [("356111", 5)]
        if sql.startswith("SELECT imei, id FROM trustonic_device"):
            return [("356222", 20)]
        if sql.startswith("SELECT imei, id FROM"):
            return []   # knox / nuovo sin devices -> continue
        if "FROM application a" in sql and "a.paytrigger_device_id IN" in sql:
            assert params == [5] + list(ESTADOS_NO_VIGENTES)
            return [(5, 100)]
        if "FROM application a" in sql and "a.trustonic_device_id IN" in sql:
            return []
        if "FROM twist_application ta" in sql:
            assert "ta.trustonic_device_id IN" in sql
            assert params == [20] + list(ESTADOS_NO_VIGENTES)
            return [(20, 200)]
        if "FROM contract_amortization" in sql:
            return [(100,)]      # PHONE 100 con cuotas atrasadas
        if "FROM twist_contract_amortization" in sql:
            return []            # TWIST 200 al día
        if "FROM contracts_user_prorroga" in sql:
            return []
        if "FROM twist_contracts_user_prorroga" in sql:
            assert "active=1" in sql
            return [
                (200, date(2026, 8, 25), None),
                (200, date(2026, 9, 1), datetime(2026, 8, 10)),  # más reciente: GANA
                (200, date(2026, 7, 1), datetime(2026, 8, 1)),
            ]
        raise AssertionError(f"SQL inesperado: {sql}")

    conn = parchear_conexion(monkeypatch, contratos, responder)
    assert _repo().estado_efectivo(["356111", "356222"]) == {
        "356111": [{"familia": "PHONE", "contract_id": 100,
                    "en_mora": True, "lock_date": None}],
        "356222": [{"familia": "TWIST_1.0", "contract_id": 200,
                    "en_mora": False, "lock_date": date(2026, 9, 1)}],
    }
    ejecutadas = conn.cursor_falso.ejecutadas
    mora_phone = [p for s, p in ejecutadas if "FROM contract_amortization" in s]
    assert mora_phone == [[100, ATRASADO_STATUS["PHONE"]]]        # código 4
    mora_twist = [p for s, p in ejecutadas if "FROM twist_contract_amortization" in s]
    assert mora_twist == [[200, ATRASADO_STATUS["TWIST_1.0"]]]    # código 3
    prorroga_twist = [p for s, p in ejecutadas if "FROM twist_contracts_user_prorroga" in s]
    assert prorroga_twist == [[200]]
    # Para paytrigger jamás se consulta twist_application.
    assert not any("ta.paytrigger_device_id" in s for s, _ in ejecutadas)


def test_estado_efectivo_sin_contratos_devuelve_vacio(monkeypatch):
    """Device encontrado pero sin contrato vigente en ninguna familia -> {}."""
    def responder(sql, params):
        if sql.startswith("SELECT imei, id FROM knox_device"):
            return [("356111", 10)]
        if sql.startswith("SELECT imei, id FROM"):
            return []
        if "FROM application a" in sql or "FROM twist_application ta" in sql:
            return []
        raise AssertionError(f"SQL inesperado: {sql}")

    conn = parchear_conexion(monkeypatch, contratos, responder)
    assert _repo().estado_efectivo(["356111"]) == {}
    # Al no haber contratos, ni mora ni prórrogas se consultan.
    assert not any("amortization" in s or "prorroga" in s
                   for s, _ in conn.cursor_falso.ejecutadas)


def test_estado_efectivo_solo_phone_no_consulta_mora_ni_prorroga_twist(monkeypatch):
    def responder(sql, params):
        if sql.startswith("SELECT imei, id FROM knox_device"):
            return [("356111", 10)]
        if sql.startswith("SELECT imei, id FROM"):
            return []
        if "FROM application a" in sql:
            return [(10, 100)]
        if "FROM twist_application ta" in sql:
            return []
        if "FROM contract_amortization" in sql:
            return []
        if "FROM contracts_user_prorroga" in sql:
            return [(100, date(2026, 8, 25), datetime(2026, 8, 1))]
        raise AssertionError(f"SQL inesperado: {sql}")

    conn = parchear_conexion(monkeypatch, contratos, responder)
    assert _repo().estado_efectivo(["356111"]) == {
        "356111": [{"familia": "PHONE", "contract_id": 100,
                    "en_mora": False, "lock_date": date(2026, 8, 25)}],
    }
    ejecutadas = conn.cursor_falso.ejecutadas
    assert not any("FROM twist_contract_amortization" in s for s, _ in ejecutadas)
    assert not any("FROM twist_contracts_user_prorroga" in s for s, _ in ejecutadas)


def test_estado_efectivo_solo_twist_no_consulta_mora_ni_prorroga_phone(monkeypatch):
    def responder(sql, params):
        if sql.startswith("SELECT imei, id FROM trustonic_device"):
            return [("356222", 20)]
        if sql.startswith("SELECT imei, id FROM"):
            return []
        if "FROM application a" in sql:
            return []
        if "FROM twist_application ta" in sql:
            return [(20, 200)]
        if "FROM twist_contract_amortization" in sql:
            return [(200,)]
        if "FROM twist_contracts_user_prorroga" in sql:
            return []
        raise AssertionError(f"SQL inesperado: {sql}")

    conn = parchear_conexion(monkeypatch, contratos, responder)
    assert _repo().estado_efectivo(["356222"]) == {
        "356222": [{"familia": "TWIST_1.0", "contract_id": 200,
                    "en_mora": True, "lock_date": None}],
    }
    ejecutadas = conn.cursor_falso.ejecutadas
    assert not any("FROM contract_amortization" in s for s, _ in ejecutadas)
    assert not any("FROM contracts_user_prorroga" in s for s, _ in ejecutadas)


# ---------------------------------------------------------------------------
# estado_release_por_imei
# ---------------------------------------------------------------------------

def test_estado_release_gana_el_mas_reciente_aunque_este_cerrado(monkeypatch):
    """Regla de LIBERACIÓN: manda el contrato más reciente a secas, aunque esté
    cerrado y exista un PHONE activo más viejo (contraste con _contrato_vigente)."""
    def responder(sql, params):
        if sql.startswith("SELECT id FROM knox_device"):
            return [(10,)]
        if sql.startswith("SELECT id FROM"):
            return []
        if "JOIN contracts_status s" in sql:
            return [(2, "Activo", datetime(2024, 5, 1))]
        if "JOIN twist_contract_status s" in sql:
            return [(8, "Cerrado", datetime(2026, 2, 1))]
        raise AssertionError(f"SQL inesperado: {sql}")

    parchear_conexion(monkeypatch, contratos, responder)
    assert _repo().estado_release_por_imei("356111") == ("TWIST_1.0", 8, "Cerrado")


def test_estado_release_sin_candidatos_devuelve_vacio(monkeypatch):
    """Sin filas (o solo filas con created_at None) -> ('', None, '')."""
    def responder(sql, params):
        if sql.startswith("SELECT id FROM trustonic_device"):
            return [(20,)]
        if sql.startswith("SELECT id FROM"):
            return []
        if "JOIN contracts_status s" in sql:
            return [(2, "Activo", None)]   # created_at None: descartada
        if "JOIN twist_contract_status s" in sql:
            return []                      # fetchone None
        raise AssertionError(f"SQL inesperado: {sql}")

    parchear_conexion(monkeypatch, contratos, responder)
    assert _repo().estado_release_por_imei("356999") == ("", None, "")


def test_estado_release_paytrigger_no_consulta_twist(monkeypatch):
    def responder(sql, params):
        if sql.startswith("SELECT id FROM paytrigger_device"):
            return [(5,)]
        if sql.startswith("SELECT id FROM"):
            return []
        if "JOIN contracts_status s" in sql:
            assert "a.paytrigger_device_id=%s" in sql
            assert params == (5,)
            return [(6, "Prepagado", datetime(2026, 1, 1))]
        raise AssertionError(f"SQL inesperado: {sql}")

    conn = parchear_conexion(monkeypatch, contratos, responder)
    assert _repo().estado_release_por_imei("356111") == ("PHONE", 6, "Prepagado")
    assert not any("twist" in s for s, _ in conn.cursor_falso.ejecutadas)


# ---------------------------------------------------------------------------
# titular_phone_por_imei (vista + fallback)
# ---------------------------------------------------------------------------

_COLS_VISTA_PHONE = ["dni", "dni_type_id", "email", "contract_id", "imei"]


def test_titular_phone_fila_en_vista_devuelve_dict_completo(monkeypatch):
    def responder(sql, params):
        assert "view_contract_information" in sql
        assert params == ["356111"]
        return _COLS_VISTA_PHONE, [("1017234567", 1, " ana@correo.co ", 100, " 356111 ")]

    parchear_conexion(monkeypatch, contratos, responder)
    assert _repo().titular_phone_por_imei("356111") == {
        "dni": "1017234567",
        "doctype": 1,
        "email": "ana@correo.co",
        "contract_id": 100,
        "imei": "356111",
    }


def test_titular_phone_doctype_cero_es_none_y_email_none_vacio(monkeypatch):
    def responder(sql, params):
        return _COLS_VISTA_PHONE, [(" 123 ", 0, None, 55, None)]

    parchear_conexion(monkeypatch, contratos, responder)
    assert _repo().titular_phone_por_imei("356111") == {
        "dni": "123",
        "doctype": None,       # 0 -> None
        "email": "",           # None -> ''
        "contract_id": 55,
        "imei": "356111",      # imei None en la vista -> el del argumento
    }


def test_titular_phone_vista_vacia_cae_al_contrato_vigente(monkeypatch):
    def responder(sql, params):
        if "view_contract_information" in sql:
            return _COLS_VISTA_PHONE, []
        if sql.startswith("SELECT id FROM knox_device"):
            return [(10,)]
        if sql.startswith("SELECT id FROM"):
            return []
        if "FROM application a JOIN contract c" in sql:
            return [(100, 1, datetime(2026, 3, 1))]
        if "FROM twist_application ta JOIN twist_contract tc" in sql:
            return []
        if "FROM alocreditprod.contract c" in sql:      # _SQL_TITULAR_POR_APP[PHONE]
            assert params == (100,)
            return [("999444333", 2, " maria@correo.co ")]
        raise AssertionError(f"SQL inesperado: {sql}")

    parchear_conexion(monkeypatch, contratos, responder)
    assert _repo().titular_phone_por_imei("356111") == {
        "dni": "999444333",
        "doctype": 2,
        "email": "maria@correo.co",
        "contract_id": 100,
        "imei": "356111",
    }


def test_titular_phone_dni_vacio_en_vista_cae_al_contrato_vigente(monkeypatch):
    def responder(sql, params):
        if "view_contract_information" in sql:
            return _COLS_VISTA_PHONE, [("   ", 1, "x@y.co", 100, "356111")]
        if sql.startswith("SELECT id FROM"):
            return []   # el fallback tampoco encuentra contrato -> {}
        raise AssertionError(f"SQL inesperado: {sql}")

    parchear_conexion(monkeypatch, contratos, responder)
    assert _repo().titular_phone_por_imei("356111") == {}


# ---------------------------------------------------------------------------
# titular_twist_por_imei (vista + fallback)
# ---------------------------------------------------------------------------

_COLS_VISTA_TWIST = ["dni", "dni_type_id", "imei"]


def test_titular_twist_fila_con_dni_sin_email_ni_contract_id(monkeypatch):
    def responder(sql, params):
        assert "view_twist_contracts" in sql
        assert params == ["356222"]
        return _COLS_VISTA_TWIST, [(" 800123 ", 3, " 356222 ")]

    parchear_conexion(monkeypatch, contratos, responder)
    assert _repo().titular_twist_por_imei("356222") == {
        "dni": "800123",
        "doctype": 3,
        "email": "",           # la vista TWIST no trae email
        "contract_id": None,   # ni contrato
        "imei": "356222",
    }


def test_titular_twist_sin_dni_cae_al_contrato_vigente(monkeypatch):
    def responder(sql, params):
        if "view_twist_contracts" in sql:
            return _COLS_VISTA_TWIST, []
        if sql.startswith("SELECT id FROM trustonic_device"):
            return [(20,)]
        if sql.startswith("SELECT id FROM"):
            return []
        if "FROM application a JOIN contract c" in sql:
            return []
        if "FROM twist_application ta JOIN twist_contract tc" in sql:
            return [(200, 1, datetime(2026, 4, 1))]
        if "FROM alocreditprod.twist_contract tc" in sql:   # _SQL_TITULAR_POR_APP[TWIST]
            assert params == (200,)
            return [("888777666", 1, None)]
        raise AssertionError(f"SQL inesperado: {sql}")

    parchear_conexion(monkeypatch, contratos, responder)
    assert _repo().titular_twist_por_imei("356222") == {
        "dni": "888777666",
        "doctype": 1,
        "email": "",
        "contract_id": 200,
        "imei": "356222",
    }


# ---------------------------------------------------------------------------
# titular_por_contrato_vigente (directo)
# ---------------------------------------------------------------------------

def test_titular_por_contrato_sin_familia_devuelve_dict_vacio(monkeypatch):
    conn = parchear_conexion(monkeypatch, contratos, lambda sql, params: [])
    assert _repo().titular_por_contrato_vigente("356999") == {}
    # Sin familia no hay SQL de titular: solo se consultaron las tablas de candado.
    assert all(s.startswith("SELECT id FROM") for s, _ in conn.cursor_falso.ejecutadas)


def _responder_contrato_phone_con_titular(fila_titular):
    def responder(sql, params):
        if sql.startswith("SELECT id FROM knox_device"):
            return [(10,)]
        if sql.startswith("SELECT id FROM"):
            return []
        if "FROM application a JOIN contract c" in sql:
            return [(100, 1, datetime(2026, 5, 1))]
        if "FROM twist_application ta JOIN twist_contract tc" in sql:
            return []
        if "FROM alocreditprod.contract c" in sql:
            assert params == (100,)
            return fila_titular
        raise AssertionError(f"SQL inesperado: {sql}")
    return responder


def test_titular_por_contrato_fila_none_devuelve_dict_vacio(monkeypatch):
    parchear_conexion(monkeypatch, contratos, _responder_contrato_phone_con_titular([]))
    assert _repo().titular_por_contrato_vigente("356111") == {}


def test_titular_por_contrato_dni_vacio_devuelve_dict_vacio(monkeypatch):
    parchear_conexion(monkeypatch, contratos,
                      _responder_contrato_phone_con_titular([("  ", 1, "x@y.co")]))
    assert _repo().titular_por_contrato_vigente("356111") == {}


def test_titular_por_contrato_feliz_devuelve_contrato_e_imei(monkeypatch):
    parchear_conexion(monkeypatch, contratos,
                      _responder_contrato_phone_con_titular([(" 52123456 ", 2, " m@x.co ")]))
    assert _repo().titular_por_contrato_vigente("356333") == {
        "dni": "52123456",
        "doctype": 2,
        "email": "m@x.co",
        "contract_id": 100,
        "imei": "356333",
    }
