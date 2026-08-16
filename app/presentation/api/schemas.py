"""Esquemas de las peticiones (pydantic). Las respuestas son dicts serializados
con ``serializacion.a_json`` para preservar tipos del driver."""
from pydantic import BaseModel


class PeticionImeis(BaseModel):
    # None o lista vacía = sin filtro (donde el contrato original lo permite).
    imeis: list[str] | None = None


class PeticionPertenencia(BaseModel):
    tablas: list[str]
    imeis: list[str]


class PeticionReferencias(BaseModel):
    sistema: str
    tacs: list[str]
