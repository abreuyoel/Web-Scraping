# farmasas_scraper.py
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
import re

# Configuración específica para Farmacias SAAS
RUTA_EXCEL = r"C:\Users\sisa4\Desktop\consolidado_farmasas.xlsx"
HEADLESS = True
PRODUCTOS = ["Diclofenac", "Paracetamol", "Ibuprofeno", "Loratadina"]
PROXY = None
INTENTOS = 2
RETRY_DELAY = 10
BASE_URL = "https://tienda.farmaciasaas.com"

# ---------------  LISTAS DE APOYO  ---------------
PRINCIPIOS_ACTIVOS = [
    "diclofenac", "paracetamol", "ibuprofeno", "loratadina", "amoxicilina",
    "naproxeno", "aspirina", "cetirizina", "omeprazol", "metformina"
]
MARCAS_CONOCIDAS = [
    "mk", "genfar", "gsk", "panadol", "bago", "roemmers", "clofen",  "raven", "drotaf", "elm", "ccm", "dlr", "clx", "sigvaris",
    "Oftalmi", "Genven", "Leti", "Calox", "Elmor", "Ponce y Benzo", "Pfizer", "CCM Farma", "Aless", "La Santé", "Dollder", "Meyer",
    "Adium", "Bioglass", "Bioquimica", "Biosano", "Valmorca", "Laboratorios Farma", "COFASA", "Siegfried", "FC Pharma", 
    "Laboratorios Vargas", "Biotech", "DAC 55", "Pharmetique Labs", "PlusAndex", "Buka", "Kimiceg", "Farmacias Unidas",
    "Biotechnologia GKV", "DistriLab", "Neo", "Quim-Far", "MediGen", "MedVal", "MegaLabs", "MVGA", "Ravel", "Remeny", "Scott Edil",
    "Drogueria Clínica", "Vitalis", "Vivax", "GeoLab", "DoroPharma", "GVS Pharma", "IPS", "KMPlus", "Laproff", "INVERSIONES GEAGAR 2021",
    "Farmacenter 24 La Lago"
]

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

def extraer_precio_farmasas(card):
    """Extrae el precio de un producto de Farmacias SAAS"""
    try:
        entero = card.select_one("span.mat-card-title")
        fraccion = card.select_one("span.mat-small")
        if entero and fraccion:
            entero_text = entero.get_text(strip=True).replace("Bs.", "").strip()
            fraccion_text = fraccion.get_text(strip=True).replace(",", ".")
            return f"Bs. {entero_text}.{fraccion_text}"
        elif entero:
            return f"Bs. {entero.get_text(strip=True).replace('Bs.', '').strip()}"
    except Exception as e:
        print(f"Error extrayendo precio: {e}")
    return None

def extraer_fabricante_farmasas(url_producto, driver):
    """Extrae el fabricante de un producto específico de Farmacias SAAS"""
    try:
        print(f"Visitando producto: {url_producto}")
        driver.get(url_producto)
        # Esperar a que cargue la información del producto
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "mat-card-content"))
        )
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Buscar la sección de fabricante
        fabricante = None
        # Intentar múltiples selectores para encontrar el fabricante
        selectores = [
            "div.fxlayout row fxlayoutalign.start end",
            "span.titulo:-soup-contains('FABRICANTE')",
            "span.titulo",
            "div.mat-card-content div.fxlayout"
        ]
        for selector in selectores:
            try:
                elementos = soup.select(selector)
                for elem in elementos:
                    texto = elem.get_text(strip=True)
                    if "FABRICANTE" in texto:
                        # Buscar el elemento hermano o siguiente que contenga el valor
                        padre = elem.parent
                        if padre:
                            textos_span = padre.find_all("span", class_="texto")
                            if textos_span and len(textos_span) > 1:
                                fabricante = textos_span[1].get_text(strip=True)
                                break
                        # Alternative: buscar siguiente elemento con clase "texto"
                        siguiente = elem.find_next("span", class_="texto")
                        if siguiente:
                            fabricante = siguiente.get_text(strip=True)
                            break
            except:
                continue
            if fabricante:
                break
        
        # Si no encontramos con selectores CSS, buscar por texto
        if not fabricante:
            for div in soup.find_all("div", class_=lambda x: x and "fxlayout" in str(x)):
                spans = div.find_all("span")
                for i, span in enumerate(spans):
                    if "FABRICANTE" in span.get_text():
                        if i+1 < len(spans) and "texto" in spans[i+1].get("class", []):
                            fabricante = spans[i+1].get_text(strip=True)
                            break
                if fabricante:
                    break
        
        print(f"Fabricante encontrado: {fabricante}")
        return fabricante
    except Exception as e:
        print(f"Error extrayendo fabricante de {url_producto}: {str(e)}")
        return None

