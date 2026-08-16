"""Dependencias de la API: autenticación por API key.

El servicio es interno (AloTonic -> ACL) y se autentica con ``X-Api-Key``.
Comparación en tiempo constante y sin claves configuradas se rechaza todo:
el servicio jamás queda "abierto" por un .env incompleto.
"""
import hmac

from fastapi import Header, HTTPException, status

from app.config import get_settings


def requiere_api_key(x_api_key: str = Header(default="")) -> None:
    claves = get_settings().api_keys()
    if not claves or not any(hmac.compare_digest(x_api_key, k) for k in claves):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key invalida o ausente",
        )
