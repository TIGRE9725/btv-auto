import requests
import concurrent.futures
import urllib.parse
import os

# CONFIGURACIÓN
RANGO_INICIO = 1
RANGO_FIN = 35000
ARCHIVO_SALIDA = "playlist_peliculas.m3u"
HILOS = 50  # Conexiones simultáneas

print(f"--- ESCANEO TURBO PELICULAS ({RANGO_INICIO}-{RANGO_FIN}) ---")

# Session para reutilizar conexiones (más velocidad)
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})

URL_BASE = os.environ.get("URL_BASE_BTV")

if not URL_BASE:
    print("❌ Error: No se encontró la URL secreta.")
    exit()

def escanear(id_peli):
    url = f"{URL_BASE}/played.php?m={id_peli}" 
    try:
        # HEAD es más rápido, allow_redirects=False para atrapar el 301/302
        r = session.head(url, allow_redirects=False, timeout=3)
        if r.status_code in [301, 302]:
            location = r.headers.get('Location', '')
            if any(ext in location for ext in ['.mp4', '.mkv', '.avi']):
                return location
    except:
        pass
    return None

enlaces_encontrados = []
procesados = 0

with concurrent.futures.ThreadPoolExecutor(max_workers=HILOS) as executor:
    # Creamos las tareas
    futuros = {executor.submit(escanear, i): i for i in range(RANGO_INICIO, RANGO_FIN + 1)}
    
    for future in concurrent.futures.as_completed(futuros):
        procesados += 1
        if procesados % 1000 == 0:
            print(f"Procesados: {procesados}/{RANGO_FIN}...", end="\r")
            
        resultado = future.result()
        if resultado:
            enlaces_encontrados.append(resultado)

# Eliminar duplicados
unicos = list(set(enlaces_encontrados))
print(f"\n✅ Encontrados: {len(unicos)} enlaces únicos.")

# Guardar M3U
with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    
    for link in unicos:
        # 1. Corrección Espacios
        link_final = link.replace(" ", "%20")
        
        # 2. Título Limpio
        nombre_archivo = link_final.split("/")[-1]
        titulo = urllib.parse.unquote(nombre_archivo)
        for ext in ['.mp4', '.mkv', '.avi']:
            titulo = titulo.replace(ext, "")
            
        # 3. Escribir
        f.write(f'#EXTINF:-1 tvg-id="avi" tvg-logo="" group-title="PELICULAS",{titulo}\n')
        f.write(f'{link_final}\n')

print(f"💾 Guardado en {ARCHIVO_SALIDA}")