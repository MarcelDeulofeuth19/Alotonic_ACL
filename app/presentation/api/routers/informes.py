from fastapi import APIRouter, Depends

from app.application import use_cases
from app.application.ports import PuertoInformes
from app.presentation.api.repos import get_repo_informes
from app.presentation.api.serializacion import a_json

router = APIRouter(prefix="/informes", tags=["informes"])


@router.get("/contratos-lock-system")
def contratos_lock_system(sistema: str,
                          repo: PuertoInformes = Depends(get_repo_informes)) -> dict:
    """Contratos Activo/Atrasado/Default de ``view_general_contracts`` para un
    lock_system (informe de liberados). Vista pesada: timeout amplio propio."""
    return {"filas": a_json(use_cases.contratos_por_lock_system(repo, sistema))}


@router.get("/catalogo-device-location")
def catalogo_device_location(repo: PuertoInformes = Depends(get_repo_informes)) -> dict:
    """(description, tags_model_device) de ``view_device`` para la sync horaria del
    catálogo de Ubicaciones."""
    return {"filas": use_cases.catalogo_device_location(repo)}
