"""Fábricas de repositorios para inyección de dependencias en los routers.

Los tests de API las sobreescriben con dobles vía ``app.dependency_overrides``.
"""
from app.config import get_settings
from app.domain.exceptions import PeticionInvalida
from app.infrastructure.mysql.candados import RepositorioCandadosMysql
from app.infrastructure.mysql.contratos import RepositorioContratosMysql
from app.infrastructure.mysql.informes import RepositorioInformesMysql
from app.infrastructure.mysql.pertenencia import RepositorioPertenenciaMysql
from app.infrastructure.mysql.poblacion import RepositorioPoblacionMysql
from app.infrastructure.mysql.prorrogas import RepositorioProrrogasMysql
from app.infrastructure.mysql.referencias import RepositorioReferenciasMysql


def get_repo_candados() -> RepositorioCandadosMysql:
    return RepositorioCandadosMysql(get_settings())


def get_repo_contratos() -> RepositorioContratosMysql:
    return RepositorioContratosMysql(get_settings())


def get_repo_pertenencia() -> RepositorioPertenenciaMysql:
    return RepositorioPertenenciaMysql(get_settings())


def get_repo_prorrogas() -> RepositorioProrrogasMysql:
    return RepositorioProrrogasMysql(get_settings())


def get_repo_poblacion() -> RepositorioPoblacionMysql:
    return RepositorioPoblacionMysql(get_settings())


def get_repo_referencias() -> RepositorioReferenciasMysql:
    return RepositorioReferenciasMysql(get_settings())


def get_repo_informes() -> RepositorioInformesMysql:
    return RepositorioInformesMysql(get_settings())


def validar_tope_imeis(imeis) -> None:
    """Techo de IMEIs por petición: da margen a las rutas masivas (chunks de 1000)
    sin aceptar payloads absurdos."""
    tope = get_settings().max_imeis_por_peticion
    if imeis and len(imeis) > tope:
        raise PeticionInvalida(f"maximo {tope} IMEIs por peticion")
