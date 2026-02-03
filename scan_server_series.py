import requests
import re
import urllib.parse
import os
import concurrent.futures
import threading
import time
from urllib.parse import urljoin, unquote

# ==========================================
# ⚙️ CONFIGURACIÓN V3.2 (TANK MODE)
# ==========================================

HOST = os.environ.get("URL_SERVER_IP")


RUTAS_SEMILLA = [
    "/contenido/",
    "/server2/contenido/",
    "/server3/contenido/series/"
]

ARCHIVO_SALIDA = "lista_server_series.m3u"

# --- AJUSTES DE RECUPERACIÓN ---
PROFUNDIDAD_MAX = 15  # Profundidad máxima para no dejar nada
HILOS = 15            # Menos hilos = Mayor estabilidad (evita bloqueos del server)
TIMEOUT = 30          # 30s de paciencia para carpetas gigantes
MAX_RETRIES = 3       # Intentos por carpeta antes de rendirse

# Filtros
PROHIBIDO = [
    "XXX", "xxx", "ADULT", "18+", "PORN", "XVIDEOS", "HENTAI", "SEX", "sex", 
    "peliculas", "Peliculas", "PELICULAS", "CINE%20CAM", "PELICULAS%204K", 
    "SAGA", "CINECAN", "CLASICAST", "ESTRENOS", "KIDS", "MEXICANAST", 
    "Navidad", "PELICULAS", "Disney", "Pixar", "Dreamworks"
]

EXTENSIONES_VIDEO = ['.mp4', '.mkv', '.avi']

IGNORAR_EN_GRUPO = [
    'contenido', 'server2', 'server3', 'series', 'series 4k', 'series 4k', 
    'lat', 'sub', 'cast', 'dual', 'latino', 'spa', 'eng', 'english', 'spanish',
    '1080p', '720p', '4k', 'hd', 'sd', 'web-dl',
    'temp', 'temporada', 'season', 's', 't', 'vol', 'volume'
]

# ==========================================
# 🛠️ FUNCIONES
# ==========================================

lock_lista = threading.Lock()
lista_final = []
visitados = set()
errores_log = []

def limpiar_texto(texto):
    return unquote(texto)

def es_contenido_permitido(url):
    url_lower = url.lower()
    for mal in PROHIBIDO:
        if mal.lower() in url_lower:
            return False
    return True

def obtener_grupo_inteligente(url_completa):
    """Lógica inteligente V2 para el nombre de la serie"""
    path = urllib.parse.urlparse(url_completa).path
    path = unquote(path)
    partes = path.split('/')
    partes = [p for p in partes if p.strip()]
    if partes: partes.pop() 

    for carpeta in reversed(partes):
        carpeta_lower = carpeta.lower()
        if re.match(r'^\d+$', carpeta): continue
        if re.search(r'^(season|temporada|temp|t\d+|s\d+|vol|volume)', carpeta_lower): continue
        
        ignorar_este = False
        for basura in IGNORAR_EN_GRUPO:
            if basura == carpeta_lower:
                ignorar_este = True; break
        if ignorar_este: continue

        nombre_final = re.sub(r'\s+4k$', '', carpeta, flags=re.IGNORECASE)
        return nombre_final.strip()

    return "Series Varias"

def request_con_retry(url):
    """Intenta descargar la URL varias veces si falla"""
    for intento in range(MAX_RETRIES):
        try:
            r = requests.get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                return r
            elif r.status_code == 404:
                return None # No existe, no reintentar
        except requests.RequestException:
            pass # Falló conexión, reintentar
        
        # Espera un poco antes de reintentar (backoff)
        time.sleep(1 + intento)
    
    return None

def escanear_url(url):
    """Procesa UNA carpeta con blindaje contra fallos"""
    subcarpetas_nuevas = []
    
    # 1. Descargar con reintentos
    r = request_con_retry(url)
    
    if not r:
        # Si falló después de 3 intentos, lo registramos
        with lock_lista:
            errores_log.append(url)
        return []

    try:
        # 2. Analizar contenido
        enlaces = re.findall(r'href=["\'](.*?)["\']', r.text)

        for link_raw in enlaces:
            if link_raw in ['../', './', '?', '#'] or link_raw.startswith('?'): continue
            
            full_link = urljoin(url, link_raw)
            
            # VIDEO DETECTADO
            if any(link_raw.lower().endswith(ext) for ext in EXTENSIONES_VIDEO):
                if not es_contenido_permitido(full_link): continue

                titulo = limpiar_texto(link_raw)
                for ext in EXTENSIONES_VIDEO:
                    titulo = titulo.replace(ext, "")
                
                grupo = obtener_grupo_inteligente(full_link)
                
                entry = f'#EXTINF:-1 tvg-id="" tvg-logo="" group-title="{grupo}",{titulo}\n{full_link}'
                
                with lock_lista:
                    lista_final.append(entry)

            # CARPETA DETECTADA
            elif link_raw.endswith('/'):
                if not es_contenido_permitido(full_link): continue
                subcarpetas_nuevas.append(full_link)

    except Exception as e:
        # Error de parsing raro
        print(f"Error procesando {url}: {e}")
        pass
        
    return subcarpetas_nuevas

# ==========================================
# 🚀 EJECUCIÓN BLINDADA
# ==========================================

print(f"--- ESCANEO SERIES V3.2 (TANK MODE) ---")
print(f"Host: {HOST}")
print(f"Config: Hilos={HILOS}, Timeout={TIMEOUT}s, Retries={MAX_RETRIES}, Profundidad={PROFUNDIDAD_MAX}")

# Nivel 0
urls_actuales = [urljoin(HOST, ruta) for ruta in RUTAS_SEMILLA]
for u in urls_actuales: visitados.add(u)

for nivel in range(1, PROFUNDIDAD_MAX + 1):
    print(f"\n📂 NIVEL {nivel}: Escaneando {len(urls_actuales)} carpetas...")
    
    siguientes_urls = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=HILOS) as executor:
        futuros = {executor.submit(escanear_url, url): url for url in urls_actuales}
        
        completados = 0
        total_nivel = len(urls_actuales)
        
        for future in concurrent.futures.as_completed(futuros):
            nuevas = future.result()
            
            for n in nuevas:
                if n not in visitados:
                    visitados.add(n)
                    siguientes_urls.append(n)
            
            completados += 1
            if completados % 20 == 0:
                print(f"   [N{nivel}] Progreso: {completados}/{total_nivel} | Series: {len(lista_final)}", end="\r")

    urls_actuales = siguientes_urls
    if not urls_actuales:
        print("\n   ✅ Profundidad máxima alcanzada o sin más carpetas.")
        break

print(f"\n\n🏁 FINALIZADO.")
print(f"📥 Episodios totales recuperados: {len(lista_final)}")

if errores_log:
    print(f"⚠️ Hubo {len(errores_log)} carpetas imposibles de leer (Timeouts/Errores).")
    # Opcional: Imprimir las primeras 5 para ver qué falló
    # for e in errores_log[:5]: print(f"   - {e}")

with open(ARCHIVO_SALIDA, "w", encoding="utf-8", newline="\n") as f:
    f.write("#EXTM3U\n")
    f.write("\n".join(lista_final))

print(f"📄 Lista guardada en: {ARCHIVO_SALIDA}")
