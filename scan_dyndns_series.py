import requests
import re
import urllib.parse
import os
from urllib.parse import urljoin
import urllib3

# Desactivar advertencias SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# ⚙️ CONFIGURACIÓN
# ==========================================

# 1. HOST (Desde Secreto)
HOST = os.environ.get("URL_DYNDS")
if not HOST:
    HOST = "https://fina.dyndns.tv" # Fallback

# 2. RUTAS A ESCANEAR (Lista)
RUTAS_OBJETIVO = ["/Series/", "/Cartoons/"]

ARCHIVO_SALIDA = "lista_dyndns_series.m3u"
PROFUNDIDAD_MAX = 10

# 3. FILTROS (Solo contenido adulto)
# ¡OJO! Aquí YA NO ponemos "Season" ni "Temporada"
PROHIBIDO = [
    "XXX", "xxx", "ADULT", "18+", "PORN", "XVIDEOS", "HENTAI"
]

EXTENSIONES_VIDEO = ('.mp4', '.mkv', '.avi', '.ts', '.m3u8')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ==========================================
# 🛠️ MOTOR INTELIGENTE
# ==========================================

urls_visitadas = set()
lista_videos = []

session = requests.Session()
session.headers.update(HEADERS)

def limpiar_texto(texto):
    """Decodifica URL y limpia caracteres feos"""
    texto = urllib.parse.unquote(texto)
    texto = texto.replace("_", " ").replace(".", " ")
    return texto.strip()

def obtener_grupo_serie(url_completa, host):
    """
    Deduce el nombre de la serie basado en la estructura de carpetas.
    Estrategia: Busca '/Series/' o '/Cartoons/' y toma la carpeta inmediata siguiente.
    """
    try:
        # Quitamos el host para analizar solo la ruta
        path = url_completa.replace(host, "")
        parts = [p for p in path.split('/') if p] # Dividir y quitar vacíos

        # Caso 1: SERIES
        if "Series" in parts:
            idx = parts.index("Series")
            # La carpeta que sigue a 'Series' es el nombre de la Serie
            if len(parts) > idx + 1:
                nombre_serie = limpiar_texto(parts[idx+1])
                return f"SERIES - {nombre_serie}"
        
        # Caso 2: CARTOONS
        elif "Cartoons" in parts:
            idx = parts.index("Cartoons")
            if len(parts) > idx + 1:
                nombre_toon = limpiar_texto(parts[idx+1])
                return f"CARTOONS - {nombre_toon}"

    except:
        pass
    
    # Si falla la detección, grupo genérico
    return "SERIES - VARIAS"

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
        r = session.get(url, timeout=15, verify=False)
        if r.status_code != 200: return
        
        html = r.text
        enlaces = re.findall(r'href=["\']([^"\']+)["\']', html)
        
        for link_raw in enlaces:
            # Ignorar navegación
            if link_raw in ['../', './', '/', '?C=N;O=D', '?C=M;O=A', '?C=S;O=A', '?C=D;O=A']:
                continue
            
            full_link = urljoin(url, link_raw)
            
            if es_contenido_prohibido(link_raw) or es_contenido_prohibido(full_link):
                continue

            # --- CASO A: VIDEO ---
            if full_link.lower().endswith(EXTENSIONES_VIDEO):
                # 1. Título del capítulo
                titulo = limpiar_texto(link_raw)
                for ext in EXTENSIONES_VIDEO:
                    titulo = titulo.replace(ext.replace(".", " "), "") # Quitar extensión limpia
                    titulo = titulo.replace(ext, "")
                
                # 2. Grupo Inteligente (Nombre de la Serie)
                grupo = obtener_grupo_serie(full_link, HOST)
                
                entry = f'#EXTINF:-1 tvg-id="" tvg-logo="" group-title="{grupo}",{titulo}\n{full_link}'
                lista_videos.append(entry)

            # --- CASO B: CARPETA ---
            elif link_raw.endswith('/'):
                escanear(full_link, nivel + 1)

    except Exception as e:
        print(f"⚠️ Error en {url}: {e}")

# ==========================================
# 🚀 EJECUCIÓN
# ==========================================

print(f"--- INICIANDO ESCANEO DE SERIES DYNDNS ---")

# Construir las URLs iniciales completas
urls_inicio = [urljoin(HOST, ruta) for ruta in RUTAS_OBJETIVO]

for url_raiz in urls_inicio:
    print(f"\n🌍 Iniciando en: {url_raiz}")
    escanear(url_raiz, 1)

print(f"\n✅ FINALIZADO. Videos encontrados: {len(lista_videos)}")

with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    f.write("\n".join(lista_videos))

print(f"💾 Guardado en: {ARCHIVO_SALIDA}")
