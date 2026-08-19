<h1 align="center">📦 Sistema de Abastecimiento Inteligente (SAI)</h1>

<p align="center">
  <strong>Orquestador multi-local para la automatización logística y financiera.</strong><br>
  Construido con Python, SQLAlchemy y Google Sheets API.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/Google_Sheets-API-34A853.svg" alt="Google Sheets">
  <img src="https://img.shields.io/badge/SQLite-Database-003B57.svg" alt="SQLite">
  <img src="https://img.shields.io/badge/Status-Prototipo_validado-blue.svg" alt="Status">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

---

## 📖 Descripción del Proyecto

> [!NOTE]
> **Estado del proyecto.** Diseñado y prototipado para un entorno multi-local real: relevamiento de la operación, modelo de datos y flujo completo funcionando de punta a punta. Fue presentado a dirección financiera y quedó pendiente de implementación. Los datos incluidos en el repositorio son sintéticos (`demo_injector.py`).

El **Sistema de Abastecimiento Inteligente (SAI)** es una solución de backend distribuido diseñada para automatizar la cadena de suministro en múltiples sucursales locales. Combina la accesibilidad y nula curva de aprendizaje de Google Sheets (como frontend) con la robustez transaccional de una base de datos centralizada (SQLite/Cloud SQL) y orquestación en Python.

**SAI resuelve problemas críticos operativos:**
- 🚫 Eliminación de pedidos fuera de horario y errores de tipeo manuales.
- 📉 Visibilidad en tiempo real del inventario y las cuentas por pagar (Fill Rate y Total Real).
- 🚚 Trazabilidad completa de recepciones e incidencias (reclamos) con proveedores.
- 📊 Sincronización automática con Data Warehouse para dashboards en Data Studio/Looker.

## 🚀 Arquitectura

El ecosistema está dividido en 4 capas fundamentales:

1. **Master (Control Central):** Un Google Sheet donde Finanzas/Compras definen los SKUs, los proveedores, precios y horarios de corte (Deadlines).
2. **Locales (Frontend Operativo):** Cada sucursal tiene su propia plantilla sincronizada. Cuenta con pestañas blindadas y protegidas para realizar `PEDIDOS`, auditar `STOCK`, realizar `RECEPCION` y gestionar `RECLAMOS`.
3. **Orquestador (El Motor):** Scripts en Python (`main.py`) que leen los datos de todos los locales en paralelo, calculan reglas de negocio, y registran estados en una base de datos relacional. Genera órdenes de compra consolidadas por proveedor.
4. **Data Warehouse (Analítica):** Exportación continua de la "verdad financiera" (`Total_Real`, `Fill Rate`, métricas de proveedores) para visualización ejecutiva.

## ✨ Características Principales

- **Validaciones Inteligentes:** "Semáforos" visuales en celdas, protección contra escritura de columnas clave y dropdowns auto-completados.
- **Gestión Avanzada de Reclamos:** Flujo de auditoría automatizado para gestionar *Faltantes* y *Productos Dañados*, impactando directamente en la métrica financiera del proveedor sin alterar falsamente el inventario.
- **Notificaciones Automatizadas:** Integración de envío de correos (`mailer.py`) con adjuntos PDF/CSV para despachar las órdenes consolidadas a los proveedores.
- **Auditoría Global (`audit_job.py`):** Exportación programada de reportes ejecutivos.
- **Modo Demo (`--manual`):** Capacidad para ejecutar simulaciones ignorando restricciones horarias, ideal para pruebas de estrés y presentaciones directivas.

## 🛠️ Stack Tecnológico

- **Lenguaje:** Python 3.9+
- **Database:** SQLAlchemy (SQLite default, fácilmente escalable a PostgreSQL/Cloud SQL)
- **Integraciones:** `gspread`, `oauth2client` (Google Drive & Sheets API)
- **Gestión de Entorno:** `python-dotenv`

## ⚙️ Instalación y Configuración

### 1. Clonar el Repositorio
```bash
git clone https://github.com/SimonChiabo/Sistema-de-Abastecimiento-Inteligente.git
cd Sistema-de-Abastecimiento-Inteligente
```

### 2. Entorno Virtual y Dependencias
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Variables de Entorno (`.env`)
Copiá `.env.example` a `.env` y completá los valores:
```bash
cp .env.example .env
```
```env
# Google Sheets API
CREDENTIALS_PATH=credentials.json
MASTER_SPREADSHEET_NAME=SAI - Sistema de Abastecimiento
LOCAL_PREFIX=SAI_Local_

# Base de datos
DB_URL=sqlite:///sai_local.db

# Notificaciones (contraseña de aplicación, no la de la cuenta)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-cuenta@ejemplo.com
SMTP_PASS=
ADMIN_EMAIL=tu-cuenta@ejemplo.com

# Sincronización con depósito central (opcional)
WAREHOUSE_SYNC_ENABLED=false
WAREHOUSE_SPREADSHEET_ID=
```
*(Colocá tu `credentials.json` —cuenta de servicio generada en Google Cloud Console, con Sheets API y Drive API habilitadas— en el directorio raíz. Está en `.gitignore`.)*

## 🏃‍♂️ Uso Operativo

### Inicializar Plantillas Locales
Para crear y formatear (colores, validaciones, bloqueos) una plantilla local:
```bash
python setup_local.py "SAI_Local_01"
```

### Ejecutar el Orquestador
Para iniciar el ciclo de conciliación de pedidos y actualización de base de datos (generalmente configurado en un CRON Job):
```bash
python main.py
```
> Añade el flag `--manual` para ignorar los horarios de corte durante demostraciones.

### Inyectar Datos de Prueba
Para llenar la base de datos y limpiar historiales en ambientes de desarrollo:
```bash
python demo_injector.py
```

## 📂 Estructura del Proyecto

```text
├── core/
│   ├── auth.py             # Autenticación con Google APIs
│   ├── db_handler.py       # Modelos ORM y lógica de Base de Datos
│   ├── log_config.py       # Sistema de logs estandarizado
│   └── reception.py        # Procesamiento de feedback y reclamos multi-local
├── logs/                   # Registro diario (.log, no versionado)
├── main.py                 # Orquestador principal (Entrypoint)
├── setup_local.py          # Configuración y formateo de templates
├── warehouse_sync.py       # Sincronización con Data Studio / Looker
├── mailer.py               # Generación y envío de Órdenes de Compra
├── audit_job.py            # Reportería ejecutiva
├── demo_injector.py        # Inyector de datos sintéticos (White-label)
└── .env.example            # Plantilla de variables de entorno
```

## 🛡️ Licencia

Distribuido bajo licencia MIT. Ver [`LICENSE`](LICENSE) para el texto completo.
