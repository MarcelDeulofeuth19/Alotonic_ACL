# Alotonic_ACL

**ACL (Anti-Corruption Layer) de la base legacy MySQL `alocreditprod`.** API HTTP
interna: el ÚNICO punto por el que AloTonic (y cualquier consumidor futuro) accede
al legacy. AloTonic no vuelve a abrir una conexión MySQL directa.

## Arquitectura (hexagonal)

```
app/
├── domain/           # hechos del legacy: catálogo de tablas/códigos, zona horaria, errores
├── application/      # puertos (Protocols) + casos de uso (normalización idéntica al cliente original)
├── infrastructure/   # adaptadores MySQL (SQL copiado 1:1 del cliente embebido de AloTonic)
└── presentation/     # FastAPI: routers por contexto, auth X-Api-Key, serialización tipada
```

Principios:

- **Paridad primero**: el SQL, la sanitización, los clamps y los retornos degenerados
  son copia exacta del cliente que vivía dentro de AloTonic. El consumidor no nota
  la diferencia.
- **Solo lectura**: no existe ningún endpoint de escritura (verificado: producción
  jamás escribió SQL contra alocreditprod).
- **Fidelidad de tipos**: datetime/date/Decimal viajan etiquetados
  (`{"$tipo": "datetime", "$v": ...}`) y el cliente los reconstruye idénticos a
  los que devolvía pymysql.
- **Trampas encapsuladas**: hora local Colombia naive del legacy, códigos de cuota
  que difieren por familia (PHONE=4 / TWIST 1.0=3), `paytrigger_device` = candado
  "globetek", vistas incompletas con fallback por contrato real.

## Endpoints (prefijo `/api/v1`, auth `X-Api-Key`)

| Endpoint | Reemplaza a |
|---|---|
| `POST /candados/consultar` | `consultar_candados_alotonic` |
| `GET /candados/prorrogas-credito/{imei}` | `prorrogas_credito_por_imei` |
| `POST /contratos/productos` | `productos_por_imei_alocredit` |
| `POST /contratos/estado-pago` | `estado_pago_por_imei_alocredit` |
| `POST /contratos/estado-efectivo` | `estado_efectivo_alocredit` |
| `GET /contratos/estado-release/{imei}` | `estado_contrato_release_por_imei` |
| `GET /contratos/titular/{imei}?familia=` | `titular_contrato_por_imei` / `titular_twist_por_imei` |
| `POST /dispositivos/pertenencia` | tramo MySQL de `resolver_proveedores` |
| `GET /dispositivos/conteo/{tabla}` | diagnóstico COUNT del resolver |
| `GET /prorrogas/cortas-vencidas` | `prorrogas_cortas_vencidas` |
| `GET /prorrogas/nuevas?sistema=&desde=` | `imeis_con_prorroga_nueva` |
| `GET /poblacion/imeis` | `enumerar_imeis_candado_mdm` |
| `GET /poblacion/imei-modelo` | `enumerar_imei_modelo_candado_mdm` |
| `POST /referencias/por-tac` | `referencias_por_tac` |
| `GET /informes/contratos-lock-system` | consulta trustonic de `view_general_contracts` |
| `GET /informes/catalogo-device-location` | consulta `view_device` de la sync horaria |

`GET /health` es público (no toca la base). Swagger/OpenAPI está apagado (servicio
interno).

## Desarrollo

```bash
make venv    # crea .venv e instala dependencias (con nice/ionice)
make test    # pytest con gate de cobertura >= 96% (falla si baja)
make lint    # flake8
```

## Lado AloTonic (consumidor)

`core/infrastructure/acl_api_client.py` es el espejo HTTP del repositorio. El
switch es **por configuración**:

- Sin `ACL_API_URL` en el entorno → AloTonic usa su camino MySQL directo (estado
  actual, cero cambio de comportamiento).
- Con `ACL_API_URL` (+ `ACL_API_KEY`) → el repositorio `candados_alotonic_repository`,
  el resolver de proveedores y las 2 tasks con SQL ad-hoc delegan TODO en esta API.

## Runbook de despliegue y cutover (NO ejecutar sin ventana controlada)

La instancia es PROD en vivo. Orden estricto:

1. **Preparar**: `cp .env.example .env`, copiar los `MYSQL_*` del `.env` de AloTonic,
   generar `ACL_API_KEYS` (`python -c "import secrets; print(secrets.token_urlsafe(48))"`).
2. **Build en ventana controlada** (revisar `free -h` y load antes):
   `docker compose build` — la imagen es pequeña (python:3.12-slim, sin Chrome).
3. **Levantar**: `docker compose up -d`. Verificar `curl -s localhost:8090/health`
   y un smoke con API key:
   `curl -s -H "X-Api-Key: $KEY" "localhost:8090/api/v1/dispositivos/conteo/nuovo"`.
4. **Sombra (opcional recomendado)**: comparar 2-3 respuestas del ACL contra el
   camino directo con IMEIs conocidos antes de conmutar.
5. **Conmutar AloTonic**: añadir al `.env` de AloTonic
   `ACL_API_URL=http://alotonic_acl:8090` y `ACL_API_KEY=<la key>`;
   `docker restart alotonic-web-1` (+ workers celery). Downtime ~3 s.
6. **Verificar**: panel de soporte (consultar IMEI), resolver en una notificación,
   y `grep "via ACL" logs`. Los errores del ACL responden 503 y se loggean con ruta.
7. **Rollback inmediato**: quitar `ACL_API_URL` del `.env` y reiniciar — vuelve el
   camino MySQL directo sin tocar código.
8. **Fase final (tras días estables)**: retirar de AloTonic el camino MySQL directo
   (los bloques `else` de la fachada) y la dependencia pymysql de esos módulos.

## Seguridad

- API key obligatoria (comparación en tiempo constante); sin claves configuradas
  se rechaza todo.
- Puerto publicado SOLO en loopback; AloTonic llega por la red docker
  `alotonic_default` (mismo patrón que PadLock).
- Contenedor sin privilegios (usuario `acl`), imagen slim sin toolchain.
- El detalle de errores del driver queda en logs; el consumidor recibe un 503 genérico.
# Alotonic_ACL
