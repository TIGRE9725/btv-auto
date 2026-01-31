import requests
import re
import urllib.parse
import os
from urllib.parse import urljoin
import urllib3

# Desactivar advertencias SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURACIÓN ---
HOST = os.environ.get("URL_DYNDS", "https://fina.dyndns.tv")
RUTA_OBJETIVO = "/Peliculas/"
URL_RAIZ = urljoin(HOST, RUTA_OBJETIVO)

ARCHIVO_SALIDA = "lista_dyndns.m3u"
NOMBRE_GRUPO = "PELIS-dyndns"
PROFUNDIDAD_MAX = 10

PROHIBIDO = ["XXX", "xxx", "ADULT", "18+", "PORN", "XVIDEOS", "Season", "Temporada", "Capitulo", "S01", "S02", "E01", "Serie"]
EXTENSIONES_VIDEO = ('.mp4', '.mkv', '.avi', '.ts', '.m3u8')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

urls_visitadas = set()
lista_videos = []
session = requests.Session()
session.headers.update(HEADERS)

def limpiar_titulo(url_segmento):
    nombre = urllib.parse.unquote(url_segmento).rstrip('/').split('/')[-1]
    for ext in EXTENSIONES_VIDEO:
        nombre = nombre.replace(ext, "")
    return nombre.replace(".", " ").replace("_", " ").strip()

def es_contenido_prohibido(texto):
    for mala in PROHIBIDO:
        if mala.lower() in texto.lower(): return True
    return False

def escanear(url, nivel):
    if nivel > PROFUNDIDAD_MAX or url in urls_visitadas: return
    urls_visitadas.add(url)
    
    print(f"📂 Escaneando: {url}") # Log normal

    try:
        r = session.get(url, timeout=15, verify=False)
        
        # --- DIAGNÓSTICO ---
        print(f"   STATUS: {r.status_code}") 
        if r.status_code != 200:
            print(f"   ❌ BLOQUEADO O ERROR: El servidor respondió {r.status_code}")
            return
        
        html = r.text
        # Usamos (?i) para que href sea insensible a mayúsculas
        enlaces = re.findall(r'(?i)href=["\']([^"\']+)["\']', html)
        print(f"   🔗 Enlaces brutos encontrados: {len(enlaces)}") # ¿Ve algo?

        for link_raw in enlaces:
            if link_raw in ['../', './', '/', '?C=N;O=D', '?C=M;O=A', '?C=S;O=A', '?C=D;O=A']: continue
            
            full_link = urljoin(url, link_raw)
            if es_contenido_prohibido(link_raw) or es_contenido_prohibido(full_link): continue

            if full_link.lower().endswith(EXTENSIONES_VIDEO):
                titulo = limpiar_titulo(link_raw)
                entry = f'#EXTINF:-1 tvg-id="" tvg-logo="" group-title="{NOMBRE_GRUPO}",{titulo}\n{full_link}'
                lista_videos.append(entry)
                # print(f"   ✅ Video: {titulo}") # Descomenta para ver cada video

            elif link_raw.endswith('/'):
                escanear(full_link, nivel + 1)

    except Exception as e:
        print(f"⚠️ EXCEPCIÓN: {e}")

print(f"--- INICIANDO DIAGNÓSTICO PELICULAS ---")
print(f"Objetivo: {URL_RAIZ}")
escanear(URL_RAIZ, 1)
print(f"\n✅ FINALIZADO. Videos encontrados: {len(lista_videos)}")

with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    f.write("\n".join(lista_videos))
