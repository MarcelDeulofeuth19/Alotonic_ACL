from app.config import Settings


def _settings(**kwargs) -> Settings:
    return Settings(_env_file=None, **kwargs)


def test_api_keys_parsea_lista_separada_por_comas():
    s = _settings(acl_api_keys="una, dos ,tres,,")
    assert s.api_keys() == frozenset({"una", "dos", "tres"})


def test_api_keys_vacia_no_genera_claves():
    assert _settings(acl_api_keys="").api_keys() == frozenset()


def test_defaults_espejan_al_cliente_actual():
    s = _settings()
    assert s.mysql_port == 3306
    assert s.mysql_connect_timeout == 15
    assert s.mysql_read_timeout == 60
    assert s.mysql_db == "alocreditprod"
    assert s.mysql_ssl_enabled is False
