"""Registro central de routers. Cada contexto aporta su router; este módulo
los monta bajo /api/v1 con la auth de API key como dependencia global.
"""
from fastapi import Depends, FastAPI

from app.presentation.api.deps import requiere_api_key

PREFIJO = "/api/v1"


def registrar(app: FastAPI) -> None:
    # Import tardío: evita ciclos y mantiene main.py ignorante de los contextos.
    routers = _routers()
    for router in routers:
        app.include_router(router, prefix=PREFIJO, dependencies=[Depends(requiere_api_key)])


def _routers() -> list:
    from app.presentation.api.routers import (
        candados,
        contratos,
        dispositivos,
        informes,
        poblacion,
        prorrogas,
        referencias,
    )

    return [
        candados.router,
        contratos.router,
        dispositivos.router,
        informes.router,
        poblacion.router,
        prorrogas.router,
        referencias.router,
    ]
