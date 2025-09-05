from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
import re
from datetime import datetime

# ---------- CONFIG ----------
PRODUCTOS = ["Diclofenac", "Paracetamol", "Ibuprofeno", "Loratadina"]
RUTA_EXCEL = r"C:\Users\Especialista de Data\Documents\productos_farmatodo.xlsx"
HEADLESS = True
# ----------------------------

def limpiar_precio(precio_str):
    if not precio_str:
        return None
    try:
        # Eliminar "Bs." y espacios
        precio_limpio = precio_str.replace("Bs.", "").strip()

        # Si tiene coma, es separador decimal -> eliminar puntos antes
        if ',' in precio_limpio:
            # Eliminar todos los puntos (miles)
            precio_limpio = precio_limpio.replace('.', '')
            # Reemplazar coma por punto decimal
            precio_limpio = precio_limpio.replace(',', '.')
        else:
            # Si no tiene coma, y tiene puntos, asumir que el último punto es decimal
            if precio_limpio.count('.') == 1:
                # Solo un punto -> ya es decimal
                pass
            elif precio_limpio.count('.') > 1:
                # Varios puntos: eliminar todos menos el último
                partes = precio_limpio.split('.')
                precio_limpio = ''.join(partes[:-1]) + '.' + partes[-1]

        return float(precio_limpio)
    except:
        return None


chrome_opts = Options()
if HEADLESS:
    chrome_opts.add_argument("--headless")
chrome_opts.add_argument("--disable-gpu")
chrome_opts.add_argument("--no-sandbox")
chrome_opts.add_argument("--disable-dev-shm-usage")
chrome_opts.add_argument("--window-size=1920,1080")
chrome_opts.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")

all_products = []

for producto in PRODUCTOS:
    print(f"🔍 Buscando: {producto}")
    url = f"https://www.farmatodo.com.ve/buscar?product={producto}&departamento=Todos&filtros="

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_opts)
    driver.get(url)
    time.sleep(6)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for card in soup.find_all("div", class_="card-ftd add-information"):
        marca = card.find("p", class_="text-brand")
        nombre = card.find("p", class_="text-title")
        precio = card.find("span", class_="price__text-price")
        if not nombre:
            continue
        all_products.append({
            "Fecha_Hora": fecha_hora,
            "Producto_Buscado": producto,
            "Marca": marca.get_text(strip=True) if marca else None,
            "Nombre": nombre.get_text(strip=True),
            "Precio": limpiar_precio(precio.get_text(strip=True) if precio else None)
        })

# ---------- GUARDAR / ANEXAR EXCEL ----------
if all_products:
    df_nuevo = pd.DataFrame(all_products)

    if os.path.isfile(RUTA_EXCEL):
        df_existente = pd.read_excel(RUTA_EXCEL)
        df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
    else:
        df_final = df_nuevo

    df_final.to_excel(RUTA_EXCEL, index=False)
    print(f"✅ {len(df_nuevo)} productos agregados a {RUTA_EXCEL}")
else:
    print("❌ No se encontraron productos.")