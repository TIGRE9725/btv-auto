import requests
import re
import urllib.parse
import os
from urllib.parse import urljoin
import urllib3

# Desactivar advertencias SSL (Vital para servidores caseros/dyndns)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# ⚙️ CONFIGURACIÓN
# ==========================================

# 1. RECUPERAR LA BASE DEL SECRETO (https://fina.dyndns.tv)
HOST = os.environ.get("URL_DYNDS")

# 2. DEFINIR LA RUTA ESPECÍFICA EN EL SCRIPT
RUTA_OBJETIVO = "/Peliculas/"

# Construimos la URL completa: https://fina.dyndns.tv/Peliculas/
URL_RAIZ = urljoin(HOST, RUTA_OBJETIVO)

ARCHIVO_SALIDA = "lista_dyndns.m3u"
NOMBRE_GRUPO = "PELIS-dyndns"  # <-- Grupo Fijo
PROFUNDIDAD_MAX = 10

# Filtros (Adultos + Series que se cuelen)
PROHIBIDO = [
    "XXX", "xxx", "ADULT", "18+", "PORN", "XVIDEOS",
    "Season", "Temporada", "Capitulo", "S01", "S02", "E01", "Serie"
]

EXTENSIONES_VIDEO = ('.mp4', '.mkv', '.avi', '.ts', '.m3u8')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ==========================================
# 🛠️ MOTOR DE ESCANEO
# ==========================================

urls_visitadas = set()
lista_videos = []

session = requests.Session()
session.headers.update(HEADERS)

def limpiar_titulo(url_segmento):
    """Limpia el nombre del archivo"""
    nombre = urllib.parse.unquote(url_segmento)
    nombre = nombre.rstrip('/')
    nombre = nombre.split('/')[-1]
    
    for ext in EXTENSIONES_VIDEO:
        nombre = nombre.replace(ext, "")
        
    nombre = nombre.replace(".", " ").replace("_", " ")
    return nombre.strip()

def es_contenido_prohibido(texto):
    texto_lower = texto.lower()
    for mala in PROHIBIDO:
        if mala.lower() in texto_lower:
            return True
    return False

def escanear(url, nivel):
    if nivel > PROFUNDIDAD_MAX: return
    if url in urls_visitadas: return
    
    urls_visitadas.add(url)
    print(f"📂 Escaneando: {url}")

    try:
        # verify=False es CLAVE aquí
        r = session.get(url, timeout=15, verify=False)
        
        if r.status_code != 200: return
        
        html = r.text
        enlaces = re.findall(r'href=["\']([^"\']+)["\']', html)
        
        for link_raw in enlaces:
            if link_raw in ['../', './', '/', '?C=N;O=D', '?C=M;O=A', '?C=S;O=A', '?C=D;O=A']:
                continue
            
            full_link = urljoin(url, link_raw)
            
            if es_contenido_prohibido(link_raw) or es_contenido_prohibido(full_link):
                continue

            # CASO A: VIDEO
            if full_link.lower().endswith(EXTENSIONES_VIDEO):
                titulo = limpiar_titulo(link_raw)
                
                # Grupo FIJO para todos
                entry = f'#EXTINF:-1 tvg-id="" tvg-logo="" group-title="{NOMBRE_GRUPO}",{titulo}\n{full_link}'
                lista_videos.append(entry)

            # CASO B: CARPETA
            elif link_raw.endswith('/'):
                escanear(full_link, nivel + 1)

    except Exception as e:
        print(f"⚠️ Error en {url}: {e}")

# ==========================================
# 🚀 EJECUCIÓN
# ==========================================

print(f"--- INICIANDO ESCANEO DYNDNS ---")
print(f"Objetivo: {URL_RAIZ}")

escanear(URL_RAIZ, 1)

print(f"\n✅ FINALIZADO. Videos encontrados: {len(lista_videos)}")

with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    f.write("\n".join(lista_videos))

print(f"💾 Guardado en: {ARCHIVO_SALIDA}")
