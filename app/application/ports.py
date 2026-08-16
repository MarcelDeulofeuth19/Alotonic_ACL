"""Puertos (contratos) de la capa de aplicación — arquitectura hexagonal.

Los casos de uso dependen de estas ABSTRACCIONES; los adaptadores MySQL de
``infrastructure`` las implementan. La dependencia apunta hacia adentro.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol


class PuertoCandados(Protocol):
    """Candado ALOTONIC (GlobeTek, tabla ``paytrigger_device``) + prórrogas del CRM."""

    def consultar_candados(self, imeis: list[str] | None) -> list[dict[str, Any]]:
        ...

    def prorrogas_credito_por_imei(self, imei: str, limite: int) -> dict[str, Any]:
        ...


class PuertoContratos(Protocol):
    """Contratos PHONE / TWIST 1.0: producto, estado de pago, titular, release."""

    def estado_pago_por_imei(self, imeis: list[str]) -> dict[str, str]:
        ...

    def productos_por_imei(self, imeis: list[str]) -> dict[str, str]:
        ...

    def estado_efectivo(self, imeis: list[str]) -> dict[str, list[dict[str, Any]]]:
        ...

    def estado_release_por_imei(self, imei: str) -> tuple[str, int | None, str]:
        ...

    def titular_phone_por_imei(self, imei: str) -> dict[str, Any]:
        ...

    def titular_twist_por_imei(self, imei: str) -> dict[str, Any]:
        ...


class PuertoPertenencia(Protocol):
    """Membresía de IMEIs en las tablas de candado del legacy."""

    def imeis_en_tabla(self, tabla: str, imeis: list[str]) -> set[str]:
        ...

    def conteo_tabla(self, tabla: str) -> int:
        ...


class PuertoProrrogas(Protocol):
    """Prórrogas del CRM: vencidas cortas y delta por timestamp."""

    def cortas_vencidas(self, sistema: str, horas_ventana: int,
                        max_horas_rango: int, limite: int) -> list[dict[str, Any]]:
        ...

    def imeis_con_prorroga_nueva(self, sistema: str, desde: datetime) -> list[str]:
        ...


class PuertoPoblacion(Protocol):
    """Población de equipos por candado (fuente de verdad del legacy)."""

    def imeis_candado(self, sistema: str, limit: int | None,
                      desde_imei: str | None) -> list[str]:
        ...

    def imei_modelo_candado(self, sistema: str, solo_vigentes: bool) -> list[tuple[str, str]]:
        ...


class PuertoReferencias(Protocol):
    """Referencia comercial por TAC desde el catálogo del CRM."""

    def referencias_por_tac(self, tacs: list[str], sistema: str) -> dict[str, dict[str, str]]:
        ...


class PuertoInformes(Protocol):
    """Vistas de informes del legacy (view_general_contracts, view_device)."""

    def contratos_por_lock_system(self, lock_system: str) -> list[dict[str, Any]]:
        ...

    def catalogo_device_location(self) -> list[tuple[str, str]]:
        ...
