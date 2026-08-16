from fastapi import APIRouter, Depends

from app.application import use_cases
from app.application.ports import PuertoPertenencia
from app.presentation.api.repos import get_repo_pertenencia, validar_tope_imeis
from app.presentation.api.schemas import PeticionPertenencia

router = APIRouter(prefix="/dispositivos", tags=["dispositivos"])


@router.post("/pertenencia")
def pertenencia(peticion: PeticionPertenencia,
                repo: PuertoPertenencia = Depends(get_repo_pertenencia)) -> dict:
    """{tabla: [imeis presentes]} para tablas ∈ {paytrigger, trustonic, knox, nuovo}.
    Es el tramo legacy del resolver de proveedores: hechos crudos de membresía;
    la precedencia y los cross-checks son negocio del consumidor."""
    validar_tope_imeis(peticion.imeis)
    return {"pertenencia": use_cases.pertenencia(repo, peticion.tablas, peticion.imeis)}


@router.get("/conteo/{tabla}")
def conteo(tabla: str,
           repo: PuertoPertenencia = Depends(get_repo_pertenencia)) -> dict:
    """Total de filas de la tabla de candado (diagnóstico: alerta si nuovo=0)."""
    return {"total": use_cases.conteo_tabla(repo, tabla)}
