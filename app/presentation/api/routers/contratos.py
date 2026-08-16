from fastapi import APIRouter, Depends

from app.application import use_cases
from app.application.ports import PuertoContratos
from app.presentation.api.repos import get_repo_contratos, validar_tope_imeis
from app.presentation.api.schemas import PeticionImeis
from app.presentation.api.serializacion import a_json

router = APIRouter(prefix="/contratos", tags=["contratos"])


@router.post("/productos")
def productos(peticion: PeticionImeis,
              repo: PuertoContratos = Depends(get_repo_contratos)) -> dict:
    """{imei: 'PHONE'|'TWIST_1.0'} según el contrato vigente más reciente. Los IMEIs
    sin contrato en el legacy NO aparecen (serán TWIST 2.0/3.0 de PDS o sin contrato)."""
    validar_tope_imeis(peticion.imeis)
    return {"productos": use_cases.productos_por_imei(repo, peticion.imeis)}


@router.post("/estado-pago")
def estado_pago(peticion: PeticionImeis,
                repo: PuertoContratos = Depends(get_repo_contratos)) -> dict:
    """{imei: 'en_mora'|'al_dia'}; en_mora = cuota ATRASADA con el código propio de
    la familia (PHONE=4, TWIST 1.0=3). IMEIs sin contrato legacy no aparecen."""
    validar_tope_imeis(peticion.imeis)
    return {"estados": use_cases.estado_pago_por_imei(repo, peticion.imeis)}


@router.post("/estado-efectivo")
def estado_efectivo(peticion: PeticionImeis,
                    repo: PuertoContratos = Depends(get_repo_contratos)) -> dict:
    """{imei: [{familia, contract_id, en_mora, lock_date}]} — TODOS los contratos
    vigentes del IMEI. lock_date = prórroga activa más reciente (datetime naive local)."""
    validar_tope_imeis(peticion.imeis)
    return {"contratos": a_json(use_cases.estado_efectivo(repo, peticion.imeis))}


@router.get("/estado-release/{imei}")
def estado_release(imei: str,
                   repo: PuertoContratos = Depends(get_repo_contratos)) -> dict:
    """Contrato MÁS RECIENTE a secas (regla de liberación, no prioriza activos)."""
    familia, status_id, status_nombre = use_cases.estado_release_por_imei(repo, imei)
    return {"familia": familia, "status_id": status_id, "status_nombre": status_nombre}


@router.get("/titular/{imei}")
def titular(imei: str, familia: str = "",
            repo: PuertoContratos = Depends(get_repo_contratos)) -> dict:
    """Titular del contrato (dni, doctype, email, contract_id, imei) o {} si no
    resuelve. ``familia=TWIST_1.0`` entra por view_twist_contracts; el resto por PHONE.
    Con fallbacks a la cadena real de contrato (las vistas no cubren todo)."""
    return {"titular": use_cases.titular_por_imei(repo, imei, familia)}
