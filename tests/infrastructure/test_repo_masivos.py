"""Tests de los repos MySQL masivos: pertenencia, población, prórrogas,
referencias e informes. Todo contra el arnés de dobles de tests/fakes.py:
se verifica el SQL emitido, los params EXACTOS y el post-procesado.
"""
from datetime import datetime

from app.infrastructure.mysql import informes as informes_mod
from app.infrastructure.mysql import pertenencia as pertenencia_mod
from app.infrastructure.mysql import poblacion as poblacion_mod
from app.infrastructure.mysql import prorrogas as prorrogas_mod
from app.infrastructure.mysql import referencias as referencias_mod
from app.infrastructure.mysql.informes import RepositorioInformesMysql
from app.infrastructure.mysql.pertenencia import RepositorioPertenenciaMysql
from app.infrastructure.mysql.poblacion import RepositorioPoblacionMysql
from app.infrastructure.mysql.prorrogas import RepositorioProrrogasMysql
from app.infrastructure.mysql.referencias import RepositorioReferenciasMysql
from tests.fakes import parchear_conexion, settings_prueba

ESTADOS = [4, 5, 6, 7, 8, 9]  # ESTADOS_NO_VIGENTES del catálogo, en orden
AHORA = datetime(2026, 8, 16, 12, 0, 0)


# ---------------------------------------------------------------- pertenencia

def test_imeis_en_tabla_trocea_en_chunks_de_1000_y_une_resultados(monkeypatch):
    imeis = [f"35{i:013d}" for i in range(1001)]

    def responder(sql, params):
        return [(params[0],)]  # cada query "encuentra" su primer imei

    conn = parchear_conexion(monkeypatch, pertenencia_mod, responder)
    repo = RepositorioPertenenciaMysql(settings_prueba())

    encontrados = repo.imeis_en_tabla("trustonic", imeis)

    assert len(conn.cursor_falso.ejecutadas) == 2
    sql1, params1 = conn.cursor_falso.ejecutadas[0]
    sql2, params2 = conn.cursor_falso.ejecutadas[1]
    assert params1 == imeis[:1000]
    assert sql1.count("%s") == 1000
    assert params2 == imeis[1000:]
    assert sql2.count("%s") == 1
    # Schema hardcodeado, independiente de MYSQL_DB.
    assert "alocreditprod.trustonic_device" in sql1
    assert "alocreditprod.trustonic_device" in sql2
    # Unión de resultados de ambos chunks.
    assert encontrados == {imeis[0], imeis[1000]}


def test_imeis_en_tabla_alias_paytrigger_usa_tabla_paytrigger_device(monkeypatch):
    conn = parchear_conexion(monkeypatch, pertenencia_mod,
                             lambda sql, params: [("111111111111111",)])
    repo = RepositorioPertenenciaMysql(settings_prueba())

    encontrados = repo.imeis_en_tabla("paytrigger", ["111111111111111", "222222222222222"])

    sql, params = conn.cursor_falso.ejecutadas[0]
    assert sql == ("SELECT DISTINCT imei FROM alocreditprod.paytrigger_device "
                   "WHERE imei IN (%s,%s)")
    assert params == ["111111111111111", "222222222222222"]
    assert encontrados == {"111111111111111"}


def test_conteo_tabla_devuelve_int(monkeypatch):
    conn = parchear_conexion(monkeypatch, pertenencia_mod,
                             lambda sql, params: [("41234",)])
    repo = RepositorioPertenenciaMysql(settings_prueba())

    total = repo.conteo_tabla("knox")

    sql, params = conn.cursor_falso.ejecutadas[0]
    assert sql == "SELECT COUNT(*) FROM alocreditprod.knox_device"
    assert params is None
    assert total == 41234
    assert isinstance(total, int)


# ------------------------------------------------------------------ poblacion

def test_imeis_candado_globetek_solo_phone_sin_union(monkeypatch):
    conn = parchear_conexion(monkeypatch, poblacion_mod,
                             lambda sql, params: [("111111111111111",), ("222222222222222",)])
    repo = RepositorioPoblacionMysql(settings_prueba())

    imeis = repo.imeis_candado("globetek", limit=None, desde_imei=None)

    sql, params = conn.cursor_falso.ejecutadas[0]
    assert "UNION" not in sql
    assert "twist" not in sql
    assert sql.startswith("SELECT DISTINCT imei FROM (")
    assert "FROM paytrigger_device d" in sql
    assert "JOIN application a ON a.paytrigger_device_id=d.id" in sql
    assert sql.endswith(") x ORDER BY imei")
    assert params == ESTADOS
    assert sql.count("%s") == 6
    # Retorno = lista PLANA de imeis.
    assert imeis == ["111111111111111", "222222222222222"]


