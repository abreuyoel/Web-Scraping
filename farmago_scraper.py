# farmago_scraper.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import pandas as pd
import time, os, traceback
from datetime import datetime

# Configuración específica para Farmago
RUTA_EXCEL = os.path.join(os.getcwd(), "consolidado_farmago.xlsx")
HEADLESS = True
PRODUCTOS = ["Diclofenac", "Paracetamol", "Ibuprofeno", "Loratadina"]
PROXY = None
INTENTOS = 2
RETRY_DELAY = 10
URL_BASE = "https://www.farmago.com.ve/website/search?search={}&order=name+asc"

# ---------------  FUNCIONES DE APOYO  ---------------
def limpiar_precio(precio_str):
    """Limpia y convierte precios a formato numérico"""
    if not precio_str:
        return None
    try:
        precio_limpio = precio_str.replace("Bs.", "").replace(" ", "").strip()
        if ',' in precio_limpio:
            if '.' in precio_limpio:
                partes = precio_limpio.split(',')
                parte_entera = partes[0].replace('.', '')
                precio_limpio = parte_entera + '.' + partes[1]
            else:
                precio_limpio = precio_limpio.replace(',', '.')
        else:
            if precio_limpio.count('.') > 1:
                partes = precio_limpio.split('.')
                parte_entera = ''.join(partes[:-1])
                parte_decimal = partes[-1]
                precio_limpio = parte_entera + '.' + parte_decimal
        return float(precio_limpio)
    except Exception as e:
        print(f"Error limpiando precio '{precio_str}': {e}")
        return None

def chrome_stealth():
    """Configura opciones de Chrome para evitar detección como bot"""
    opts = Options()
    if HEADLESS:
        opts.add_argument("--headless=new")
    for a in ["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
              "--window-size=1920,1080", "--log-level=3"]:
        opts.add_argument(a)
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option('useAutomationExtension', False)
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-web-security")
    opts.add_argument("--disable-features=VizDisplayCompositor")
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    if PROXY:
        opts.add_argument(f'--proxy-server={PROXY}')
    return opts

def retry(func, producto):
    """Implementa reintentos para operaciones frágiles"""
    for i in range(1, INTENTOS + 1):
        try:
            return func(producto)
        except Exception as e:
            print(f"[RETRY {i}/{INTENTOS}] {func.__name__} – {producto}: {e}")
            if i == INTENTOS:
                traceback.print_exc()
            else:
                time.sleep(RETRY_DELAY)
    return []

# ---------------  SCRAPER ESPECÍFICO PARA FARMA GO  ---------------
def scrap_farmago(producto):
    """Extrae productos de Farmago para el término de búsqueda dado"""
    url = URL_BASE.format(producto)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_stealth())
    try:
        driver.get(url)
        WebDriverWait(driver, 35).until(
            EC.presence_of_element_located((By.CLASS_NAME, "o_search_result_item"))
        )
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, "html.parser")
    except Exception as e:
        driver.save_screenshot(f"farmago_{producto}.png")
        raise e
    finally:
        driver.quit()
    
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filas = []
    
    # Diccionario de mapeo de términos a marcas (CASOS ESPECÍFICOS)
    marca_por_termino = {
        "biosa": "BIOSANO",
        "biosano": "BIOSANO",
        "butan": "Meyer",
        "meyer": "Meyer",
        "brolat": "MEYER",  # Para productos relacionados
        "ibutan": "Meyer",  # Variación común
        "brolat": "MEYER"   # Para productos relacionados
    }
    
    for card in soup.select("a.dropdown-item"):
        nombre_raw = card.select_one("div.h6.fw-bold.mb-0")
        precio_span = card.select_one("span.oe_currency_value")
        if not nombre_raw:
            continue
        texto = nombre_raw.get_text(strip=True)
        
        # --- extraer marca y limpiar nombre ---
        marca = None
        texto_limpio = texto.strip()
        
        # 1. Primero intentar extraer marca de paréntesis (tu lógica actual)
        if texto_limpio.endswith(")"):
            idx = texto_limpio.rfind("(")
            if idx != -1:
                marca = texto_limpio[idx+1:-1].strip()
                texto_limpio = texto_limpio[:idx].strip()
        
        # 2. Si no hay marca, buscar por términos clave en el nombre
        if not marca:
            texto_lower = texto_limpio.lower()
            
            # Caso especial para BIOSA/BIOSANO
            if "biosa" in texto_lower and "biosano" not in texto_lower:
                marca = "BIOSANO"
            
            # Caso especial para IBUTAN
            elif "butan" in texto_lower and "meyer" not in texto_lower:
                marca = "Meyer"
            
            # Búsqueda general usando el diccionario
            else:
                for termino, marca_asignar in marca_por_termino.items():
                    if termino in texto_lower:
                        marca = marca_asignar
                        break  # Encontramos una marca, no seguimos buscando
        
        # 3. CORRECCIÓN ADICIONAL: Normalizar la marca "Meyer" para que sea consistente
        if marca and "meyer" in marca.lower():
            marca = "Meyer"  # Estándar que usas en tus datos
        
        filas.append({
            "Fecha_Hora": fecha,
            "Origen": "FarmaGo",
            "Producto_Buscado": producto,
            "Marca": marca,
            "Nombre": texto_limpio,
            "Precio": limpiar_precio(f"Bs. {precio_span.text}" if precio_span else None)
        })
    
    # Eliminar duplicados
    seen = set()
    unicos = []
    for item in filas:
        clave = (item['Nombre'], item['Marca'])
        if clave not in seen:
            seen.add(clave)
            unicos.append(item)
    
    return unicos

# ---------------  FUNCIÓN PRINCIPAL  ---------------
def main():
    """Ejecuta el scraping para todos los productos definidos"""
    todos = []
    for prod in PRODUCTOS:
        print(f"🔍 Buscando '{prod}' en Farmago...")
        data = retry(scrap_farmago, prod)
        todos.extend(data)
        print(f"✅ {prod}: {len(data)} productos encontrados")
        time.sleep(5)  # Pausa entre búsquedas
    
    if not todos:
        print("❌ No se recuperó ningún producto.")
        return
    
    print("📊 Creando DataFrame...")
    df_nuevo = pd.DataFrame(todos).drop_duplicates(subset=["Nombre", "Marca"])
    
    # Manejo del archivo Excel
    if os.path.isfile(RUTA_EXCEL):
        print("📂 Leyendo Excel existente...")
        df_existente = pd.read_excel(RUTA_EXCEL)
        df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
    else:
        print("📂 Creando Excel nuevo...")
        df_final = df_nuevo
    
    print("💾 Guardando Excel...")
    df_final.to_excel(RUTA_EXCEL, index=False)
    print(f"✅ {len(df_nuevo)} registros agregados → {RUTA_EXCEL}")

# ---------------  EJECUCIÓN  ---------------
if __name__ == "__main__":
    main()