from fastapi import APIRouter, Depends

from app.application import use_cases
from app.application.ports import PuertoReferencias
from app.presentation.api.repos import get_repo_referencias
from app.presentation.api.schemas import PeticionReferencias

router = APIRouter(prefix="/referencias", tags=["referencias"])


@router.post("/por-tac")
def por_tac(peticion: PeticionReferencias,
            repo: PuertoReferencias = Depends(get_repo_referencias)) -> dict:
    """{tac: {referencia, marca, referencia_larga}} desde el catálogo del CRM.
    Cuando un TAC devuelve varias referencias gana la MÁS FRECUENTE."""
    return {"referencias": use_cases.referencias_por_tac(repo, peticion.tacs, peticion.sistema)}
