from fastapi import APIRouter, Depends

from app.application import use_cases
from app.application.ports import PuertoPoblacion
from app.presentation.api.repos import get_repo_poblacion

router = APIRouter(prefix="/poblacion", tags=["poblacion"])


@router.get("/imeis")
def imeis(sistema: str, limit: int | None = None, desde_imei: str | None = None,
          repo: PuertoPoblacion = Depends(get_repo_poblacion)) -> dict:
    """IMEIs con contrato VIGENTE del candado, ORDENADOS; paginación por clave
    (``desde_imei`` exclusivo, el llamador usa el último como cursor siguiente)."""
    return {"imeis": use_cases.imeis_candado(repo, sistema, limit, desde_imei)}


@router.get("/imei-modelo")
def imei_modelo(sistema: str, solo_vigentes: bool = False,
                repo: PuertoPoblacion = Depends(get_repo_poblacion)) -> dict:
    """[(imei, model)] del candado, para sembrar TAC HISTORY con el modelo que el
    candado no reporta en vivo."""
    return {"filas": use_cases.imei_modelo_candado(repo, sistema, solo_vigentes)}
