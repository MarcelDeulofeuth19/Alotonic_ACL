"""Excepciones del dominio. La capa de presentación las traduce a HTTP;
la infraestructura traduce los errores del driver hacia estas — así ni el
dominio ni los consumidores conocen pymysql.
"""


class ErrorAcl(Exception):
    """Base de todos los errores del servicio."""


class BaseLegacyNoDisponible(ErrorAcl):
    """No se pudo conectar/consultar la base legacy (timeout, red, credenciales)."""


class PeticionInvalida(ErrorAcl):
    """La petición viola una regla del contrato (p.ej. demasiados IMEIs)."""
