"""Casos de uso: normalizan la entrada EXACTAMENTE como lo hacía el cliente
embebido en AloTonic (misma sanitización, mismos clamps, mismos retornos
degenerados sin tocar la base) y delegan en el puerto correspondiente.

Mantener esa paridad es deliberado: el consumidor no debe notar diferencia
alguna entre llamar a su antiguo repositorio local y llamar a esta API.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.application.ports import (
    PuertoCandados,
    PuertoContratos,
    PuertoInformes,
    PuertoPertenencia,
    PuertoPoblacion,
    PuertoProrrogas,
    PuertoReferencias,
)
from app.domain.catalogo import MDM_CANDADO, TABLAS_PERTENENCIA
from app.domain.exceptions import PeticionInvalida
from app.domain.tiempo import a_hora_local_legacy

VACIO_PRORROGAS_CREDITO = {
    "proximo_bloqueo": None, "estado_candado": None, "vigente": None, "prorrogas": [],
}


def sanear_imeis(imeis) -> list[str]:
    """Misma sanitización del cliente actual: filtra None ANTES de str() (bug
    histórico del IMEI literal 'None') y descarta vacíos."""
    return [str(i).strip() for i in (imeis or []) if i is not None and str(i).strip()]


def consultar_candados(repo: PuertoCandados, imeis) -> list[dict[str, Any]]:
    limpios = sanear_imeis(imeis)
    # Sin IMEIs = listado completo de candados ALOTONIC vigentes (mismo contrato
    # que el repositorio original: lista vacía y None son equivalentes).
    return repo.consultar_candados(limpios or None)


def prorrogas_credito_por_imei(repo: PuertoCandados, imei, limite) -> dict[str, Any]:
    imei = str(imei or "").strip()
    if not imei:
        return dict(VACIO_PRORROGAS_CREDITO)
    limite = max(1, min(int(limite or 8), 50))
    return repo.prorrogas_credito_por_imei(imei, limite)


def estado_pago_por_imei(repo: PuertoContratos, imeis) -> dict[str, str]:
    limpios = sanear_imeis(imeis)
    if not limpios:
        return {}
    return repo.estado_pago_por_imei(limpios)


def productos_por_imei(repo: PuertoContratos, imeis) -> dict[str, str]:
    limpios = sanear_imeis(imeis)
    if not limpios:
        return {}
    return repo.productos_por_imei(limpios)


def estado_efectivo(repo: PuertoContratos, imeis) -> dict[str, list[dict[str, Any]]]:
    limpios = sanear_imeis(imeis)
    if not limpios:
        return {}
    return repo.estado_efectivo(limpios)


def estado_release_por_imei(repo: PuertoContratos, imei) -> tuple[str, int | None, str]:
    imei = str(imei or "").strip()
    if not imei:
        return "", None, ""
    return repo.estado_release_por_imei(imei)


def titular_por_imei(repo: PuertoContratos, imei, familia) -> dict[str, Any]:
    """Titular del contrato. ``familia`` decide la vista de entrada (TWIST_1.0 va
    por ``view_twist_contracts``); cualquier otro valor entra por PHONE, que es el
    mismo enrutamiento del servicio original (subcadena TWIST_1.0 en el producto)."""
    imei = str(imei or "").strip()
    if not imei:
        return {}
    if familia == "TWIST_1.0":
        return repo.titular_twist_por_imei(imei)
    return repo.titular_phone_por_imei(imei)


def pertenencia(repo: PuertoPertenencia, tablas, imeis) -> dict[str, list[str]]:
    limpios = sanear_imeis(imeis)
    desconocidas = [t for t in (tablas or []) if t not in TABLAS_PERTENENCIA]
    if desconocidas:
        raise PeticionInvalida(f"tablas desconocidas: {', '.join(sorted(desconocidas))}")
    if not tablas:
        raise PeticionInvalida("se requiere al menos una tabla")
    salida: dict[str, list[str]] = {}
    for tabla in tablas:
        presentes = repo.imeis_en_tabla(tabla, limpios) if limpios else set()
        salida[tabla] = sorted(presentes)
    return salida


def conteo_tabla(repo: PuertoPertenencia, tabla) -> int:
    if tabla not in TABLAS_PERTENENCIA:
        raise PeticionInvalida(f"tabla desconocida: {tabla}")
    return repo.conteo_tabla(tabla)


def prorrogas_cortas_vencidas(repo: PuertoProrrogas, sistema, horas_ventana,
                              max_horas_rango, limite) -> list[dict[str, Any]]:
    if sistema not in MDM_CANDADO:
        return []
    limite = max(1, min(int(limite or 500), 5000))
    return repo.cortas_vencidas(sistema, int(horas_ventana), int(max_horas_rango), limite)


def imeis_con_prorroga_nueva(repo: PuertoProrrogas, sistema, desde: datetime | None) -> list[str]:
    if sistema not in MDM_CANDADO or desde is None:
        return []
    # El cursor puede llegar aware (ISO con zona); el legacy compara en hora local naive.
    return repo.imeis_con_prorroga_nueva(sistema, a_hora_local_legacy(desde))


def imeis_candado(repo: PuertoPoblacion, sistema, limit, desde_imei) -> list[str]:
    if sistema not in MDM_CANDADO:
        return []
    return repo.imeis_candado(sistema, limit, desde_imei)


def imei_modelo_candado(repo: PuertoPoblacion, sistema, solo_vigentes) -> list[tuple[str, str]]:
    if sistema not in MDM_CANDADO:
        return []
    return repo.imei_modelo_candado(sistema, bool(solo_vigentes))


def referencias_por_tac(repo: PuertoReferencias, tacs, sistema) -> dict[str, dict[str, str]]:
    tacs = sorted({str(t).strip() for t in (tacs or []) if t is not None and str(t).strip()})
    if not tacs or sistema not in MDM_CANDADO:
        return {}
    return repo.referencias_por_tac(tacs, sistema)


def contratos_por_lock_system(repo: PuertoInformes, lock_system) -> list[dict[str, Any]]:
    lock_system = str(lock_system or "").strip()
    if not lock_system:
        raise PeticionInvalida("se requiere lock_system")
    return repo.contratos_por_lock_system(lock_system)


def catalogo_device_location(repo: PuertoInformes) -> list[tuple[str, str]]:
    return repo.catalogo_device_location()
