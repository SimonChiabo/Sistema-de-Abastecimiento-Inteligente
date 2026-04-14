import gspread
from oauth2client.service_account import ServiceAccountCredentials
from core.db_handler import Session, MasterProv, MasterSku

def sync_master_providers():
    print("--- Sincronizando Maestro de Proveedores a Local ---")
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        sh = client.open("SAI - Sistema de Abastecimiento")
        ws_prov = sh.worksheet("MASTER_PROV")
        prov_data = ws_prov.get_all_records()
        
        session = Session()
        try:
            # Limpiar tabla actual (o hacer upsert)
            session.query(MasterProv).delete()
            
            for p in prov_data:
                new_prov = MasterProv(
                    proveedor_id=str(p['Proveedor_ID']).strip(),
                    nombre=str(p['Nombre']).strip(),
                    email=str(p['Email']).strip(),
                    frecuencia=str(p['Frecuencia']).strip(),
                    hora_limite=str(p['Hora_Limite']).strip(),
                    dias_programados=str(p['Dias_Programados']).strip()
                )
                session.add(new_prov)
            
            session.commit()
            print(f"OK: {len(prov_data)} proveedores sincronizados.")
            
            # 2. Sincronizar SKUs
            print("--- Sincronizando Maestro de SKUs a Local ---")
            ws_sku = sh.worksheet("MASTER_SKU")
            sku_data = ws_sku.get_all_records()
            
            session.query(MasterSku).delete()
            for s in sku_data:
                raw_price = str(s['Precio_Ref']).replace('$', '').replace(',', '.').strip()
                new_sku = MasterSku(
                    sku_id=str(s['SKU_ID']).strip(),
                    nombre=str(s['Nombre']).strip(),
                    categoria=str(s['Categoría']).strip(),
                    presentacion=str(s['Presentación']).strip(),
                    proveedor_id=str(s['Proveedor_ID']).strip(),
                    precio_ref=float(raw_price) if raw_price else 0.0
                )
                session.add(new_sku)
            
            session.commit()
            print(f"OK: {len(sku_data)} productos sincronizados.")
            
        except Exception as e:
            session.rollback()
            print(f"ERROR: No se pudo actualizar MASTER_PROV en SQLite. {e}")
        finally:
            session.close()
            
    except Exception as e:
        print(f"ERROR: Fallo en conexión con Google Sheets. {e}")

if __name__ == "__main__":
    sync_master_providers()
