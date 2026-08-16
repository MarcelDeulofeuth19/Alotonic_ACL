"""Catálogo del legacy alocreditprod: los hechos fijos del modelo de datos.

Copiado 1:1 del cliente actual de AloTonic (candados_alotonic_repository) — este
módulo ES la fuente de esas constantes de ahora en adelante. Ningún nombre de
tabla/columna proviene de entrada de usuario: siempre se resuelven contra estos
literales antes de interpolarse en SQL.
"""

# Tablas de candado (device) y su FK en application/twist_application. El candado NO
# determina el producto: el mismo device puede pertenecer a un contrato PHONE
# (``application``) o TWIST 1.0 (``twist_application``); TWIST 1.0 no usa paytrigger.
DEVICE_FK = (
    ("paytrigger_device", "paytrigger_device_id"),
    ("knox_device", "knox_device_id"),
    ("nuovo_device", "nuovo_device_id"),
    ("trustonic_device", "trustonic_device_id"),
)

# Estados de contrato que NO cuentan como vigentes (Completado/Anulado/Prepagado/
# Fraude/Cerrado + Fallecido[PHONE]/Garantia[TWIST], mismos ids en ambos catalogos).
ESTADOS_NO_VIGENTES = (4, 5, 6, 7, 8, 9)

# Código de cuota ATRASADA (vencida sin pagar) por familia — VERIFICADO en prod:
# los catálogos difieren. contract_amortization_payment_status: 4=Atrasado.
# twist_contract_amortization_payment_status: 3=Atrasado (¡2=Pendiente, 4=Pagado!).
ATRASADO_STATUS = {"PHONE": 4, "TWIST_1.0": 3}

# Candado (nombre local del MDM) -> (tabla de device, FK en application) en el legacy.
# TRAMPA de nombres: la tabla ``paytrigger_device`` es el candado local "globetek"
# (candado ALOTONIC); el candado local "paytrigger" NO tiene tabla en el legacy.
MDM_CANDADO = {
    "globetek": ("paytrigger_device", "paytrigger_device_id"),
    "knox": ("knox_device", "knox_device_id"),
    "trustonic": ("trustonic_device", "trustonic_device_id"),
    "nuovo": ("nuovo_device", "nuovo_device_id"),
}

# Alias público que expone /dispositivos/pertenencia: nombre corto -> tabla real.
TABLAS_PERTENENCIA = {
    "paytrigger": "paytrigger_device",
    "trustonic": "trustonic_device",
    "knox": "knox_device",
    "nuovo": "nuovo_device",
}

# Prórrogas del CRM de crédito.
#   - ``lock_date``     = VENCIMIENTO de la prórroga (nueva fecha de bloqueo).
#   - ``active``        NO significa "vigente": se apaga cuando el CRM la procesa. La
#     vigencia se juzga SIEMPRE por ``lock_date`` vs ahora, nunca por ``active``.
TIPO_PRORROGA_CRM = {0: "otra", 1: "salvavidas", 2: "canoa"}

# Cadena tabla-prórroga -> contrato -> application, por familia de producto:
#   (familia, tabla_prorroga, fk_contrato, tabla_contrato, fk_application, tabla_application)
PRORROGA_CRM = (
    ("PHONE", "contracts_user_prorroga", "contract_id",
     "contract", "application_id", "application"),
    ("TWIST_1.0", "twist_contracts_user_prorroga", "twist_contract_id",
     "twist_contract", "twist_application_id", "twist_application"),
)

# Tabla de cuotas por familia, para juzgar si el cliente sigue en mora.
# OJO: la columna de TWIST NO sigue el nombre de su tabla (es ...payment_status_id,
# no ...amortization_payment_status_id) y su catálogo difiere (3=Atrasado).
AMORTIZACION = {
    "PHONE": ("contract_amortization", "contract_id", "contract_amortization_payment_status_id"),
    "TWIST_1.0": ("twist_contract_amortization", "twist_contract_id",
                  "twist_contract_payment_status_id"),
}

FAMILIAS = ("PHONE", "TWIST_1.0")


def tipo_prorroga_crm(tipo):
    """Nombre del tipo de prórroga del CRM ('salvavidas'/'canoa'/...) desde su id."""
    try:
        return TIPO_PRORROGA_CRM.get(int(tipo), f"tipo_{int(tipo)}")
    except (TypeError, ValueError):
        return "desconocido"


def placeholders(vals):
    """Placeholders ``%s`` para una cláusula IN (patrón del legacy, sin ``IN %s``)."""
    return ",".join(["%s"] * len(vals))
