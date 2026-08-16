"""Escala de tiempo del legacy: hora LOCAL de Colombia, naive.

alocreditprod guarda sus datetimes en hora local de Colombia SIN zona. Este módulo
centraliza esa rareza para que ningún consumidor tenga que conocerla: los cursores
llegan a la API en ISO-8601 (con o sin zona) y aquí se traducen a la escala en la
que el legacy compara. Bug histórico que esto previene: un cursor UTC corría 5 h
hacia el futuro y un delta de prórrogas pasó 1.412 ejecuciones devolviendo 0.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

ZONA_LEGACY = ZoneInfo("America/Bogota")


def a_hora_local_legacy(dt: datetime | None) -> datetime | None:
    """Convierte un datetime (aware o naive) a la hora que el legacy tiene GUARDADA.

    Aware -> se convierte a America/Bogota y se le quita la zona.
    Naive -> se asume ya en hora local del legacy y se devuelve tal cual.
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(ZONA_LEGACY).replace(tzinfo=None)
    return dt


def ahora_local_legacy() -> datetime:
    """'Ahora' en la misma escala que las fechas guardadas en el legacy (local, naive)."""
    return datetime.now(tz=ZONA_LEGACY).replace(tzinfo=None)
