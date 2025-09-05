# ---------------  MÓDULOS  ---------------
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import pandas as pd
import time, os, traceback, re
from datetime import datetime

# ---------------  CONFIG  ---------------
RUTA_EXCEL   = r"C:\Users\Especialista de Data\Documents\consolidado_farmacias.xlsx"
HEADLESS     = True
PRODUCTOS    = ["diclofenac", "paracetamol", "ibuprofeno", "loratadina"]
PROXY        = None  # Cambiar aquí si usas proxy
INTENTOS     = 2
RETRY_DELAY  = 10
# ----------------------------------------

# 🔍 Principios activos y marcas locales (backup)
PRINCIPIOS_ACTIVOS = [
    "diclofenac", "paracetamol", "ibuprofeno", "loratadina", "amoxicilina",
    "naproxeno", "aspirina", "cetirizina", "omeprazol", "metformina"
]

MARCAS_CONOCIDAS = [
    "aflamax", "diklason", "genven", "oftalmi", "mk", "genfar", "pfizer",
    "gsk", "panadol", "calox", "bago", "roemmers", "clofen"
]

def limpiar_precio(precio_str):
    if not precio_str:
        return None
    try:
        precio_limpio = precio_str.replace("Bs.", "").strip()
        if ',' in precio_limpio:
            precio_limpio = precio_limpio.replace('.', '').replace(',', '.')
        else:
            if precio_limpio.count('.') > 1:
                partes = precio_limpio.split('.')
                precio_limpio = ''.join(partes[:-1]) + '.' + partes[-1]
        return float(precio_limpio)
    except:
        return None

def chrome_stealth():
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

# ---------------  EXTRACCIÓN INTELIGENTE  ---------------
def extraer_claves(nombre):
    nombre = nombre.lower()
    principio = next((p for p in PRINCIPIOS_ACTIVOS if p in nombre), None)
    dosis = next((m.group(0).replace(" ", "") for m in re.finditer(r'(\d+)\s*mg|\b(\d+)\s*g\b|\b(\d+)\s*ml\b', nombre)), None)
    presentacion = next((m.group(0).replace(" ", "") for m in re.finditer(r'(\d+)\s*(tab|cap|soft|comp|grag|sob|jbe|susp)', nombre)), None)
    return principio, dosis, presentacion

def extraer_marca_desde_nombre(nombre):
    nombre = nombre.lower()
    return next((m for m in MARCAS_CONOCIDAS if m in nombre), None)

def asignar_sku_final(nombre, marca_col):
    principio, dosis, presentacion = extraer_claves(nombre)
    marca_detectada = extraer_marca_desde_nombre(nombre) or (marca_col.lower() if marca_col else None)
    if not principio:
        return f"SKU{hash(nombre) % 10000:04d}"
    return f"{principio}_{dosis or '0mg'}_{presentacion or '0tab'}_{marca_detectada or 'sinmarca'}"

# ---------------  SCRAPPERS  ---------------
def scrap_farmatodo(producto):
    url = f"https://www.farmatodo.com.ve/buscar?product={producto}&departamento=Todos&filtros="
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
        filas.append({"Fecha_Hora": fecha, "Origen": "farmatodo",
                      "Producto_Buscado": producto,
                      "Marca": marca.get_text(strip=True) if marca else None,
                      "Nombre": nombre.get_text(strip=True),
                      "Precio": limpiar_precio(precio.get_text(strip=True) if precio else None)})
    seen = set(); unicos = []
    for item in filas:
        clave = (item['Nombre'], item['Marca'])
        if clave not in seen:
            seen.add(clave); unicos.append(item)
    return unicos

def scrap_farmago(producto):
    url = f"https://www.farmago.com.ve/website/search?search={producto}&order=name+asc"
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

    for card in soup.select("a.dropdown-item"):
        nombre_raw = card.select_one("div.h6.fw-bold.mb-0")
        precio_span = card.select_one("span.oe_currency_value")
        if not nombre_raw:
            continue

        texto = nombre_raw.get_text(strip=True)

        # --- extraer marca y limpiar nombre ---
        marca = None
        if texto.endswith(")"):
            idx = texto.rfind("(")
            if idx != -1:
                marca = texto[idx+1:-1].strip()
                texto = texto[:idx].strip()

        filas.append({
            "Fecha_Hora": fecha,
            "Origen": "farmago",
            "Producto_Buscado": producto,
            "Marca": marca,
            "Nombre": texto,
            "Precio": limpiar_precio(f"Bs. {precio_span.text}" if precio_span else None)
        })

    seen = set(); unicos = []
    for item in filas:
        clave = (item['Nombre'], item['Marca'])
        if clave not in seen:
            seen.add(clave); unicos.append(item)
    return unicos

# ---------------  NUEVA FARMACIA: FARMAAAS  ---------------
def scrap_farmaaas(producto):
    url = f"https://tienda.farmaciasaas.com/buscar/{producto}/0"
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_stealth())
    try:
        driver.get(url)
        time.sleep(5)
        soup = BeautifulSoup(driver.page_source, "html.parser")
    except Exception as e:
        driver.save_screenshot(f"farmaaas_{producto}.png")
        raise e
    finally:
        driver.quit()

    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filas = []

    for card in soup.select("div.contenedor-informacion"):
        nombre = card.select_one("mat-card-title.titulo a")
        principio = card.select_one("mat-card-subtitle.subtitulo")
        precio_entero = card.select_one("span.precio")
        precio_frac = card.select_one("span.fraccion")

        if not nombre:
            continue

        texto_nombre = nombre.get_text(strip=True)
        texto_principio = principio.get_text(strip=True) if principio else ""
        precio_text = None
        if precio_entero and precio_frac:
            precio_text = f"Bs. {precio_entero.text.strip()},{precio_frac.text.strip()}"

        # 🔍 Buscar marca dentro del nombre
        marca_detectada = extraer_marca_desde_nombre(texto_nombre)

        filas.append({
            "Fecha_Hora": fecha,
            "Origen": "farmaaas",
            "Producto_Buscado": producto,
            "Marca": marca_detectada or None,
            "Nombre": texto_nombre,
            "Precio": limpiar_precio(precio_text)
        })

    seen = set(); unicos = []
    for item in filas:
        clave = (item['Nombre'], item['Marca'])
        if clave not in seen:
            seen.add(clave); unicos.append(item)
    return unicos

# ---------------  CONSOLIDADO + SKU  ---------------
def main():
    todos = []
    for prod in PRODUCTOS:
        for nombre, func in (("farmatodo", scrap_farmatodo),
                             ("farmago", scrap_farmago),
                             ("farmaaas", scrap_farmaaas)):
            data = retry(func, prod)
            todos.extend(data)
            print(f"[{nombre.upper()}] {prod}: {len(data)} productos")
        time.sleep(10)

    if not todos:
        print("❌ No se recuperó ningún producto.")
        return

    print("🔍 Creando DataFrame...")
    df_nuevo = pd.DataFrame(todos).drop_duplicates(subset=["Nombre", "Marca"])
    print(f"📊 DataFrame creado: {len(df_nuevo)} filas")

    print("🔍 Asignando SKU...")
    df_nuevo['SKU'] = df_nuevo.apply(lambda row: asignar_sku_final(row['Nombre'], row['Marca']), axis=1)
    print("✅ SKU asignado")

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