def test_imeis_candado_knox_une_phone_y_twist(monkeypatch):
    conn = parchear_conexion(monkeypatch, poblacion_mod, lambda sql, params: [])
    repo = RepositorioPoblacionMysql(settings_prueba())

    assert repo.imeis_candado("knox", limit=None, desde_imei=None) == []

    sql, params = conn.cursor_falso.ejecutadas[0]
    assert " UNION " in sql
    assert "FROM knox_device d" in sql
    assert "JOIN twist_application ta ON ta.knox_device_id=d.id" in sql
    assert "JOIN twist_contract tc ON tc.twist_application_id=ta.id" in sql
    assert params == ESTADOS + ESTADOS
    assert sql.endswith(") x ORDER BY imei")


def test_imeis_candado_desde_imei_agrega_where_y_param_al_final(monkeypatch):
    conn = parchear_conexion(monkeypatch, poblacion_mod, lambda sql, params: [])
    repo = RepositorioPoblacionMysql(settings_prueba())

    repo.imeis_candado("globetek", limit=None, desde_imei=350000000000000)

    sql, params = conn.cursor_falso.ejecutadas[0]
    # El WHERE va sobre la query externa y ANTES del ORDER BY.
    assert sql.endswith(") x WHERE imei > %s ORDER BY imei")
    # El cursor se agrega AL FINAL de los params, casteado a str.
    assert params == ESTADOS + ["350000000000000"]


def test_imeis_candado_limit_se_interpola_como_entero(monkeypatch):
    conn = parchear_conexion(monkeypatch, poblacion_mod, lambda sql, params: [])
    repo = RepositorioPoblacionMysql(settings_prueba())

    repo.imeis_candado("globetek", limit="5", desde_imei=None)

    sql, params = conn.cursor_falso.ejecutadas[0]
    assert sql.endswith(" ORDER BY imei LIMIT 5")
    assert params == ESTADOS  # el LIMIT no viaja como placeholder


def test_imei_modelo_candado_sin_vigencia_query_simple(monkeypatch):
    conn = parchear_conexion(monkeypatch, poblacion_mod,
                             lambda sql, params: [["111111111111111", "SM-A165M"],
                                                  ["222222222222222", "KM8"]])
    repo = RepositorioPoblacionMysql(settings_prueba())

    pares = repo.imei_modelo_candado("knox", solo_vigentes=False)

    sql, params = conn.cursor_falso.ejecutadas[0]
    assert sql == ("SELECT imei, model FROM knox_device "
                   "WHERE imei IS NOT NULL AND imei<>'' AND model IS NOT NULL AND model<>''")
    assert params is None
    assert "JOIN" not in sql
    assert pares == [("111111111111111", "SM-A165M"), ("222222222222222", "KM8")]
    assert all(isinstance(p, tuple) for p in pares)


def test_imei_modelo_candado_vigentes_globetek_sin_union(monkeypatch):
    conn = parchear_conexion(monkeypatch, poblacion_mod,
                             lambda sql, params: [("111111111111111", "KM8")])
    repo = RepositorioPoblacionMysql(settings_prueba())

    pares = repo.imei_modelo_candado("globetek", solo_vigentes=True)

    sql, params = conn.cursor_falso.ejecutadas[0]
    assert sql.startswith("SELECT DISTINCT imei, model FROM (")
    assert "UNION" not in sql
    assert "twist" not in sql
    assert "FROM paytrigger_device d" in sql
    assert params == ESTADOS
    assert pares == [("111111111111111", "KM8")]


def test_imei_modelo_candado_vigentes_trustonic_con_union(monkeypatch):
    conn = parchear_conexion(monkeypatch, poblacion_mod,
                             lambda sql, params: [("333333333333333", "Moto G24")])
    repo = RepositorioPoblacionMysql(settings_prueba())

    pares = repo.imei_modelo_candado("trustonic", solo_vigentes=True)

    sql, params = conn.cursor_falso.ejecutadas[0]
    assert " UNION " in sql
    assert "FROM trustonic_device d" in sql
    assert "JOIN twist_application ta ON ta.trustonic_device_id=d.id" in sql
    assert params == ESTADOS + ESTADOS
    assert pares == [("333333333333333", "Moto G24")]


