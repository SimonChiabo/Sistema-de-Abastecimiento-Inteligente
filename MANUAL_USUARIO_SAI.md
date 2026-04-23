# Manual de Usuario: Sistema de Abastecimiento Inteligente (SAI)

Este documento detalla el funcionamiento y las responsabilidades para cada uno de los tres niveles de la arquitectura SAI.

---

## 🏗️ Nivel 1: Hub Central (Mandos Intermedios)
**Archivo**: `SAI - Sistema de Abastecimiento`
**Perfil**: Directores de Compras / Gerencia Operativa

### Propósito
Gestionar el catálogo maestro de productos y la base de datos de proveedores que alimentan a todos los locales de Andorra.

### 📋 Gestión de MASTER_SKU
En esta pestaña se definen los artículos que los locales pueden pedir.
*   **SKU_ID**: Identificador único (Ej: `SKU-CAR-01`). **NUNCA** duplicar ni cambiar una vez creado.
*   **Nombre/Categoría**: Información comercial que aparecerá en los reportes.
*   **Precio_Ref**: Precio unitario de mercado. El operario no lo ve, pero el sistema lo usa para calcular el gasto proyectado.
*   **Proveedor_ID**: Vincula el producto con su distribuidor.

### 🚚 Gestión de MASTER_PROV
Configuración logca de los distribuidores.
*   **Hora_Limite**: Muy importante. Si un operario pide después de esta hora (ej: 20:00), el pedido se marcará como `LATE` (Atrasado) y se auditará la demora.
*   **Email**: Dirección donde llegarán las órdenes de compra automáticas.

> [!WARNING]
> **Regla de Oro**: Cualquier cambio en esta hoja se propaga a los 12 locales en el siguiente ciclo del bot. Evite borrar filas; prefiera dejar los campos vacíos si un producto ya no está disponible.

---

## 📱 Nivel 2: Locales Distribuidos (Operarios)
**Archivo**: `SAI_Local_Template` (o el nombre específico del local)
**Perfil**: Personal de cocina / Almacén / Responsables de local

### Propósito
Operación diaria: realizar pedidos, confirmar recepción de mercancía y contar stock.

### 🛒 Pestaña: PEDIDOS
Diseñada para un uso rápido desde tablets y móviles.
1.  **Producto**: Seleccione el artículo del desplegable. El `SKU_ID` se completará solo.
2.  **Cantidad**: Ingrese la cantidad necesaria.
3.  **Pedidos Acumulados**: Observe esta columna. Si ya hay un número, significa que un compañero ya pidió esa cantidad hoy. **Sume a ese valor si necesita más**.
4.  **Confirmar**: Marque el checkbox para enviar.

### 📦 Pestaña: RECEPCIÓN
Aquí es donde el bot le informará qué pedidos están "En Camino".
*   **Cant_Recibida**: El operario debe anotar lo que realmente llegó físicamente.
*   **Estado_Articulo**: Seleccione el estado (OK, Faltante, Dañado). Esto alimenta el reporte de calidad de proveedores.

### 📉 Pestaña: STOCK
Para inventarios periódicos. El sistema le muestra la lista de productos y usted solo rellena el conteo físico.

> [!TIP]
> **Consejo Pro**: El bot "limpia" tus pedidos una vez procesados. Si ves que tu fila de `PEDIDOS` vuelve a estar blanca y el log dice "OK", significa que el pedido ya está en la base de datos central.

---

## 📊 Nivel 3: Data Warehouse (Sistemas / BI)
**Archivo**: `SAI_Data_Warehouse`
**Perfil**: Analistas de Datos / Dueño de Negocio

### Propósito
Servir como fuente de verdad inmutable para Looker Studio y auditorías financieras.

### 🛑 Advertencia de Seguridad
**ESTA HOJA NO DEBE SER TOCADA MANUALMENTE.**
*   Cualquier edición manual (borrar una fila, cambiar un número) romperá la integridad del dashboard de Looker Studio y la auditoría histórica.
*   Esta hoja es puramente de **SALIDA** de datos desde el motor de Python.

### Funcionamiento
*   Cada 2 horas (o según programación), el bot inyecta aquí los registros procesados.
*   Los datos ya vienen con el nombre del proveedor y del producto "pre-unidos" para que Looker Studio no tenga que hacer cálculos lentos.

---

## 🛠️ Operaciones Avanzadas (Presentación / Auditoría)
**Acceso**: CLI / Servidor
**Perfil**: Administrador de Sistemas / Presentador

### 🚀 Levantamiento Manual de Pedidos
Para demostraciones o situaciones de emergencia donde se requiere procesar pedidos fuera del horario establecido (ignorar `LATE` status):

1.  Abrir una terminal en el directorio raíz del proyecto.
2.  Ejecutar el siguiente comando:
    ```powershell
    python main.py --manual
    ```
3.  **Efecto**: El bot procesará todos los pedidos confirmados en los locales, marcándolos como `OK` en lugar de `LATE`, permitiendo visualizar el flujo completo de abastecimiento instantáneamente.

---

> [!IMPORTANT]
> **SOPORTE TÉCNICO**: Si el sistema no detecta un nuevo local, asegúrese de que el archivo del mismo comience con el prefijo `SAI_Local_` y esté compartido con `sai-bot@sai-sistema-abastecimiento.iam.gserviceaccount.com`.
