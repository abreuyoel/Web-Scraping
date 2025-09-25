#farmadon-ws.py
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import os
import re

def scrape_farmadon_full():
    # Lista de productos a buscar (incluyendo diclofenac potásico)
    PRODUCTOS = ["Paracetamol", "Ibuprofeno", "Loratadina", "Diclofenac Potasico"]
    
    # Configurar opciones de Chrome
    chrome_options = Options()
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Iniciar el navegador
    driver = webdriver.Chrome(options=chrome_options)
    all_products = []
    
    try:
        for termino_busqueda in PRODUCTOS:
            print(f"\n=== Buscando productos para: {termino_busqueda} ===")
            
            # Formatear término de búsqueda para URL
            termino_formateado = termino_busqueda.replace(" ", "+")
            base_url = f"https://www.farmadon.com.ve/?s={termino_formateado}&post_type=product&dgwt_wcas=1"
            
            print("Accediendo a la página de búsqueda...")
            driver.get(base_url)
            
            # Esperar a que cargue la página
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "section.product, .products, .woocommerce-pagination, .product, .product-grid-item"))
                )
                print("Página principal cargada")
            except:
                print("No se encontraron elementos products o paginación, continuando...")
            
            # Intentar hacer clic en "Cargar más" si existe
            try:
                load_more_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".load-more, .btn-load-more, #load-more, button.load-more"))
                )
                load_more_button.click()
                print("Se hizo clic en el botón 'Cargar más'")
                time.sleep(3)
            except:
                print("No se encontró botón 'Cargar más'")
            
            # Manejar infinite scroll con más intentos
            print("Iniciando scroll infinito para cargar todos los productos...")
            last_height = driver.execute_script("return document.body.scrollHeight")
            scroll_attempts = 0
            max_scroll_attempts = 20  # Aumentamos a 20 intentos
            no_new_content_count = 0
            max_no_new_content = 5  # Aumentamos a 5 intentos sin contenido nuevo
            
            while scroll_attempts < max_scroll_attempts:
                # Hacer scroll hasta el final de la página
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                # Esperar a que carguen nuevos productos (más tiempo)
                time.sleep(4)
                
                # Calcular nueva altura de la página
                new_height = driver.execute_script("return document.body.scrollHeight")
                
                # Verificar si se cargó nuevo contenido
                if new_height == last_height:
                    no_new_content_count += 1
                    print(f"No nuevo contenido ({no_new_content_count}/{max_no_new_content})")
                else:
                    no_new_content_count = 0
                    print(f"Nuevo contenido detectado. Nueva altura: {new_height}px")
                
                # Si no hay nuevo contenido después de varios intentos, terminar
                if no_new_content_count >= max_no_new_content:
                    print("No se detectó nuevo contenido después de varios intentos, finalizando scroll.")
                    break
                    
                last_height = new_height
                scroll_attempts += 1
                print(f"Intento de scroll {scroll_attempts}/{max_scroll_attempts}. Altura de la página: {new_height}px")
            
            # Intentar hacer clic en "Cargar más" nuevamente después del scroll
            try:
                load_more_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".load-more, .btn-load-more, #load-more, button.load-more"))
                )
                load_more_button.click()
                print("Se hizo clic en el botón 'Cargar más' después del scroll")
                time.sleep(3)
                
                # Hacer scroll adicional después de cargar más
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)
            except:
                print("No se encontró botón 'Cargar más' después del scroll")
            
            # Extraer productos después del scroll
            soup = BeautifulSoup(driver.page_source, "html.parser")
            
            # Buscar productos con varios selectores posibles
            product_selectors = [
                "section.product",
                "li.product",
                "div.product",
                ".product-grid-item",
                ".product-item",
                ".product-inner",
                ".woocommerce-loop-product__link",
                ".product-wrapper"
            ]
            
            product_sections = []
            for selector in product_selectors:
                elements = soup.select(selector)
                if elements:
                    product_sections.extend(elements)
                    print(f"Encontrados {len(elements)} productos con selector: {selector}")
            
            # Si no encontramos productos, intentar una búsqueda más amplia
            if not product_sections:
                print("No se encontraron productos con selectores específicos, intentando búsqueda amplia...")
                # Buscar cualquier elemento que pueda contener un producto
                possible_containers = soup.select(".col, .item, .box, .card, .product-box")
                for container in possible_containers:
                    # Verificar si el contenedor tiene elementos que sugieran que es un producto
                    has_name = container.find(["h2", "h3", "h4"], class_=re.compile("title|name|product", re.I))
                    has_price = container.find(class_=re.compile("price|amount", re.I))
                    if has_name and has_price:
                        product_sections.append(container)
                        print("Producto encontrado mediante búsqueda amplia")
            
            # Eliminar duplicados (por si un elemento coincide con múltiples selectores)
            seen_ids = set()
            unique_products = []
            for product in product_sections:
                product_id = str(product)
                if product_id not in seen_ids:
                    seen_ids.add(product_id)
                    unique_products.append(product)
            
            product_sections = unique_products
            
            print(f"Productos únicos encontrados para {termino_busqueda}: {len(product_sections)}")
            
            for product in product_sections:
                # Extraer nombre del producto
                nombre = "Nombre no encontrado"
                nombre_selectors = [
                    "h3.heading-title", 
                    "h3.product-name", 
                    "h2", 
                    "h3", 
                    "h4",
                    ".product-title",
                    ".product-name a",
                    "a h3",
                    ".title",
                    ".name",
                    "h2.woocommerce-loop-product__title"
                ]
                
                for selector in nombre_selectors:
                    try:
                        nombre_tag = product.select_one(selector)
                        if nombre_tag and nombre_tag.get_text(strip=True):
                            nombre = nombre_tag.get_text(strip=True)
                            break
                    except:
                        continue
                
                # Si aún no encontramos el nombre, buscar en enlaces
                if nombre == "Nombre no encontrado":
                    a_tags = product.find_all("a")
                    for a_tag in a_tags:
                        if a_tag.get_text(strip=True) and len(a_tag.get_text(strip=True)) > 5:
                            nombre = a_tag.get_text(strip=True)
                            break
                
                # Extraer precio
                precio = "Precio no encontrado"
                try:
                    # Método 1: Buscar precio en <ins> (precio con descuento)
                    price_tag = product.find("ins")
                    if price_tag:
                        price_amount = price_tag.find(["span", "p", "bdi"], class_=re.compile("price|amount", re.I))
                        if price_amount:
                            precio = price_amount.get_text(strip=True)
                        else:
                            precio = price_tag.get_text(strip=True)
                    
                    # Método 2: Buscar en otros elementos de precio
                    if precio == "Precio no encontrado":
                        price_elements = product.find_all(["span", "p", "div"], class_=re.compile("price|amount", re.I))
                        for elem in price_elements:
                            if elem and elem.get_text(strip=True):
                                precio = elem.get_text(strip=True)
                                break
                    
                    # Método 3: Buscar en texto de screen reader
                    if precio == "Precio no encontrado":
                        price_tag = product.find("span", class_="screen-reader-text")
                        if price_tag:
                            price_text = price_tag.get_text(strip=True)
                            if "precio" in price_text.lower():
                                match = re.search(r'Bs\.\s*([\d.,]+)', price_text)
                                if match:
                                    precio = match.group(1)
                    
                    # Método 4: Buscar en atributos de datos
                    if precio == "Precio no encontrado":
                        cache_tags = product.find_all(attrs={"data-price": True})
                        for cache_tag in cache_tags:
                            if cache_tag['data-price']:
                                precio = cache_tag['data-price']
                                break
                    
                    # Método 5: Buscar en cualquier elemento con información de precio
                    if precio == "Precio no encontrado":
                        all_elements = product.find_all(string=re.compile(r'Bs\.|REF|USD|\d+\.\d+'))
                        for element in all_elements:
                            if element.parent and not any(x in str(element.parent).lower() for x in ['button', 'input', 'script']):
                                match = re.search(r'(\d+[\d.,]*)', element)
                                if match:
                                    precio = match.group(1)
                                    break
                    
                    # Limpiar el precio
                    if precio != "Precio no encontrado":
                        # Eliminar texto no numérico pero mantener puntos y comas
                        precio = re.sub(r'[^\d.,]', '', precio)
                        
                        # Si está vacío después de la limpieza, mantener el valor original
                        if not precio:
                            precio = "Precio no encontrado"
                        else:
                            # Manejar múltiples puntos (separadores de miles)
                            if precio.count('.') > 1:
                                parts = precio.split('.')
                                integer_part = ''.join(parts[:-1])
                                decimal_part = parts[-1]
                                precio = f"{integer_part}.{decimal_part}"
                            
                            # Convertir comas a puntos para decimales
                            if ',' in precio:
                                precio = precio.replace(',', '.')
                            
                            # Asegurar formato decimal correcto
                            try:
                                # Intentar convertir a float y formatear
                                precio_float = float(precio)
                                precio = f"{precio_float:.2f}"
                            except ValueError:
                                # Si hay error, mantener el formato actual
                                pass
                except Exception as e:
                    print(f"Error al procesar el precio: {str(e)}")
                    precio = "Precio no encontrado"
                
                # Agregar producto a la lista
                all_products.append({
                    "nombre": nombre,
                    "precio": precio,
                    "producto_busqueda": termino_busqueda
                })
            
            print(f"Total acumulado de productos: {len(all_products)}")
            
            # Pequeña pausa entre búsquedas
            time.sleep(3)
    
    except Exception as e:
        print(f"Error durante el scraping: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            driver.quit()
        except:
            pass
        print("\nNavegador cerrado")
    
    # Guardar todos los productos en un CSV
    if all_products:
        unique_products = []
        seen = set()
        
        for product in all_products:
            identifier = (product["nombre"], product["precio"], product["producto_busqueda"])
            if identifier not in seen:
                seen.add(identifier)
                unique_products.append(product)
        
        df = pd.DataFrame(unique_products)
        
        output_path = r"C:\Users\sisa4\Downloads\productos_farmacia_completo.csv"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        
        print(f"\n✅ Se han guardado {len(df)} productos únicos en {output_path}")
        print("\nResumen por producto buscado:")
        for producto in PRODUCTOS:
            count = len(df[df["producto_busqueda"] == producto])
            print(f"- {producto}: {count} productos")
        
        print("\nEjemplo de los primeros 5 productos:")
        print(df.head())
    else:
        print("❌ No se encontraron productos para guardar")

if __name__ == "__main__":
    scrape_farmadon_full()