# ------------------------------------------------------------------ prorrogas

def test_cortas_vencidas_globetek_salta_twist_y_manda_params_exactos(monkeypatch):
    fila = ("999888777666555", 42, 2,
            datetime(2026, 8, 15, 8, 30, 0), datetime(2026, 8, 16, 9, 30, 0), 25, 1)
    conn = parchear_conexion(monkeypatch, prorrogas_mod, lambda sql, params: [fila])
    monkeypatch.setattr(prorrogas_mod, "ahora_local_legacy", lambda: AHORA)
    repo = RepositorioProrrogasMysql(settings_prueba())

    salida = repo.cortas_vencidas("globetek", horas_ventana=6, max_horas_rango=48, limite=500)

    # globetek (paytrigger_device) NO existe en TWIST 1.0: una sola query.
    assert len(conn.cursor_falso.ejecutadas) == 1
    sql, params = conn.cursor_falso.ejecutadas[0]
    assert "twist" not in sql
    assert "FROM contracts_user_prorroga p" in sql
    assert "JOIN paytrigger_device d ON d.id = ap.paytrigger_device_id" in sql
    # Orden EXACTO: [atrasado_PHONE, ahora, horas, ahora, max_rango] + estados + [ahora, limite]
    assert params == [4, AHORA, 6, AHORA, 48] + ESTADOS + [AHORA, 500]
    assert salida == [{
        "imei": "999888777666555",
        "familia": "PHONE",
        "contract_id": 42,
        "tipo": "canoa",
        "otorgada_en": "2026-08-15 08:30:00",
        "vencio_en": "2026-08-16 09:30:00",
        "horas": 25,
        "en_mora": True,
    }]


def test_cortas_vencidas_knox_recorre_ambas_familias_y_dedup_por_imei(monkeypatch):
    filas_phone = [
        ("111111111111111", 10, 1,
         datetime(2026, 8, 15, 10, 0, 0), datetime(2026, 8, 15, 16, 0, 0), 6, 1),
        # Mismo imei con otra prórroga: se descarta (gana la PRIMERA aparición,
        # que ya viene ORDER BY lock_date DESC del SQL).
        ("111111111111111", 11, 2,
         datetime(2026, 8, 14, 10, 0, 0), datetime(2026, 8, 14, 13, 0, 0), 3, 0),
        ("222222222222222", 12, 0, None, None, None, 0),
    ]
    filas_twist = [
        # Duplicado ENTRE familias: también se descarta.
        ("111111111111111", 99, 2,
         datetime(2026, 8, 15, 11, 0, 0), datetime(2026, 8, 15, 12, 0, 0), 1, 1),
        ("333333333333333", 13, 7,
         datetime(2026, 8, 15, 0, 0, 0), datetime(2026, 8, 15, 12, 0, 0), 12, 1),
    ]

    def responder(sql, params):
        return filas_twist if "twist" in sql else filas_phone

    conn = parchear_conexion(monkeypatch, prorrogas_mod, responder)
    monkeypatch.setattr(prorrogas_mod, "ahora_local_legacy", lambda: AHORA)
    repo = RepositorioProrrogasMysql(settings_prueba())

    salida = repo.cortas_vencidas("knox", horas_ventana=6, max_horas_rango=48, limite=200)

    assert len(conn.cursor_falso.ejecutadas) == 2
    sql_phone, params_phone = conn.cursor_falso.ejecutadas[0]
    sql_twist, params_twist = conn.cursor_falso.ejecutadas[1]
    assert params_phone == [4, AHORA, 6, AHORA, 48] + ESTADOS + [AHORA, 200]
    # TWIST 1.0: atrasado=3 (¡catálogo distinto a PHONE!) y tablas twist_*.
    assert params_twist == [3, AHORA, 6, AHORA, 48] + ESTADOS + [AHORA, 200]
    assert "FROM twist_contracts_user_prorroga p" in sql_twist
    assert "JOIN twist_contract c" in sql_twist
    assert "c.twist_contract_status_id NOT IN" in sql_twist
    assert "FROM twist_contract_amortization am" in sql_twist
    assert "am.twist_contract_payment_status_id = %s" in sql_twist

    assert salida == [
        {"imei": "111111111111111", "familia": "PHONE", "contract_id": 10,
         "tipo": "salvavidas", "otorgada_en": "2026-08-15 10:00:00",
         "vencio_en": "2026-08-15 16:00:00", "horas": 6, "en_mora": True},
        {"imei": "222222222222222", "familia": "PHONE", "contract_id": 12,
         "tipo": "otra", "otorgada_en": None, "vencio_en": None,
         "horas": None, "en_mora": False},
        {"imei": "333333333333333", "familia": "TWIST_1.0", "contract_id": 13,
         "tipo": "tipo_7", "otorgada_en": "2026-08-15 00:00:00",
         "vencio_en": "2026-08-15 12:00:00", "horas": 12, "en_mora": True},
    ]


