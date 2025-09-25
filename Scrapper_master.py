#scrapper_master.py
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
from collections import defaultdict, Counter
# ---------------  CONFIG  -------------
RUTA_EXCEL   = r"C:\Users\pcdel\OneDrive\Desktop\consolidado_farmacias.xlsx"
HEADLESS     = True
PRODUCTOS    = ["Diclofenac", "Paracetamol", "Ibuprofeno", "Loratadina"]
PROXY        = None  # Cambiar aquí si usas proxy
INTENTOS     = 2
RETRY_DELAY  = 10
BASE_URL_FARMASAS = "https://tienda.farmaciasaas.com"

# ----------------------------------------

# 🔍 Principios activos y marcas locales (backup)
PRINCIPIOS_ACTIVOS = [
    "diclofenac", "paracetamol", "ibuprofeno", "loratadina", "amoxicilina",
    "naproxeno", "aspirina", "cetirizina", "omeprazol", "metformina"
]

MARCAS_CONOCIDAS = [
    "mk", "genfar", "gsk", "panadol", "bago", "roemmers",  "raven", "drotaf", "elm", "ccm", "dlr", "clx", "sigvaris",
    "Oftalmi", "Genven", "Leti", "Calox", "Elmor", "Ponce y Benzo", "Pfizer", "CCM Farma", "Aless", "La Santé", "Dollder", "Meyer",
    "Adium", "Bioglass", "Bioquimica", "Biosano", "Valmorca", "Laboratorios Farma", "COFASA", "Siegfried", "FC Pharma", 
    "Laboratorios Vargas", "Biotech", "DAC 55", "Pharmetique Labs", "PlusAndex", "Buka", "Kimiceg", "Farmacias Unidas",
    "Biotechnologia GKV", "DistriLab", "Neo", "Quim-Far", "MediGen", "MedVal", "MegaLabs", "MVGA", "Ravel", "Remeny", "Scott Edil",
    "Drogueria Clínica", "Vitalis", "Vivax", "GeoLab", "DoroPharma", "GVS Pharma", "IPS", "KMPlus", "Laproff", "INVERSIONES GEAGAR 2021",
    "Farmacenter 24 La Lago", "H&M Medical"
]

# ---------------  MEJORA EN LA FUNCIÓN LIMPIAR_PRECIO  ---------------
def limpiar_precio(precio_str):
    if not precio_str:
        return None
    try:
        # Eliminar "Bs." y espacios
        precio_limpio = precio_str.replace("Bs.", "").replace(" ", "").strip()
        
        # Si tiene coma como separador decimal
        if ',' in precio_limpio:
            # Caso: "1.000,00" -> quitar puntos y convertir coma a punto
            if '.' in precio_limpio:
                partes = precio_limpio.split(',')
                parte_entera = partes[0].replace('.', '')
                precio_limpio = parte_entera + '.' + partes[1]
            else:
                # Caso: "100,50" -> convertir coma a punto
                precio_limpio = precio_limpio.replace(',', '.')
        else:
            # Caso con múltiples puntos como separadores de miles
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

    # Si termina en "PHARME", es Pharmetique Labs
    if nombre.endswith("pharme"):
        return "Pharmetique Labs"

    # Si termina en "H&M MEDICAL", lo extraemos
    if "h&m medical" in nombre:
        return "H&M Medical"

    # Búsqueda normal en MARCAS_CONOCIDAS
    for marca in MARCAS_CONOCIDAS:
        if marca.lower() in nombre:
            return marca  # ← ESTA LÍNEA FALTABA

    # Mapeo de correcciones específicas
    correcciones = {
        "biosa": "Biosano",
        # Agrega más correcciones aquí si es necesario
    }
    
    # Primero verificar correcciones específicas
    for key, value in correcciones.items():
        if key in nombre:
            return value
    
    # Lista expandida de marcas conocidas
    marcas_extendidas = MARCAS_CONOCIDAS + [
        "leti", "aless", "calox", "raven", "drotaf", "elm", "ccm", 
        "dlr", "clx", "sigvaris", "audace", "media", "biosano", "biotech"
    ]
    
    for marca in marcas_extendidas:
        if marca in nombre:
            return marca.upper()

    # Intentar extraer última palabra como marca
    palabras = nombre.split()
    if len(palabras) > 1:
        ultima = palabras[-1]
        if len(ultima) <= 6 and ultima.isalpha():
            return ultima.upper()

    return None

def limpiar_nombre(nombre):
    # Separar principios activos pegados
    nombre = re.sub(r'(DICLOFENAC|SODICO|POTASICO|IBUPROFENO|LORATADINA|PARACETAMOL)(\d+)', r'\1 \2', nombre)
    nombre = re.sub(r'(DICLOFENAC)(SODICO|POTASICO)', r'\1 \2', nombre)
    nombre = re.sub(r'(LORATADINA)(\d+)', r'\1 \2', nombre)
    nombre = re.sub(r'(IBUPROFENO)(\d+)', r'\1 \2', nombre)
    nombre = re.sub(r'(PARACETAMOL)(\d+)', r'\1 \2', nombre)
    return nombre

