import requests
import re
import urllib.parse
import os
from urllib.parse import urljoin

# ==========================================
# ⚙️ CONFIGURACIÓN SEGURA
# ==========================================

# 1. RECUPERAR IP DEL SECRETO (Nadie la verá en el código)
HOST = os.environ.get("URL_SERVER_IP")

# 2. DEFINIR LAS RUTAS RELATIVAS (El script las pegará al HOST)
RUTAS_A_ESCANEAR = [
    "/contenido/",
    "/server2/contenido/",
    "/server3/contenido/peliculas/"
]

ARCHIVO_SALIDA = "lista_server.m3u"
NOMBRE_GRUPO = "PELIS-SERVER"
PROFUNDIDAD_MAX = 8

# 3. FILTROS DE EXCLUSIÓN (Adultos + Series Intrusas)
# Si una carpeta tiene esto, EL SCRIPT NO ENTRA.
PROHIBIDO = [
    # --- ADULTOS ---
    "XXX", "xxx", "ADULT", "18+", "PORN", "XVIDEOS", "HENTAI",
    # --- SERIES INTRUSAS (Para que no salgan en lista de pelis) ---
    "Game of Thrones", "Game%20of%20Thrones", "Game%20of%20Thrones4k", "Dave,%20El%20Barbaro", "Monster%20High", "Monster%20High%20Serie", "Rupaul's%20Drag%20Race%20All%20Stars", "Switch%20Drag%20Race", "The_Neighborhoodt", "Yin%20Yang%20Yo", "Ahsoka%204k", "Game%20Of%20Thrones", "Game%20Of%20Thrones%204k",
    "Season", "Temporada", "Capitulo", "Episodio",
    "S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08",
    "E01", "E02", "Series", "Serie", "series", "serie", "SERIES%204K", "ANIME", "ANIME%202023", "DORAMAS", "ESTRENO%20SERIES", "REPARTIR", "Primo", "RETROSV", "SEIRES%202023", "SERIES%202024", "Series_2", "TURKASS", "Telenovelas", "Tv%20Novelas%202", "SERIES%20DOBLE%20AUIDO%202"
]

EXTENSIONES_VIDEO = ('.mp4', '.mkv', '.avi', '.ts', '.m3u8')

# ==========================================
# 🛠️ MOTOR DE ESCANEO
# ==========================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

urls_visitadas = set()
lista_final = []

session = requests.Session()
session.headers.update(HEADERS)

def limpiar_titulo(url_segmento):
    nombre = urllib.parse.unquote(url_segmento)
    nombre = nombre.rstrip('/')
    nombre = nombre.split('/')[-1]
    for ext in EXTENSIONES_VIDEO:
        nombre = nombre.replace(ext, "")
    nombre = nombre.replace(".", " ").replace("_", " ")
    return nombre.strip()

def es_contenido_prohibido(texto):
    """Revisa si el link contiene palabras prohibidas (Adultos o Series)"""
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
        r = session.get(url, timeout=10)
        if r.status_code != 200: return
        
        html = r.text
        # Regex robusto para sacar hrefs
        enlaces = re.findall(r'href=["\']([^"\']+)["\']', html)
        
        for link_raw in enlaces:
            # Ignorar navegación
            if link_raw in ['../', './', '/', '?C=N;O=D', '?C=M;O=A', '?C=S;O=A', '?C=D;O=A']:
                continue
            
            full_link = urljoin(url, link_raw)
            
            # --- FILTRO MAESTRO ---
            # Aquí es donde ignoramos "Game of Thrones" o "XXX"
            if es_contenido_prohibido(link_raw) or es_contenido_prohibido(full_link):
                # print(f"   🚫 Saltando carpeta/archivo: {link_raw}") # Descomentar para depurar
                continue

            # CASO A: VIDEO (PELICULA)
            if full_link.lower().endswith(EXTENSIONES_VIDEO):
                titulo = limpiar_titulo(link_raw)
                entry = f'#EXTINF:-1 tvg-id="" tvg-logo="" group-title="{NOMBRE_GRUPO}",{titulo}\n{full_link}'
                lista_final.append(entry)

            # CASO B: CARPETA (RECURSIVIDAD)
            elif link_raw.endswith('/'):
                escanear(full_link, nivel + 1)

    except Exception as e:
        print(f"⚠️ Error en {url}: {e}")

# ==========================================
# 🚀 EJECUCIÓN
# ==========================================

print(f"--- INICIANDO ESCANEO PROTEGIDO ---")

# Construimos las URLs usando el SECRETO + LAS RUTAS
urls_objetivo_reales = [urljoin(HOST, ruta) for ruta in RUTAS_A_ESCANEAR]

for url_raiz in urls_objetivo_reales:
    print(f"\n🌍 Iniciando en ruta: {url_raiz}")
    escanear(url_raiz, 1)

print(f"\n✅ FINALIZADO. Videos encontrados: {len(lista_final)}")

with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    f.write("\n".join(lista_final))

print(f"💾 Guardado en: {ARCHIVO_SALIDA}")