def test_imeis_con_prorroga_nueva_globetek_solo_query_phone(monkeypatch):
    desde = datetime(2026, 8, 10, 0, 0, 0)
    conn = parchear_conexion(monkeypatch, prorrogas_mod,
                             lambda sql, params: [("222222222222222",), ("111111111111111",)])
    repo = RepositorioProrrogasMysql(settings_prueba())

    imeis = repo.imeis_con_prorroga_nueva("globetek", desde)

    assert len(conn.cursor_falso.ejecutadas) == 1
    sql, params = conn.cursor_falso.ejecutadas[0]
    assert "FROM contracts_user_prorroga p" in sql
    assert "JOIN paytrigger_device d ON d.id=a.paytrigger_device_id" in sql
    assert params == [desde] + ESTADOS
    assert imeis == ["111111111111111", "222222222222222"]  # sorted


def test_imeis_con_prorroga_nueva_knox_une_familias_sin_duplicados(monkeypatch):
    desde = datetime(2026, 8, 10, 0, 0, 0)

    def responder(sql, params):
        if "twist_contracts_user_prorroga" in sql:
            return [("111111111111111",), ("333333333333333",)]
        return [("222222222222222",), ("111111111111111",)]

    conn = parchear_conexion(monkeypatch, prorrogas_mod, responder)
    repo = RepositorioProrrogasMysql(settings_prueba())

    imeis = repo.imeis_con_prorroga_nueva("knox", desde)

    assert len(conn.cursor_falso.ejecutadas) == 2
    sql_twist, params_twist = conn.cursor_falso.ejecutadas[1]
    assert "FROM twist_contracts_user_prorroga p" in sql_twist
    assert "JOIN knox_device d ON d.id=ta.knox_device_id" in sql_twist
    assert params_twist == [desde] + ESTADOS
    # sorted(set()): el duplicado entre familias entra UNA vez y ordenado.
    assert imeis == ["111111111111111", "222222222222222", "333333333333333"]


# ---------------------------------------------------------------- referencias

def test_referencias_por_tac_trocea_en_lotes_de_50(monkeypatch):
    tacs = [f"350000{i:02d}" for i in range(61)]

    def responder(sql, params):
        if len(params) == 50:
            return [("35000000", "RefA", "MarcaA", "LargaA", 5)]
        return [("35000050", "RefB", "MarcaB", "LargaB", 3)]

    conn = parchear_conexion(monkeypatch, referencias_mod, responder)
    repo = RepositorioReferenciasMysql(settings_prueba())

    out = repo.referencias_por_tac(tacs, "globetek")

    # globetek solo consulta application: 2 lotes x 1 familia = 2 queries.
    assert len(conn.cursor_falso.ejecutadas) == 2
    sql1, params1 = conn.cursor_falso.ejecutadas[0]
    sql2, params2 = conn.cursor_falso.ejecutadas[1]
    assert sql1.count("dv.imei LIKE %s") == 50
    assert params1 == [f"{t}%" for t in tacs[:50]]
    assert sql2.count("dv.imei LIKE %s") == 11
    assert params2 == [f"{t}%" for t in tacs[50:]]
    assert "twist_application" not in sql1
    assert "twist_application" not in sql2
    assert "FROM paytrigger_device dv" in sql1
    assert "JOIN application ap        ON ap.paytrigger_device_id = dv.id" in sql1
    assert out == {
        "35000000": {"referencia": "RefA", "marca": "MarcaA", "referencia_larga": "LargaA"},
        "35000050": {"referencia": "RefB", "marca": "MarcaB", "referencia_larga": "LargaB"},
    }


