"""Tests de dominio puro (catálogo, tiempo) y de la serialización etiquetada."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.domain.catalogo import placeholders, tipo_prorroga_crm
from app.domain.tiempo import ZONA_LEGACY, a_hora_local_legacy, ahora_local_legacy
from app.presentation.api.serializacion import a_json

# ---------------------------------------------------------------------------
# app/domain/catalogo.py
# ---------------------------------------------------------------------------


def test_tipo_prorroga_crm_resuelve_los_ids_conocidos():
    assert tipo_prorroga_crm(0) == "otra"
    assert tipo_prorroga_crm(1) == "salvavidas"
    assert tipo_prorroga_crm(2) == "canoa"


def test_tipo_prorroga_crm_acepta_el_id_como_string_numerico():
    # El legacy a veces entrega el id como texto: int(tipo) lo normaliza.
    assert tipo_prorroga_crm("2") == "canoa"


def test_tipo_prorroga_crm_id_desconocido_devuelve_tipo_n():
    assert tipo_prorroga_crm(7) == "tipo_7"
    assert tipo_prorroga_crm("99") == "tipo_99"


def test_tipo_prorroga_crm_none_devuelve_desconocido():
    # int(None) -> TypeError, capturado.
    assert tipo_prorroga_crm(None) == "desconocido"


def test_tipo_prorroga_crm_texto_no_numerico_devuelve_desconocido():
    # int('x') -> ValueError, capturado.
    assert tipo_prorroga_crm("x") == "desconocido"


def test_placeholders_genera_un_marcador_por_valor():
    assert placeholders([10, 20, 30]) == "%s,%s,%s"
    assert placeholders(("solo",)) == "%s"


def test_placeholders_lista_vacia_devuelve_cadena_vacia():
    assert placeholders([]) == ""


# ---------------------------------------------------------------------------
# app/domain/tiempo.py
# ---------------------------------------------------------------------------


def test_a_hora_local_legacy_none_devuelve_none():
    assert a_hora_local_legacy(None) is None


def test_a_hora_local_legacy_aware_utc_se_traduce_a_bogota_naive():
    # Colombia es UTC-5 fijo (sin DST): 12:30 UTC son las 07:30 en Bogotá.
    aware_utc = datetime(2026, 8, 16, 12, 30, 45, tzinfo=timezone.utc)
    resultado = a_hora_local_legacy(aware_utc)
    assert resultado == datetime(2026, 8, 16, 7, 30, 45)
    assert resultado.tzinfo is None
    # El corrimiento es exactamente -5 h respecto del reloj UTC de entrada.
    assert aware_utc.replace(tzinfo=None) - resultado == timedelta(hours=5)


def test_a_hora_local_legacy_aware_no_utc_tambien_aterriza_en_bogota():
    # Una zona +02:00: 18:00+02 = 16:00 UTC = 11:00 Bogotá.
    aware = datetime(2026, 8, 16, 18, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    assert a_hora_local_legacy(aware) == datetime(2026, 8, 16, 11, 0, 0)


def test_a_hora_local_legacy_naive_se_devuelve_intacto():
    naive = datetime(2026, 8, 16, 23, 59, 59)
    resultado = a_hora_local_legacy(naive)
    assert resultado == naive
    assert resultado.tzinfo is None


def test_ahora_local_legacy_es_naive_y_coincide_con_el_reloj_de_bogota():
    antes = datetime.now(tz=ZoneInfo("America/Bogota")).replace(tzinfo=None)
    resultado = ahora_local_legacy()
    despues = datetime.now(tz=ZoneInfo("America/Bogota")).replace(tzinfo=None)
    assert resultado.tzinfo is None
    # Coherente con el reloj real de America/Bogota (acotado entre dos lecturas).
    assert antes <= resultado <= despues
    assert despues - antes < timedelta(seconds=5)


def test_zona_legacy_es_america_bogota():
    assert str(ZONA_LEGACY) == "America/Bogota"


# ---------------------------------------------------------------------------
# app/presentation/api/serializacion.py
# ---------------------------------------------------------------------------


def test_a_json_datetime_naive_se_etiqueta_como_datetime_no_como_date():
    # datetime ES subclase de date: el orden de isinstance decide la etiqueta.
    dt = datetime(2026, 8, 16, 20, 15, 0)
    resultado = a_json(dt)
    assert resultado == {"$tipo": "datetime", "$v": "2026-08-16T20:15:00"}
    assert resultado["$tipo"] != "date"


def test_a_json_datetime_conserva_los_microsegundos():
    dt = datetime(2026, 8, 16, 20, 15, 0, 123456)
    assert a_json(dt) == {"$tipo": "datetime", "$v": "2026-08-16T20:15:00.123456"}


def test_a_json_date_se_etiqueta_como_date():
    assert a_json(date(2026, 8, 16)) == {"$tipo": "date", "$v": "2026-08-16"}


def test_a_json_decimal_conserva_la_representacion_exacta():
    # str(Decimal('10.10')) mantiene el cero final: '10.10', no '10.1'.
    assert a_json(Decimal("10.10")) == {"$tipo": "decimal", "$v": "10.10"}
    assert a_json(Decimal("123.45")) == {"$tipo": "decimal", "$v": "123.45"}
    assert a_json(Decimal("-0.00")) == {"$tipo": "decimal", "$v": "-0.00"}


def test_a_json_dict_y_list_anidados_se_recorren_recursivamente():
    entrada = {
        "cuota": Decimal("99.90"),
        "vence": date(2026, 8, 25),
        "pagos": [
            {"cuando": datetime(2026, 8, 1, 8, 0, 0), "monto": Decimal("50.00")},
            None,
        ],
    }
    assert a_json(entrada) == {
        "cuota": {"$tipo": "decimal", "$v": "99.90"},
        "vence": {"$tipo": "date", "$v": "2026-08-25"},
        "pagos": [
            {
                "cuando": {"$tipo": "datetime", "$v": "2026-08-01T08:00:00"},
                "monto": {"$tipo": "decimal", "$v": "50.00"},
            },
            None,
        ],
    }


def test_a_json_tupla_se_convierte_en_lista_json():
    resultado = a_json((Decimal("1.5"), "texto", 3))
    assert resultado == [{"$tipo": "decimal", "$v": "1.5"}, "texto", 3]
    assert isinstance(resultado, list)


def test_a_json_escalares_json_nativos_pasan_intactos():
    assert a_json("hola") == "hola"
    assert a_json(42) == 42
    assert a_json(3.14) == 3.14
    assert a_json(True) is True
    assert a_json(False) is False
    assert a_json(None) is None
