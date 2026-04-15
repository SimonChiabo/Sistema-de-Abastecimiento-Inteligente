"""
sync_masters.py — Sincroniza los maestros de Proveedores y SKUs
desde Google Sheets a la base de datos SQLite local.
"""
import logging

from core.auth import obtener_spreadsheet_maestro
from core.db_handler import MasterProv, MasterSku, Session

logger = logging.getLogger(__name__)


def sync_master_providers() -> None:
    """Lee los maestros de Google Sheets y los persiste en SQLite local."""
    logger.info("Sincronizando maestro de proveedores a base de datos local...")

    try:
        sh = obtener_spreadsheet_maestro()

        # --- Proveedores ---
        datos_prov = sh.worksheet("MASTER_PROV").get_all_records()

        session = Session()
        try:
            session.query(MasterProv).delete()

            for p in datos_prov:
                session.add(
                    MasterProv(
                        proveedor_id=str(p["Proveedor_ID"]).strip(),
                        nombre=str(p["Nombre"]).strip(),
                        email=str(p["Email"]).strip(),
                        frecuencia=str(p["Frecuencia"]).strip(),
                        hora_limite=str(p["Hora_Limite"]).strip(),
                        dias_programados=str(p["Dias_Programados"]).strip(),
                    )
                )

            session.commit()
            logger.info("%d proveedores sincronizados.", len(datos_prov))

            # --- SKUs ---
            logger.info("Sincronizando maestro de SKUs a base de datos local...")
            datos_sku = sh.worksheet("MASTER_SKU").get_all_records()

            session.query(MasterSku).delete()
            for s in datos_sku:
                precio_raw = str(s["Precio_Ref"]).replace("$", "").replace(",", ".").strip()
                session.add(
                    MasterSku(
                        sku_id=str(s["SKU_ID"]).strip(),
                        nombre=str(s["Nombre"]).strip(),
                        categoria=str(s["Categoría"]).strip(),
                        presentacion=str(s["Presentación"]).strip(),
                        proveedor_id=str(s["Proveedor_ID"]).strip(),
                        precio_ref=float(precio_raw) if precio_raw else 0.0,
                    )
                )

            session.commit()
            logger.info("%d productos sincronizados.", len(datos_sku))

        except Exception as error:
            session.rollback()
            logger.error("Error al actualizar SQLite: %s", error)
        finally:
            session.close()

    except Exception as error:
        logger.error("Error de conexión con Google Sheets: %s", error)


if __name__ == "__main__":
    from core.log_config import configurar_logging
    configurar_logging()
    sync_master_providers()
