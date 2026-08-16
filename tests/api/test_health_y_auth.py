import hmac

from app.presentation.api.deps import requiere_api_key


def test_health_responde_sin_api_key(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "alotonic-acl"}


def test_swagger_apagado_en_servicio_interno(cliente):
    assert cliente.get("/docs").status_code == 404
    assert cliente.get("/openapi.json").status_code == 404


def test_requiere_api_key_rechaza_clave_ausente(cliente):
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        requiere_api_key(x_api_key="")
    assert exc.value.status_code == 401


def test_requiere_api_key_rechaza_clave_incorrecta(cliente):
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        requiere_api_key(x_api_key="clave-equivocada")
    assert exc.value.status_code == 401


def test_requiere_api_key_acepta_clave_valida(cliente, cabeceras_auth):
    assert requiere_api_key(x_api_key=cabeceras_auth["X-Api-Key"]) is None


def test_sin_claves_configuradas_se_rechaza_todo(monkeypatch):
    import pytest
    from fastapi import HTTPException

    from app.config import get_settings

    monkeypatch.setenv("ACL_API_KEYS", "")
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as exc:
        requiere_api_key(x_api_key="cualquiera")
    assert exc.value.status_code == 401
    get_settings.cache_clear()


def test_comparacion_en_tiempo_constante_es_la_usada():
    # Guarda de estilo: la comparación debe ser hmac.compare_digest (no ==).
    import inspect

    fuente = inspect.getsource(requiere_api_key)
    assert "compare_digest" in fuente
    assert hmac.compare_digest("a", "a")
