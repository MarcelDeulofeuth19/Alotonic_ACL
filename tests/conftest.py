import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import crear_app

CLAVE_PRUEBA = "clave-de-prueba"

ENTORNO_PRUEBA = {
    "MYSQL_HOST": "mysql.prueba",
    "MYSQL_PORT": "3306",
    "MYSQL_USER": "usuario",
    "MYSQL_PASSWORD": "secreto",
    "MYSQL_DB": "alocreditprod",
    "ACL_API_KEYS": CLAVE_PRUEBA,
}


@pytest.fixture()
def cliente(monkeypatch):
    """TestClient con settings de prueba fijados por entorno.

    Por entorno (y no por dependency_overrides) porque get_settings() también se
    llama directo fuera de Depends (p.ej. en deps.requiere_api_key).
    """
    for clave, valor in ENTORNO_PRUEBA.items():
        monkeypatch.setenv(clave, valor)
    get_settings.cache_clear()
    with TestClient(crear_app()) as c:
        yield c
    get_settings.cache_clear()


@pytest.fixture()
def cabeceras_auth() -> dict:
    return {"X-Api-Key": CLAVE_PRUEBA}