def test_referencias_por_tac_knox_gana_el_n_mas_alto_entre_familias(monkeypatch):
    tacs = ["35123456", "35777777", "35999999"]

    def responder(sql, params):
        if "twist_application" in sql:
            return [
                ("35123456", " Galaxy A26 ", "Samsung ", " SM-A266M", 12),  # gana a PHONE (10)
                ("35777777", "Redmi 13", "Xiaomi", "R13", 2),               # pierde con PHONE (8)
                ("35999999", "Moto G24", "Motorola", None, 3),              # solo TWIST
            ]
        return [
            ("35123456", "Galaxy A16", "Samsung", "SM-A165M", 10),
            ("35123456", "Galaxy A15", "Samsung", "SM-A155M", 4),  # n menor: no reemplaza
            ("35777777", "Poco C65", "Xiaomi", "C65", 8),
        ]

    conn = parchear_conexion(monkeypatch, referencias_mod, responder)
    repo = RepositorioReferenciasMysql(settings_prueba())

    out = repo.referencias_por_tac(tacs, "knox")

    # 1 lote x 2 familias (application y twist_application).
    assert len(conn.cursor_falso.ejecutadas) == 2
    sql_app, params_app = conn.cursor_falso.ejecutadas[0]
    sql_twist, params_twist = conn.cursor_falso.ejecutadas[1]
    assert "JOIN application ap" in sql_app and "twist_application" not in sql_app
    assert "JOIN twist_application ap" in sql_twist
    assert "FROM knox_device dv" in sql_app
    assert "ON ap.knox_device_id = dv.id" in sql_app
    assert params_app == ["35123456%", "35777777%", "35999999%"]
    assert params_twist == params_app

    assert out == {
        # Con strip de referencia/marca/larga y SIN la clave interna _n.
        "35123456": {"referencia": "Galaxy A26", "marca": "Samsung",
                     "referencia_larga": "SM-A266M"},
        "35777777": {"referencia": "Poco C65", "marca": "Xiaomi",
                     "referencia_larga": "C65"},
        "35999999": {"referencia": "Moto G24", "marca": "Motorola",
                     "referencia_larga": ""},
    }
    assert all("_n" not in v for v in out.values())


# ------------------------------------------------------------------- informes

def test_contratos_por_lock_system_devuelve_dicts_tal_cual(monkeypatch):
    filas = [
        {"imei": "111111111111111", "contract_number": "C-1", "customer_dni": "123",
         "full_name": "Ana Pérez", "customer_phone": "3001112233",
         "status_name": "Activo", "product": "PHONE"},
        {"imei": "222222222222222", "contract_number": "C-2", "customer_dni": "456",
         "full_name": "Luis Gómez", "customer_phone": "3009998877",
         "status_name": "Atrasado", "product": "TWIST"},
    ]
    conn = parchear_conexion(monkeypatch, informes_mod, lambda sql, params: filas)
    repo = RepositorioInformesMysql(settings_prueba())

    resultado = repo.contratos_por_lock_system("KNOX GUARD")

    set_names, _ = conn.cursor_falso.ejecutadas[0]
    assert set_names == "SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci"
    sql, params = conn.cursor_falso.ejecutadas[1]
    assert "FROM view_general_contracts" in sql
    assert "lock_system COLLATE utf8mb4_unicode_ci = %s" in sql
    assert "status_name COLLATE utf8mb4_unicode_ci IN %s" in sql
    assert params == ("KNOX GUARD", ("Activo", "Atrasado", "Default"))
    assert resultado == filas


def test_catalogo_device_location_devuelve_tuplas_y_filtra_en_sql(monkeypatch):
    conn = parchear_conexion(monkeypatch, informes_mod,
                             lambda sql, params: [["Bodega Central", "KM8n,KM8"],
                                                  ["Tienda Norte", None]])
    repo = RepositorioInformesMysql(settings_prueba())

    catalogo = repo.catalogo_device_location()

    sql, params = conn.cursor_falso.ejecutadas[0]
    assert sql == ("SELECT description, tags_model_device FROM view_device "
                   "WHERE description IS NOT NULL AND description <> ''")
    assert params is None
    assert catalogo == [("Bodega Central", "KM8n,KM8"), ("Tienda Norte", None)]
    assert all(isinstance(fila, tuple) for fila in catalogo)
