import requests
import concurrent.futures
import urllib.parse
import os
import re

# CONFIGURACIÓN
RANGO_INICIO = 1
RANGO_FIN = 120000
ARCHIVO_SALIDA = "playlist_series.m3u"
HILOS = 60 # Un poco más agresivo para series

print(f"--- ESCANEO TURBO SERIES ({RANGO_INICIO}-{RANGO_FIN}) ---")

session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})

URL_BASE = os.environ.get("URL_BASE_BTV")

if not URL_BASE:
    print("❌ Error: No se encontró la URL secreta.")
    exit()

def escanear(id_serie):
    url = f"{URL_BASE}/s.php?m={id_serie}"
    try:
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
    futuros = {executor.submit(escanear, i): i for i in range(RANGO_INICIO, RANGO_FIN + 1)}
    
    for future in concurrent.futures.as_completed(futuros):
        procesados += 1
        if procesados % 2000 == 0:
            print(f"Procesados: {procesados}/{RANGO_FIN}...", end="\r")
            
        resultado = future.result()
        if resultado:
            enlaces_encontrados.append(resultado)

unicos = list(set(enlaces_encontrados))
print(f"\n✅ Encontrados: {len(unicos)} capítulos únicos.")

with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    
    for link in unicos:
        # Limpieza URL
        link_final = link.replace(" ", "%20")
        
        # --- A. Título ---
        nombre_crudo = link_final.split("/")[-1].split("?")[0]
        titulo = urllib.parse.unquote(nombre_crudo)
        for ext in ['.mp4', '.mkv', '.avi']:
            titulo = titulo.replace(ext, "")
            
        # --- B. Grupo Inteligente (Tu lógica portada a Python) ---
        partes = link_final.split("/")
        # partes[-1] es el archivo
        # partes[-2] es la carpeta contenedora
        # partes[-3] es la carpeta anterior
        
        carpeta_inmediata = urllib.parse.unquote(partes[-2])
        
        # Regex para buscar Season, Temporada, S01, T01, etc.
        es_temporada = re.search(r'(?i)(Season|Temporada|Volume|S\d+|T\d+|TP\d+|Tp\d+)', carpeta_inmediata)
        
        if es_temporada:
            # Si es carpeta de temporada, el nombre de la serie está una atrás
            grupo_raw = partes[-3]
        else:
            # Si no, la carpeta inmediata es el nombre
            grupo_raw = partes[-2]
            
        grupo = urllib.parse.unquote(grupo_raw)
        
        # Limpiezas finales de grupo
        grupo = grupo.replace("P3L1CUL4S", "PELICULAS").replace("S3R13S", "SERIES").replace("_", " ")
        
        # --- C. Guardar ---
        f.write(f'#EXTINF:-1 tvg-id="avi" tvg-logo="" group-title="{grupo}",{titulo}\n')
        f.write(f'{link_final}\n')


print(f"💾 Guardado en {ARCHIVO_SALIDA}")
