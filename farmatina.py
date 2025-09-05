from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from bs4 import BeautifulSoup
import time
import csv
from datetime import datetime

# Ruta al chromedriver
service = Service(r"C:\Users\sisa4\Downloads\chromedriver-win64\chromedriver-win64\chromedriver.exe")

options = webdriver.ChromeOptions()
options.add_argument("--headless")
driver = webdriver.Chrome(service=service, options=options)

# Definir el término de búsqueda (esto es lo que quieres como nombre_propducto)
termino_busqueda = "Diclofenac"
url = f"https://farmatina.com/?s={termino_busqueda}&post_type=product&dgwt_wcas=1"
driver.get(url)
time.sleep(5)

# Cargar todos los productos haciendo clic en "CARGA MÁS..."
max_attempts = 5  # Evitar bucle infinito
attempts = 0

while attempts < max_attempts:
    try:
        # Buscar el botón EN CADA ITERACIÓN (esto es crucial)
        load_more_button = driver.find_element(By.CSS_SELECTOR, "a.nasa-archive-loadmore")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
        time.sleep(1)
        
        # Intentar hacer clic
        driver.execute_script("arguments[0].click();", load_more_button)
        
        # Esperar a que se carguen nuevos productos
        time.sleep(3)
        
        # Verificar si realmente se cargaron más productos
        current_count = len(driver.find_elements(By.CSS_SELECTOR, "li.product-warp-item"))
        print(f"Productos después de cargar más: {current_count}")
        
        attempts = 0  # Reiniciar contador si fue exitoso
    except (NoSuchElementException, StaleElementReferenceException):
        attempts += 1
        print(f"Intento {attempts} de {max_attempts} - No se encontró el botón 'CARGA MÁS...'")
        time.sleep(1)
        
        # Si no hay más intentos, salir del bucle
        if attempts >= max_attempts:
            print("No se encontró más el botón 'CARGA MÁS...' o se alcanzó el límite de intentos")
            break

# Obtener HTML final
html = driver.page_source
soup = BeautifulSoup(html, "html.parser")

# Extraer productos
productos = soup.find_all("li", class_="product-warp-item")

print(f"Total de productos encontrados: {len(productos)}")

# Lista de marcas conocidas (puedes ampliarla con el tiempo)
marcas_conocidas = {
    "Coaspharma", "Kmplus", "Genven", "Distrilab", "Calox", "La Sante", "Spefar", "DAC55",
    "Megalabs", "Dollder", "Siegfried", "Cofasa", "Lab Farma", "Drotafarma", "Oftalmi",
    "Valmorca", "Leti", "Biotech", "Vivax", "Elmor", "Ponce", "Roemmers", "Oftamil",
    "Pharmetique", "Novartis", "Bioglass", "Tiares", "Plusandex", "Dac55", "Bioglass",
    "Voltaren"  
}

def extraer_marca(nombre):
    nombre_limpio = nombre.strip()
    palabras = nombre_limpio.split()
    for palabra in palabras:
        if palabra in marcas_conocidas:
            return palabra
    return "Desconocida"

# --- Extraer y mostrar productos con marca ---
resultados = []

# Obtener la fecha actual en formato YYYY-MM-DD
fecha_extraccion = datetime.now().strftime("%Y-%m-%d")

for producto in productos:
    nombre = producto.find("a", class_="woocommerce-loop-product__title")
    precio = producto.find("span", class_="woocommerce-Price-amount")

    if nombre and precio:
        nombre_texto = nombre.text.strip()
        precio_texto = precio.text.strip()
        marca = extraer_marca(nombre_texto)

        resultados.append({
            "Producto": nombre_texto,
            "Precio": precio_texto,
            "Marca": marca,
            "Fecha_Extraccion": fecha_extraccion,
            "nombre_propducto": termino_busqueda  # Nuevo campo solicitado
        })

# --- Mostrar resultados ---
for r in resultados:
    print(f"Producto: {r['Producto']}")
    print(f"Precio: {r['Precio']}")
    print(f"Marca: {r['Marca']}")
    print(f"Fecha de Extracción: {r['Fecha_Extraccion']}")
    print(f"Término de búsqueda: {r['nombre_propducto']}")
    print("-" * 40)

# --- Guardar resultados en CSV ---
csv_path = r"C:\Users\sisa4\Desktop\productos_farmatina.csv"

with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
    fieldnames = ['Producto', 'Precio', 'Marca', 'Fecha_Extraccion', 'nombre_propducto']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    
    # Escribir el encabezado
    writer.writeheader()
    
    # Escribir los datos
    for r in resultados:
        writer.writerow(r)

print(f"\nResultados guardados exitosamente en: {csv_path}")
print(f"Total de productos guardados: {len(resultados)}")
print(f"Todos los productos están relacionados con el término de búsqueda: {termino_busqueda}")

driver.quit()