def scrap_farmatodo(producto):
    url = f"https://www.farmatodo.com.ve/buscar?product={producto}&departamento=Todos&filtros="
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_stealth())
    try:
        driver.get(url)
        time.sleep(8)
        soup = BeautifulSoup(driver.page_source, "html.parser")
    except Exception as e:
        driver.save_screenshot(f"Farmatodo_{producto}.png")
        raise e
    finally:
        driver.quit()

    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filas = []

    for card in soup.find_all("div", class_=lambda x: x and "card-ftd" in x.split()):
        marca = card.find("p", class_="text-brand")
        nombre = card.find("p", class_="text-title")
        if not nombre:
            continue

        # ✅ Detectar si está no disponible
        no_disponible = card.select_one("div.offer-description.not-available")
        if no_disponible:
            precio_limpio = None
        else:
            precio = card.find("span", class_="price__text-price")
            precio_limpio = limpiar_precio(precio.get_text(strip=True) if precio else None)

        filas.append({
            "Fecha_Hora": fecha,
            "Origen": "Farmatodo",
            "Producto_Buscado": producto,
            "Marca": marca.get_text(strip=True) if marca else None,
            "Nombre": nombre.get_text(strip=True),
            "Precio": precio_limpio
        })

    # Eliminar duplicados por (Nombre, Marca)
    seen = set()
    unicos = []
    for item in filas:
        clave = (item['Nombre'], item['Marca'])
        if clave not in seen:
            seen.add(clave)
            unicos.append(item)

    return unicos

#############################################################################################
###################################### FARMACIAS GO  ########################################
#############################################################################################
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
        driver.save_screenshot(f"FarmaGo_{producto}.png")
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
            "Origen": "FarmaGo",
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

def corregir_marcas_especificas(df):
    """
    Corrige marcas específicas basándose en patrones conocidos
    """
    correcciones = {
        # Patrón: (origen, nombre contiene, marca actual) -> nueva marca
        ("FarmaGo", "biosa", "ALESS"): "BIOSANO",
        # Agrega más correcciones aquí según sea necesario
    }
    
    for idx, row in df.iterrows():
        nombre = row['Nombre'].lower()
        origen = row['Origen'].lower()
        marca_actual = row['Marca']
        
        for (patron_origen, patron_nombre, patron_marca), nueva_marca in correcciones.items():
            if (patron_origen in origen and 
                patron_nombre in nombre and 
                marca_actual == patron_marca):
                df.at[idx, 'Marca'] = nueva_marca
                print(f"Corregida marca: {marca_actual} -> {nueva_marca} para {nombre}")
    
    return df

# ---------------  FUNCIÓN PARA COMPLETAR MARCAS FALTANTES  ---------------
def completar_marcas_faltantes(productos):
    """
    Completa las marcas faltantes en productos basándose en productos similares
    del mismo origen que tengan el mismo nombre comercial.
    """
    # Agrupar productos por origen y nombre comercial
    productos_por_origen = defaultdict(list)
    for producto in productos:
        productos_por_origen[producto['Origen']].append(producto)
    
    # Para cada origen, completar marcas faltantes
    for origen, productos_origen in productos_por_origen.items():
        # Crear un diccionario de marcas por nombre comercial
        marcas_por_nombre = defaultdict(list)
        
        # Primera pasada: recolectar marcas conocidas por nombre comercial
        for producto in productos_origen:
            if producto['Marca']:
                # Extraer nombre comercial (primera palabra o palabras clave)
                nombre = producto['Nombre'].lower()
                nombre_comercial = extraer_nombre_comercial(nombre)
                if nombre_comercial:
                    marcas_por_nombre[nombre_comercial].append(producto['Marca'])
        
        # Segunda pasada: asignar marcas a productos sin marca
        for producto in productos_origen:
            if not producto['Marca']:
                nombre = producto['Nombre'].lower()
                nombre_comercial = extraer_nombre_comercial(nombre)
                
                if nombre_comercial and nombre_comercial in marcas_por_nombre:
                    # Usar la marca más común para este nombre comercial
                    marcas = marcas_por_nombre[nombre_comercial]
                    contador = Counter(marcas)
                    marca_mas_comun = contador.most_common(1)[0][0]
                    producto['Marca'] = marca_mas_comun
                    print(f"Asignada marca '{marca_mas_comun}' a '{producto['Nombre']}'")
    
    return productos

