import requests
import re
import urllib.parse
import os
from urllib.parse import urljoin
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HOST = os.environ.get("URL_DYNDS", "https://fina.dyndns.tv")
RUTAS_OBJETIVO = ["/Series/", "/Cartoons/"]
ARCHIVO_SALIDA = "lista_dyndns_series.m3u"
PROFUNDIDAD_MAX = 10
PROHIBIDO = ["XXX", "xxx", "ADULT", "18+", "PORN", "XVIDEOS", "HENTAI"]
EXTENSIONES_VIDEO = ('.mp4', '.mkv', '.avi', '.ts', '.m3u8')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

urls_visitadas = set()
lista_videos = []
session = requests.Session()
session.headers.update(HEADERS)

def limpiar_texto(texto):
    return urllib.parse.unquote(texto).replace("_", " ").replace(".", " ").strip()

def obtener_grupo_serie(url_completa, host):
    try:
        path = url_completa.replace(host, "")
        parts = [p for p in path.split('/') if p]
        if "Series" in parts:
            idx = parts.index("Series")
            if len(parts) > idx + 1: return f"SERIES - {limpiar_texto(parts[idx+1])}"
        elif "Cartoons" in parts:
            idx = parts.index("Cartoons")
            if len(parts) > idx + 1: return f"CARTOONS - {limpiar_texto(parts[idx+1])}"
    except: pass
    return "SERIES - VARIAS"

def es_contenido_prohibido(texto):
    for mala in PROHIBIDO:
        if mala.lower() in texto.lower(): return True
    return False

def escanear(url, nivel):
    if nivel > PROFUNDIDAD_MAX or url in urls_visitadas: return
    urls_visitadas.add(url)
    
    print(f"📂 Escaneando: {url}")

    try:
        r = session.get(url, timeout=15, verify=False)
        
        # --- DIAGNÓSTICO ---
        print(f"   STATUS: {r.status_code}")
        if r.status_code != 200:
            print(f"   ❌ ERROR: Código {r.status_code}")
            return

        html = r.text
        enlaces = re.findall(r'(?i)href=["\']([^"\']+)["\']', html)
        print(f"   🔗 Enlaces encontrados: {len(enlaces)}")

        for link_raw in enlaces:
            if link_raw in ['../', './', '/', '?C=N;O=D', '?C=M;O=A', '?C=S;O=A', '?C=D;O=A']: continue
            full_link = urljoin(url, link_raw)
            if es_contenido_prohibido(link_raw) or es_contenido_prohibido(full_link): continue

            if full_link.lower().endswith(EXTENSIONES_VIDEO):
                titulo = limpiar_texto(link_raw)
                for ext in EXTENSIONES_VIDEO:
                    titulo = titulo.replace(ext, "").replace(ext.replace(".", " "), "")
                grupo = obtener_grupo_serie(full_link, HOST)
                entry = f'#EXTINF:-1 tvg-id="" tvg-logo="" group-title="{grupo}",{titulo}\n{full_link}'
                lista_videos.append(entry)
            
            elif link_raw.endswith('/'):
                escanear(full_link, nivel + 1)

    except Exception as e:
        print(f"⚠️ EXCEPCIÓN: {e}")

print(f"--- INICIANDO DIAGNÓSTICO SERIES ---")
urls_inicio = [urljoin(HOST, ruta) for ruta in RUTAS_OBJETIVO]
for url_raiz in urls_inicio:
    print(f"\n🌍 Iniciando en: {url_raiz}")
    escanear(url_raiz, 1)

print(f"\n✅ FINALIZADO. Videos encontrados: {len(lista_videos)}")

with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    f.write("\n".join(lista_videos))
