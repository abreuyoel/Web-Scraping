# farmatodo_scraper.py
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

# Configuración específica para Farmatodo
RUTA_EXCEL = r"C:\Users\sisa4\Desktop\consolidado_farmatodo.xlsx"
HEADLESS = True
PRODUCTOS = ["Diclofenac", "Paracetamol", "Ibuprofeno", "Loratadina"]
PROXY = None
INTENTOS = 2
RETRY_DELAY = 10
URL_BASE = "https://www.farmatodo.com.ve/buscar?product={}&departamento=Todos&filtros="

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

# ---------------  SCRAPER ESPECÍFICO PARA FARMATODO  ---------------
def scrap_farmatodo(producto):
    """Extrae productos de Farmatodo para el término de búsqueda dado"""
    url = URL_BASE.format(producto)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_stealth())
    try:
        driver.get(url)
        time.sleep(8)
        soup = BeautifulSoup(driver.page_source, "html.parser")
    except Exception as e:
        driver.save_screenshot(f"farmatodo_{producto}.png")
        raise e
    finally:
        driver.quit()
    
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filas = []
    for card in soup.find_all("div", class_=lambda x: x and "card-ftd" in x.split()):
        marca = card.find("p", class_="text-brand")
        nombre = card.find("p", class_="text-title")
        precio = card.find("span", class_="price__text-price")
        if not nombre:
            continue
        filas.append({
            "Fecha_Hora": fecha,
            "Origen": "farmatodo",
            "Producto_Buscado": producto,
            "Marca": marca.get_text(strip=True) if marca else None,
            "Nombre": nombre.get_text(strip=True),
            "Precio": limpiar_precio(precio.get_text(strip=True) if precio else None)
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
        print(f"🔍 Buscando '{prod}' en Farmatodo...")
        data = retry(scrap_farmatodo, prod)
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