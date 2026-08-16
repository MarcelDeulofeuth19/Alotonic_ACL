"""Punto de entrada del servicio Alotonic_ACL.

ACL (Anti-Corruption Layer) de la base legacy MySQL ``alocreditprod``: único
punto por el que AloTonic consulta el legacy. Arquitectura hexagonal:

- ``domain``: entidades/errores del negocio, sin dependencias externas.
- ``application``: puertos (contratos) y casos de uso.
- ``infrastructure``: adaptadores MySQL que implementan los puertos.
- ``presentation``: API HTTP (FastAPI), auth y traducción de errores.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.exceptions import BaseLegacyNoDisponible, PeticionInvalida

logger = logging.getLogger("alotonic_acl")


def crear_app() -> FastAPI:
    app = FastAPI(
        title="Alotonic ACL",
        description="API única de acceso a la base legacy alocreditprod",
        version="1.0.0",
        docs_url=None,           # servicio interno: sin Swagger público
        redoc_url=None,
        openapi_url=None,
    )

    @app.exception_handler(BaseLegacyNoDisponible)
    async def _legacy_caido(request: Request, exc: BaseLegacyNoDisponible) -> JSONResponse:
        # El detalle del driver (hosts, SQL) se queda en el log; el consumidor
        # recibe un mensaje genérico y accionable.
        logger.error("Base legacy no disponible en %s: %s", request.url.path, exc)
        return JSONResponse(status_code=503, content={"detail": "base legacy no disponible"})

    @app.exception_handler(PeticionInvalida)
    async def _peticion_invalida(request: Request, exc: PeticionInvalida) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/health")
    def health() -> dict:
        """Vivo/listo para el orquestador. No toca la base: un legacy caído no
        debe tumbar el servicio (los endpoints ya responden 503 por operación)."""
        return {"status": "ok", "service": "alotonic-acl"}

    _registrar_routers(app)
    return app


def _registrar_routers(app: FastAPI) -> None:
    # Los routers por contexto se registran aquí (candados, productos, resolver...).
    from app.presentation.api.routers import registrar

    registrar(app)


app = crear_app()
