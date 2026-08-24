# SAI — Instalación y uso

Guía técnica del repositorio. Para el contexto de negocio y las decisiones de
diseño, ver el [README](../README.md).

## Requisitos

- Python 3.9+
- Una cuenta de servicio de Google Cloud con **Sheets API** y **Drive API**
  habilitadas, y su `credentials.json`.
- Un spreadsheet maestro compartido con el email de esa cuenta de servicio.

## Instalación

```bash
git clone https://github.com/SimonChiabo/Sistema-de-Abastecimiento-Inteligente.git
cd Sistema-de-Abastecimiento-Inteligente

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Variables de entorno

Copiá la plantilla y completá los valores:

```bash
cp .env.example .env
```

| Variable | Para qué |
|---|---|
| `CREDENTIALS_PATH` | Ruta al JSON de la cuenta de servicio. Está en `.gitignore`. |
| `MASTER_SPREADSHEET_NAME` | Nombre exacto del spreadsheet maestro (`MASTER_SKU` / `MASTER_PROV`). |
| `LOCAL_PREFIX` | Prefijo por el que se descubren los spreadsheets de cada local. |
| `DB_URL` | Cadena SQLAlchemy. Por defecto `sqlite:///sai_local.db`. |
| `SMTP_SERVER` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` | Envío de correo. Usar contraseña de aplicación, no la de la cuenta. |
| `ADMIN_EMAIL` | Destinatario del reporte de auditoría y de las copias en modo demo. |
| `WAREHOUSE_SYNC_ENABLED` | `false` por defecto. Si no es `true`, `main.py` saltea el volcado al warehouse. |
| `WAREHOUSE_SPREADSHEET_ID` | ID del spreadsheet de BI destino. Sin él, el volcado se omite con un warning. |

## Puesta en marcha

```bash
# 1. Crear las pestañas MASTER_SKU y MASTER_PROV en el spreadsheet maestro
python init_setup.py

# 2. (Opcional) Cargar datos maestros de ejemplo en el spreadsheet
python sync_main_masters.py

# 3. Espejar los maestros del spreadsheet a la base local
python sync_masters.py

# 4. Crear y formatear la plantilla de un local
python setup_local.py "SAI_Local_01"
```

`setup_local.py` crea cinco pestañas: `_DB_INTERNAL` (oculta, alimentada por
`IMPORTRANGE` desde el maestro), `PEDIDOS`, `STOCK`, `RECEPCION` y `RECLAMOS`, y
les aplica dropdowns, checkboxes, fondos de color y un rango protegido en modo
aviso sobre la columna de SKU_ID.

## Ciclo operativo

El ciclo son dos ejecuciones distintas. Correr solo `main.py` captura pedidos
pero no genera ninguna orden de compra.

```bash
# Captura: lee PEDIDOS de cada local, consolida en el buffer,
# procesa RECEPCION y RECLAMOS, y vuelca al warehouse si está habilitado.
python main.py

# Despacho: consolida el buffer por proveedor, renderiza la OC HTML
# en outbox/ y archiva los pedidos al historial.
python mailer.py
```

Ambos aceptan `--manual`, que saltea las validaciones de horario y frecuencia y
envía copias a `ADMIN_EMAIL`. Está pensado para demostraciones, no para uso
regular.

```bash
# Auditoría: exporta el historial a CSV y lo envía por correo al administrador.
python audit_job.py

# Datos sintéticos: limpia las tablas e inyecta transacciones de demostración.
python demo_injector.py
```

En un despliegue real, `main.py`, `mailer.py` y `audit_job.py` irían en tareas
programadas separadas, con `mailer.py` posterior a la hora de corte más tardía
del maestro.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

41 tests: 19 de reglas de negocio contra base de datos, 22 del modelo de
proyección y del motor de backtesting. `tests/conftest.py` reapunta el engine a
una base SQLite temporal, así que la suite nunca toca `sai_local.db`.

## Estructura

```text
├── core/
│   ├── auth.py             # Cliente gspread con reintentos y backoff exponencial
│   ├── db_handler.py       # Modelos SQLAlchemy y operaciones sobre buffer e historial
│   ├── log_config.py       # Configuración de logging
│   ├── notifier.py         # Envío SMTP: reporte de auditoría y correos genéricos
│   ├── reception.py        # Distribución y lectura de RECEPCION y RECLAMOS
│   ├── rules.py            # Reglas puras: corte horario, fill rate
│   ├── forecast.py         # Modelo de proyección de pedidos (puro)
│   ├── politicas.py        # Tres políticas de reposición comparables
│   └── backtest.py         # Motor de simulación día por día
├── tests/                  # Suite pytest
├── docs/SETUP.md           # Este archivo
├── main.py                 # Captura de pedidos (entrypoint)
├── mailer.py               # Consolidación y generación de OCs (entrypoint)
├── audit_job.py            # Exportación + envío del reporte de auditoría
├── analytics_export.py     # Volcado del historial a CSV
├── warehouse_sync.py       # Volcado del historial al spreadsheet de BI
├── init_setup.py           # Creación de pestañas maestras
├── sync_masters.py         # Maestros: spreadsheet → base local
├── sync_main_masters.py    # Maestros: datos de ejemplo → spreadsheet
├── setup_local.py          # Creación y formateo de la plantilla de un local
├── demo_injector.py        # Inyector de datos sintéticos
├── test_mail.py            # Prueba manual de la configuración SMTP
├── outbox/                 # OCs generadas (no versionado)
├── logs/                   # Registro diario (no versionado)
└── .env.example            # Plantilla de variables de entorno
```

`credentials.json`, `.env`, `*.db`, `outbox/`, `logs/` y `*.csv` están en
`.gitignore`: el repositorio no contiene credenciales ni datos operativos.
