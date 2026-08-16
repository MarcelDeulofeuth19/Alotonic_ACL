"""Configuración del servicio por variables de entorno (pydantic-settings).

Los nombres MYSQL_* son los mismos que ya usa la operación en AloTonic, para que
el .env de este servicio se arme copiando los valores existentes sin traducción.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Conexión a la base legacy alocreditprod (mismos timeouts que el cliente actual).
    mysql_host: str = ""
    mysql_port: int = 3306
    mysql_user: str = ""
    mysql_password: str = ""
    mysql_db: str = "alocreditprod"
    mysql_connect_timeout: int = 15
    mysql_read_timeout: int = 60
    # Los informes recorren vistas pesadas (view_general_contracts) que en el cliente
    # original corrían SIN read_timeout; aquí se les da un techo amplio propio.
    mysql_read_timeout_informes: int = 300
    mysql_ssl_enabled: bool = False
    mysql_ssl_ca: str = ""

    # Claves de API de los consumidores (separadas por coma). Sin claves configuradas
    # el servicio rechaza todo: nunca arranca "abierto" por accidente.
    acl_api_keys: str = ""

    # Tope de IMEIs por petición batch (las rutas masivas de AloTonic trocean en
    # bloques de 1000; el tope da margen sin permitir payloads absurdos).
    max_imeis_por_peticion: int = 5000

    def api_keys(self) -> frozenset[str]:
        return frozenset(k.strip() for k in self.acl_api_keys.split(",") if k.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
