#normaliza.py
import pandas as pd
import re
from pathlib import Path

# ---------- CONFIG ----------
RUTA_CONSOLIDADO = Path(r"C:\Users\sisa4\Desktop\consolidado_farmacias.xlsx")
RUTA_UNICOS      = RUTA_CONSOLIDADO.with_name("productos_unicos.csv")

# ---------- FUNCIÓS DE NORMALIZACIÓN ----------
def normalizar(texto):
    if pd.isna(texto) or not isinstance(texto, str):
        return None
    return re.sub(r'\s+', ' ', texto.lower().strip())

def extraer_dosis(nombre):
    m = re.search(r'(\d+(?:\.\d+)?)\s*(mg|g|ml|mcg|µg)\b', nombre, re.I)
    return f"{float(m.group(1))}{m.group(2).lower()}" if m else None

def extraer_cantidad_forma(nombre):
    m = re.search(r'(\d+)\s*(tab|cap|soft|comp|grag|sob|jbe|susp|ml|g)\w*', nombre, re.I)
    return f"{m.group(1)}{m.group(2).lower()}" if m else None

def extraer_principio(nombre):
    principios = ["diclofenac", "paracetamol", "ibuprofeno", "loratadina",
                  "amoxicilina", "naproxeno", "aspirina", "cetirizina",
                  "omeprazol", "metformina"]
    for p in principios:
        if p in nombre.lower():
            return p
    return None

def extraer_marca(nombre, marca_col):
    marcas = ["aflamax", "diklason", "genven", "oftalmi", "mk", "genfar",
              "pfizer", "gsk", "panadol", "calox", "bago", "roemmers", "clofen"]
    nombre_low = nombre.lower()
    for m in marcas:
        if m in nombre_low:
            return m
    return normalizar(marca_col)  # ya retorna None si marca_col es NaN

def generar_id(row):
    return hash((row['principio'], row['marca'], row['dosis'], row['presentacion'])) & 0xffffffff

# ---------- CARGAR DATOS ----------
df = pd.read_excel(RUTA_CONSOLIDADO)
df['nombre_norm'] = df['Nombre'].apply(normalizar)

# ---------- EXTRAER COMPONENTES ----------
df['principio']   = df['nombre_norm'].apply(extraer_principio)
df['dosis']       = df['nombre_norm'].apply(extraer_dosis)
df['presentacion']= df['nombre_norm'].apply(extraer_cantidad_forma)
df['marca']       = df.apply(lambda r: extraer_marca(r['nombre_norm'], r['Marca']), axis=1)

# ---------- FILTRAR FILAS VÁLIDAS ----------
df_valido = df.dropna(subset=['principio', 'marca', 'dosis', 'presentacion'])

# ---------- CREAR TABLA ÚNICA ----------
unicos = (df_valido
          .drop_duplicates(subset=['principio', 'marca', 'dosis', 'presentacion'])
          .assign(id_producto=lambda x: x.apply(generar_id, axis=1))
          [['id_producto', 'principio', 'marca', 'dosis', 'presentacion']]
          .sort_values(['principio', 'marca']))

unicos.to_csv(RUTA_UNICOS, index=False)
print(f"✅ {len(unicos)} productos únicos guardados en {RUTA_UNICOS}")


# ... (todo el código anterior hasta guardar unicos.to_csv)

# ✅ PASO 2: ASIGNAR id_producto AL CONSOLIDADO ORIGINAL
# ---------- CARGAR TABLA ÚNICA ----------
mapa = (df_valido
        .drop_duplicates(subset=['principio', 'marca', 'dosis', 'presentacion'])
        .assign(id_producto=lambda x: x.apply(generar_id, axis=1))
        .set_index(['principio', 'marca', 'dosis', 'presentacion'])['id_producto']
        .to_dict())

# ---------- ASIGNAR id_producto AL CONSOLIDADO ----------
df['id_producto'] = df.apply(
    lambda r: mapa.get((r['principio'], r['marca'], r['dosis'], r['presentacion'])), axis=1)

# ---------- GUARDAR ----------
df.to_excel(RUTA_CONSOLIDADO, index=False)
print("✅ Columna 'id_producto' añadida al consolidado")