def extraer_nombre_comercial(nombre):
    """
    Extrae el nombre comercial de un producto basándose en patrones comunes.
    """
    # Lista de palabras a excluir (principios activos, formas farmacéuticas, etc.)
    exclusiones = PRINCIPIOS_ACTIVOS + [
        'tabletas', 'capsulas', 'comprimidos', 'crema', 'gel', 'ungüento',
        'suspension', 'jarabe', 'supositorios', 'inyectable', 'ampollas',
        'mg', 'g', 'ml', 'x', 'de'
    ]
    
    # Buscar la primera palabra que parece un nombre comercial
    palabras = nombre.split()
    for palabra in palabras:
        # Excluir palabras muy cortas o numéricas
        if (len(palabra) > 3 and 
            not any(c.isdigit() for c in palabra) and 
            palabra not in exclusiones):
            return palabra
    
    # Si no encontramos un nombre comercial claro, usar las primeras palabras
    if len(palabras) > 1:
        return palabras[0]
    
    return None



#############################################################################################
###################################### FARMACIAS SAAS #######################################
#############################################################################################
def extraer_precio_farmasas(card):
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

        # 1) Buscar el contenedor que tenga “Ahora”
        ahora = card.find(string=re.compile(r'\bAhora\b'))
        if ahora:
            # Subir al contenedor-precio que lo incluye
            contenedor = ahora.find_parent('div', class_='contenedor-precio')
            if contenedor:
                # Obtener todos los spans internos
                partes = [
                    span.get_text(strip=True)
                    for span in contenedor.select('span.precio, span.fraccion, span.mat-small')
                ]
                # Unir y limpiar
                texto = ''.join(partes)                      # ej: "Bs.442,24"
                match = re.search(r'Bs\.?\s*(\d+[.,]?\d*)', texto)
                if match:
                    precio = match.group(1).replace('.', '').replace(',', '.')
                    return f"Bs. {float(precio):.2f}"

        # 2) Fallback: método antiguo si no hay “Ahora”
        texto_completo = card.get_text()
        match = re.search(r'Bs\.\s*(\d+\.?\d*,?\d*)', texto_completo)
        if match:
            precio = match.group(1).replace('.', '').replace(',', '.')
            return f"Bs. {float(precio):.2f}"

    except Exception as e:
        print(f"Error extrayendo precio: {e}")

    return None

# ---------------  NUEVA FUNCIÓN PARA EXTRAER FABRICANTE  ---------------
def extraer_fabricante_farmasas(url_producto, driver):
    try:
        print(f"Visitando producto: {url_producto}")
        driver.get(url_producto)
        
        # Esperar a que cargue la información del producto
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "mat-card-content"))
        )
        
        # Esperar adicionalmente para contenido dinámico
        time.sleep(3)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Buscar la sección de fabricante - método más robusto
        fabricante = None
        
        # Intentar múltiples selectores para encontrar el fabricante
        selectores = [
            "div.fxlayout row fxlayoutalign.start end",  # Selector específico
            "span.titulo:-soup-contains('FABRICANTE')",  # Contiene texto FABRICANTE
            "span.titulo",  # Solo el título
            "div.mat-card-content div.fxlayout"  # Estructura general
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

# ---------------  SCRAPER MODIFICADO PARA FARMASIAS SAAS  ---------------
def scrap_farmasas(producto):
    url = f"{BASE_URL_FARMASAS}/buscar/{producto}/0"
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_stealth())
    
    try:
        driver.get(url)
        print(f"Buscando productos de: {producto}")
        # Esperar más tiempo para resultados
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
                enlace_completo = f"{BASE_URL_FARMASAS}{enlace_relativo}"
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
            "Marca": fabricante or marca_detectada,  # Usar fabricante o marca detectada
            "Nombre": nombre,
            "Precio": limpiar_precio(precio)
        })
        
        # Esperar entre solicitudes para no sobrecargar el servidor
        time.sleep(2)

    driver.quit()
    
    seen = set()
    unicos = []
    for item in filas:
        clave = (item['Nombre'], item['Marca'])
        if clave not in seen:
            seen.add(clave)
            unicos.append(item)
    
    print(f"Encontrados {len(unicos)} productos únicos de Farmacias Saas")
    return unicos

#############################################################################################
###################################### MAIN  ################################################
#############################################################################################
def main():
    todos = []
    for prod in PRODUCTOS:
        for nombre, func in (("Farmatodo", scrap_farmatodo),
                             ("FarmaGo", scrap_farmago),
                             ("Farmacias Saas", scrap_farmasas)):
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

    # 🔄 COMPLETAR MARCAS FALTANTES
    print("🔄 Completando marcas faltantes...")
    df_nuevo = df_nuevo.reset_index(drop=True)
    productos_list = df_nuevo.to_dict('records')
    productos_completados = completar_marcas_faltantes(productos_list)
    df_nuevo = pd.DataFrame(productos_completados)
    
    # 🔧 CORREGIR MARCAS ESPECÍFICAS
    print("🔧 Corrigiendo marcas específicas...")
    df_nuevo = corregir_marcas_especificas(df_nuevo)

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