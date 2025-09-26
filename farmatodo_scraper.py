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
RUTA_EXCEL = os.path.join(os.getcwd(), "consolidado_farmatodo.xlsx")
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
        print(f"⏳ Cargando página para {producto}...")
        
        # Esperar a que se cargue el contenedor de productos
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.cont-group-view"))
        )
        
        # Variable para controlar si hay más productos para cargar
        intentos_maximos = 10
        intentos = 0
        productos_anteriores = 0
        boton_cargando = False
        
        while intentos < intentos_maximos:
            try:
                # Obtener el número actual de productos
                productos_actuales = len(driver.find_elements(By.CSS_SELECTOR, "div.card-ftd"))
                print(f"📦 Productos encontrados: {productos_actuales}")
                
                # Si no hay productos, salir
                if productos_actuales == 0:
                    print("⚠️ No se encontraron productos en la página")
                    break
                
                # Si no hay cambio en el número de productos, esperar un poco más
                # por si está en medio de una carga
                if productos_actuales == productos_anteriores and not boton_cargando:
                    if intentos > 2:  # Dar un par de intentos antes de rendirse
                        print("🔍 No se están cargando más productos, finalizando...")
                        break
                    time.sleep(2)
                    intentos += 1
                    continue
                
                productos_anteriores = productos_actuales
                
                try:
                    # Intentar encontrar el botón "Cargar más"
                    load_more_button = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.ID, "group-view-load-more"))
                    )
                    
                    # Verificar si el botón está visible
                    if load_more_button.is_displayed():
                        # Verificar si el botón está habilitado
                        if not load_more_button.get_attribute("disabled"):
                            print("🔄 Botón 'Cargar más' encontrado y habilitado")
                            boton_cargando = True
                            
                            # Desplazarse hasta el botón
                            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", load_more_button)
                            time.sleep(1)
                            
                            # Hacer clic en el botón usando JavaScript
                            driver.execute_script("arguments[0].click();", load_more_button)
                            print(f"✅ Clic #{intentos + 1} en 'Cargar más'")
                            intentos += 1
                            
                            # Esperar a que carguen los nuevos productos
                            time.sleep(3)
                        else:
                            print("ℹ️ Botón 'Cargar más' encontrado pero está deshabilitado")
                            boton_cargando = False
                            # Dar un momento adicional para ver si hay carga automática
                            time.sleep(2)
                            continue
                    else:
                        print("ℹ️ Botón 'Cargar más' no visible")
                        boton_cargando = False
                except Exception as e:
                    print(f"🔍 No se encontró el botón 'Cargar más' (posiblemente ya no hay más productos): {str(e)}")
                    boton_cargando = False
                    # Esperar un momento para ver si hay carga automática
                    time.sleep(2)
                
                # Verificar si hay nuevos productos
                nuevos_productos = len(driver.find_elements(By.CSS_SELECTOR, "div.card-ftd"))
                if nuevos_productos > productos_actuales:
                    print(f"✨ Se cargaron {nuevos_productos - productos_actuales} nuevos productos")
                    productos_anteriores = nuevos_productos
                elif intentos > 0 and nuevos_productos == productos_actuales:
                    print("🔍 No se cargaron nuevos productos después del clic")
                    intentos += 1
            
            except Exception as e:
                print(f"⚠️ Error durante el proceso de carga: {str(e)}")
                break
        
        # Esperar un momento adicional para que se carguen los últimos productos
        time.sleep(3)
        
        # Obtener el HTML después de cargar todos los productos
        soup = BeautifulSoup(driver.page_source, "html.parser")
        print(f"✅ HTML obtenido con {len(soup.find_all('div', class_='card-ftd'))} tarjetas de producto")
    except Exception as e:
        driver.save_screenshot(f"farmatodo_{producto}_error.png")
        raise e
    finally:
        driver.quit()
    
    # Procesar los productos
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
    
    # Eliminar duplicados (mejorada para manejar casos específicos)
    seen = {}
    unicos = []
    for item in filas:
        # Crear una clave única más flexible
        clave_nombre = item['Nombre'].lower().replace(" ", "").replace("-", "").replace(",", "")
        clave_marca = item['Marca'].lower().replace(" ", "").replace("-", "").replace(",", "") if item['Marca'] else "sinmarca"
        clave = f"{clave_nombre}_{clave_marca}"
        
        # Si es la primera vez que vemos esta clave o si el precio es diferente, lo agregamos
        if clave not in seen or seen[clave] != item['Precio']:
            seen[clave] = item['Precio']
            unicos.append(item)
    
    print(f"🔍 Encontrados {len(unicos)} productos únicos después de cargar todos los resultados")
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