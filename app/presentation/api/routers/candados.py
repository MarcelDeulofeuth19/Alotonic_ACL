from fastapi import APIRouter, Depends

from app.application import use_cases
from app.application.ports import PuertoCandados
from app.presentation.api.repos import get_repo_candados, validar_tope_imeis
from app.presentation.api.schemas import PeticionImeis
from app.presentation.api.serializacion import a_json

router = APIRouter(prefix="/candados", tags=["candados"])


@router.post("/consultar")
def consultar(peticion: PeticionImeis,
              repo: PuertoCandados = Depends(get_repo_candados)) -> dict:
    """Clientes con candado ALOTONIC (GlobeTek) + info de cuota/mora.
    Sin ``imeis`` = todos los candados de contratos vigentes (listado pesado)."""
    validar_tope_imeis(peticion.imeis)
    return {"filas": a_json(use_cases.consultar_candados(repo, peticion.imeis))}


@router.get("/prorrogas-credito/{imei}")
def prorrogas_credito(imei: str, limite: int = 8,
                      repo: PuertoCandados = Depends(get_repo_candados)) -> dict:
    """Prórrogas que el CRM de crédito otorgó al equipo + su próximo bloqueo.
    Fechas como texto en hora local Colombia, tal cual las guarda el legacy."""
    return use_cases.prorrogas_credito_por_imei(repo, imei, limite)