def extraer_marca_desde_nombre(nombre):
    """Extrae la marca desde el nombre del producto"""
    nombre = nombre.lower()
    # Si termina en "PHARME", es Pharmetique Labs
    if nombre.endswith("pharme"):
        return "Pharmetique Labs"
    # Si termina en "H&M MEDICAL", lo extraemos
    if "h&m medical" in nombre:
        return "H&M Medical"
    # Búsqueda normal en MARCAS_CONOCIDAS
    for marca in MARCAS_CONOCIDAS:
        if marca.lower() in nombre:
            return marca.upper()
    # Intentar extraer última palabra como marca
    palabras = nombre.split()
    if len(palabras) > 1:
        ultima = palabras[-1]
        if len(ultima) <= 6 and ultima.isalpha():
            return ultima.upper()
    return None

# ---------------  SCRAPER ESPECÍFICO PARA FARMACIAS SAAS  ---------------
def scrap_farmasas(producto):
    """Extrae productos de Farmacias SAAS para el término de búsqueda dado"""
    url = f"{BASE_URL}/buscar/{producto}/0"
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_stealth())
    try:
        driver.get(url)
        print(f"Buscando productos de: {producto}")
        time.sleep(10)
        soup = BeautifulSoup(driver.page_source, "html.parser")
    except Exception as e:
        driver.save_screenshot(f"farmasas_{producto}.png")
        raise e
    
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filas = []
    enlaces_productos = []
    
    # Primero recopilar todos los enlaces de productos
    contenedores = soup.select("div.contenedor-informacion")
    print(f"Encontrados {len(contenedores)} contenedores de productos")
    
    for card in contenedores:
        try:
            nombre_elem = card.select_one("mat-card-title.titulo a")
            if not nombre_elem:
                continue
            texto_nombre = nombre_elem.get_text(strip=True)
            # Extraer precio con la función mejorada
            precio_text = extraer_precio_farmasas(card)
            print(f"Precio extraído para {texto_nombre}: {precio_text}")
            # Guardar el enlace para visitar después
            enlace_relativo = nombre_elem.get('href')
            if enlace_relativo:
                enlace_completo = f"{BASE_URL}{enlace_relativo}"
                enlaces_productos.append((texto_nombre, precio_text, enlace_completo))
                print(f"Producto añadido: {texto_nombre}")
        except Exception as e:
            print(f"Error procesando tarjeta de producto: {e}")
            continue
    
    print(f"Total de enlaces a visitar: {len(enlaces_productos)}")
    
    # Ahora visitar cada producto para obtener el fabricante
    for i, (nombre, precio, enlace) in enumerate(enlaces_productos):
        print(f"Procesando producto {i+1}/{len(enlaces_productos)}: {nombre}")
        fabricante = extraer_fabricante_farmasas(enlace, driver)
        # Si no encontramos fabricante, intentar extraer marca del nombre
        marca_detectada = None
        if not fabricante:
            marca_detectada = extraer_marca_desde_nombre(nombre)
            print(f"Usando marca detectada del nombre: {marca_detectada}")
        
        filas.append({
            "Fecha_Hora": fecha,
            "Origen": "Farmacias SAAS",
            "Producto_Buscado": producto,
            "Marca": fabricante or marca_detectada,
            "Nombre": nombre,
            "Precio": limpiar_precio(precio)
        })
        
        # Esperar entre solicitudes para no sobrecargar el servidor
        time.sleep(2)
    
    driver.quit()
    
    # Eliminar duplicados
    seen = set()
    unicos = []
    for item in filas:
        clave = (item['Nombre'], item['Marca'])
        if clave not in seen:
            seen.add(clave)
            unicos.append(item)
    
    print(f"Encontrados {len(unicos)} productos únicos de Farmacias Saas")
    return unicos

# ---------------  FUNCIÓN PRINCIPAL  ---------------
def main():
    """Ejecuta el scraping para todos los productos definidos"""
    todos = []
    for prod in PRODUCTOS:
        print(f"🔍 Buscando '{prod}' en Farmacias SAAS...")
        data = retry(scrap_farmasas, prod)
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