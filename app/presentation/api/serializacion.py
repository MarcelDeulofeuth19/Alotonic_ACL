"""Serialización con fidelidad de tipos entre el ACL y sus consumidores.

El driver MySQL devuelve datetime/date/Decimal y los llamadores de AloTonic
dependen de esos tipos EXACTOS (comparan fechas, formatean dinero). JSON no los
distingue, así que viajan etiquetados::

    datetime -> {"$tipo": "datetime", "$v": "2026-08-16T20:15:00"}
    date     -> {"$tipo": "date",     "$v": "2026-08-16"}
    Decimal  -> {"$tipo": "decimal",  "$v": "123.45"}

El cliente aplica la inversa y recibe los mismos objetos que le daba pymysql.
Los datetimes del legacy son naive (hora local Colombia): se serializan SIN zona.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def a_json(valor: Any) -> Any:
    """Convierte recursivamente un valor con tipos del driver a JSON etiquetado."""
    # datetime es subclase de date: se chequea primero.
    if isinstance(valor, datetime):
        return {"$tipo": "datetime", "$v": valor.isoformat()}
    if isinstance(valor, date):
        return {"$tipo": "date", "$v": valor.isoformat()}
    if isinstance(valor, Decimal):
        return {"$tipo": "decimal", "$v": str(valor)}
    if isinstance(valor, dict):
        return {clave: a_json(v) for clave, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [a_json(v) for v in valor]
    return valor
