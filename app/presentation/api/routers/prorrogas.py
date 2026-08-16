from datetime import datetime

from fastapi import APIRouter, Depends

from app.application import use_cases
from app.application.ports import PuertoProrrogas
from app.presentation.api.repos import get_repo_prorrogas

router = APIRouter(prefix="/prorrogas", tags=["prorrogas"])


@router.get("/cortas-vencidas")
def cortas_vencidas(sistema: str, horas_ventana: int = 6, max_horas_rango: int = 24,
                    limite: int = 500,
                    repo: PuertoProrrogas = Depends(get_repo_prorrogas)) -> dict:
    """Prórrogas CORTAS recién vencidas con contrato vigente (candidatos a re-bloqueo).
    Sistema fuera de catálogo devuelve lista vacía (mismo contrato del original)."""
    filas = use_cases.prorrogas_cortas_vencidas(repo, sistema, horas_ventana,
                                                max_horas_rango, limite)
    return {"filas": filas}


@router.get("/nuevas")
def nuevas(sistema: str, desde: datetime,
           repo: PuertoProrrogas = Depends(get_repo_prorrogas)) -> dict:
    """IMEIs con prórroga ACTIVA nueva desde el cursor (delta por timestamp).
    ``desde`` en ISO-8601; si trae zona se convierte a la hora local naive del
    legacy — la trampa horaria queda encapsulada aquí."""
    return {"imeis": use_cases.imeis_con_prorroga_nueva(repo, sistema, desde)}
