import requests
import concurrent.futures
import urllib.parse
import os
import re

# ================= CONFIGURACIÓN =================
RANGO_INICIO = 1
RANGO_FIN = 120000
ARCHIVO_SALIDA = "playlist_series.m3u"
HILOS = 60 

# Lista de carpetas "sistema" que NO son nombres de series
CARPETAS_IGNORAR = [
    'series', 'S3R13S', 'm244$', 'NANEGOBACK', 'SERIESLAT', 
    'M', '132T', 'nvmevod.btv.mx', 'https:', 'http:', ''
]
# =================================================

print(f"--- ESCANEO INTELIGENTE SERIES V2 ({RANGO_INICIO}-{RANGO_FIN}) ---")

session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})

URL_BASE = os.environ.get("URL_BASE_BTV")

if not URL_BASE:
    print("❌ Error: No se encontró la variable de entorno URL_BASE_BTV.")
    exit()

def obtener_nombre_inteligente(url_limpia):
    """
    Recorre la URL de atrás hacia adelante descartando carpetas 
    que son números o temporadas, hasta encontrar el nombre real.
    """
    # 1. Decodificar (%20 -> Espacio)
    url_decoded = urllib.parse.unquote(url_limpia)
    
    # 2. Dividir en partes
    partes = url_decoded.split('/')
    
    # 3. Eliminar el nombre del archivo final (ej: 042.mp4)
    partes = partes[:-1]
    
    # 4. Recorrer de atrás hacia adelante
    for carpeta in reversed(partes):
        carpeta = carpeta.strip()
        if not carpeta: continue
        
        # CASO A: Es solo números (ej: "042", "1", "05") -> Es carpeta de episodio
        if re.match(r'^\d+$', carpeta):
            continue
            
        # CASO B: Es carpeta de temporada (Season X, Temporada X, TP1)
        if re.search(r'(?i)^(Season|Temporada|Volume|Vol|S\d+|T\d+|TP\d+)', carpeta):
            continue
            
        # CASO C: Es carpeta de sistema (S3R13S, series, etc)
        if carpeta in CARPETAS_IGNORAR:
            continue
            
        # Si no es nada de lo anterior, ¡ES LA SERIE!
        return carpeta
        
    return "Series Varias"

def escanear(id_serie):
    url = f"{URL_BASE}/s.php?m={id_serie}"
    try:
        # allow_redirects=False para atrapar el 302
        r = session.head(url, allow_redirects=False, timeout=3)
        if r.status_code in [301, 302]:
            location = r.headers.get('Location', '')
            
            # Verificar si es video
            if any(ext in location for ext in ['.mp4', '.mkv', '.avi']):
                # 1. CORRECCIÓN TOKEN: Quitamos todo desde el '?'
                location_clean = location.split('?')[0]
                return location_clean
                
    except:
        pass
    return None

enlaces_encontrados = []
procesados = 0

print("🚀 Iniciando escaneo...")

with concurrent.futures.ThreadPoolExecutor(max_workers=HILOS) as executor:
    # Generar rango de IDs
    futuros = {executor.submit(escanear, i): i for i in range(RANGO_INICIO, RANGO_FIN + 1)}
    
    for future in concurrent.futures.as_completed(futuros):
        procesados += 1
        resultado = future.result()
        
        if resultado:
            link_final = resultado
            
            # --- LÓGICA DE NOMBRE ---
            # 1. Obtener Nombre del Archivo (Titulo Episodio)
            nombre_archivo = link_final.split("/")[-1] # Ej: 042.mp4
            titulo = urllib.parse.unquote(nombre_archivo)
            for ext in ['.mp4', '.mkv', '.avi']:
                titulo = titulo.replace(ext, "")
            
            # 2. Obtener Grupo Inteligente (Nombre Serie)
            grupo = obtener_nombre_inteligente(link_final)
            
            # --- GENERAR ENTRADA M3U ---
            # Usamos el grupo también en el título para que se vea bien: "Serie - Episodio"
            nombre_display = f"{grupo} - {titulo}"
            
            m3u_entry = f'#EXTINF:-1 tvg-id="avi" tvg-logo="" group-title="{grupo}",{nombre_display}\n{link_final}'
            enlaces_encontrados.append(m3u_entry)
            print(f"[+] {grupo}: {titulo}")
            
        if procesados % 1000 == 0:
            print(f"   Progreso: {procesados}/{RANGO_FIN - RANGO_INICIO} ... Encontrados: {len(enlaces_encontrados)}")

# GUARDAR
print(f"💾 Guardando {len(enlaces_encontrados)} series en {ARCHIVO_SALIDA}...")
with open(ARCHIVO_SALIDA, "w", encoding="utf-8", newline="\n") as f:
    f.write("#EXTM3U\n")
    f.write("\n".join(enlaces_encontrados))

print("✅ ¡Terminado!")
