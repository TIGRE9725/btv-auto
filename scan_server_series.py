import requests
import re
import urllib.parse
import os
import concurrent.futures
import threading
import time
from urllib.parse import urljoin, unquote

# ==========================================
# ⚙️ CONFIGURACIÓN V6 (FINAL FUSION)
# ==========================================

HOST = os.environ.get("URL_SERVER_IP")

RUTAS_A_ESCANEAR = [
    "/contenido/",
    "/server2/contenido/",
    "/server3/contenido/series/"
]

ARCHIVO_SALIDA = "lista_server_series.m3u"

# --- AJUSTES DE RENDIMIENTO BLINDADO ---
PROFUNDIDAD_MAX = 15  # Profundidad total
HILOS = 15            # Hilos moderados para no saturar y causar errores 404 falsos
TIMEOUT = 40          # 40s de espera por carpeta
MAX_RETRIES = 5       # 5 Intentos por carpeta (Clave para recuperar los 81k)

# --- 1. LISTA NEGRA EXACTA (DEL COMMIT) ---
PROHIBIDO = [
    "XXX", "xxx", "ADULT", "18+", "PORN", "XVIDEOS", "HENTAI", "SEX", "sex", 
    "peliculas", "Peliculas", "PELICULAS", "CINE%20CAM", "PELICULAS%204K", 
    "PELICULAS%2060%20FPS", "SAGA", "CINECAN", "CLASICAST", "ESTRENOS%20PELICULAS%202", 
    "KIDS", "MEXICANAST", "Navidad", "PELICULAS%2060%20FPS", "PELICULAS%202023", 
    "PELICULAS2024", "PELICULAS%20DC", "PELICULAS%20DE%20ACCION", "PELICULAS%20DISNEY"
]

# --- 2. EXTENSIONES VÁLIDAS ---
EXTENSIONES_VIDEO = ['.mp4', '.mkv', '.avi']

# --- 3. CARPETAS A IGNORAR AL BUSCAR EL NOMBRE DE LA SERIE ---
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
    """
    Recupera el nombre limpio de la serie ignorando carpetas basura.
    """
    path = urllib.parse.urlparse(url_completa).path
    path = unquote(path)
    partes = path.split('/')
    partes = [p for p in partes if p.strip()]
    if partes: partes.pop() # Quitar archivo

    for carpeta in reversed(partes):
        carpeta_lower = carpeta.lower()
        
        # Ignorar números y temporadas
        if re.match(r'^\d+$', carpeta): continue
        if re.search(r'^(season|temporada|temp|t\d+|s\d+|vol|volume)', carpeta_lower): continue
        
        # Ignorar palabras técnicas
        ignorar_este = False
        for basura in IGNORAR_EN_GRUPO:
            if basura == carpeta_lower:
                ignorar_este = True; break
        if ignorar_este: continue

        # Limpieza final del nombre
        nombre_final = re.sub(r'\s+4k$', '', carpeta, flags=re.IGNORECASE)
        return nombre_final.strip()

    return "Series Varias"

def request_con_retry(url):
    """Intenta descargar con mucha paciencia (Recuperador de archivos)"""
    for intento in range(MAX_RETRIES):
        try:
            r = requests.get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                return r
            elif r.status_code == 404:
                return None 
        except requests.RequestException:
            pass 
        
        # Espera un poco antes de reintentar
        time.sleep(1 + intento)
    
    return None

def escanear_url(url):
    """Exploración robusta con reintentos"""
    subcarpetas_nuevas = []
    
    # 1. Descarga Blindada
    r = request_con_retry(url)
    
    if not r:
        with lock_lista:
            errores_log.append(url)
        return []

    try:
        # 2. Análisis
        enlaces = re.findall(r'href=["\'](.*?)["\']', r.text)

        for link_raw in enlaces:
            if link_raw in ['../', './', '?', '#'] or link_raw.startswith('?'): continue
            
            full_link = urljoin(url, link_raw)
            
            # --- CASO VIDEO ---
            if any(link_raw.lower().endswith(ext) for ext in EXTENSIONES_VIDEO):
                if not es_contenido_permitido(full_link): continue

                titulo = limpiar_texto(link_raw)
                for ext in EXTENSIONES_VIDEO:
                    titulo = titulo.replace(ext, "")
                
                grupo = obtener_grupo_inteligente(full_link)
                
                entry = f'#EXTINF:-1 tvg-id="" tvg-logo="" group-title="{grupo}",{titulo}\n{full_link}'
                
                with lock_lista:
                    lista_final.append(entry)

            # --- CASO CARPETA ---
            elif link_raw.endswith('/'):
                if not es_contenido_permitido(full_link): continue
                subcarpetas_nuevas.append(full_link)

    except Exception as e:
        # Si falla el parseo, lo anotamos
        pass
        
    return subcarpetas_nuevas

# ==========================================
# 🚀 EJECUCIÓN
# ==========================================

print(f"--- ESCANEO SERIES V6 (FINAL FUSION) ---")

if not HOST:
    print("❌ Error: Variable URL_SERVER_IP no definida.")
    exit(1)

print(f"Host: {HOST}")
print(f"Config: Hilos={HILOS}, Timeout={TIMEOUT}s, Retries={MAX_RETRIES}")

urls_actuales = [urljoin(HOST, ruta) for ruta in RUTAS_A_ESCANEAR]
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
            if completados % 50 == 0:
                print(f"   Progreso: {completados}/{total_nivel} | Encontrados: {len(lista_final)}", end="\r")

    urls_actuales = siguientes_urls
    if not urls_actuales:
        print("\n   ✅ Fin de carpetas.")
        break

print(f"\n\n🏁 FINALIZADO.")
print(f"📥 Episodios totales: {len(lista_final)}")

if errores_log:
    print(f"⚠️ Atención: {len(errores_log)} carpetas fallaron completamente tras 5 intentos.")

with open(ARCHIVO_SALIDA, "w", encoding="utf-8", newline="\n") as f:
    f.write("#EXTM3U\n")
    f.write("\n".join(lista_final))

print(f"📄 Lista guardada en: {ARCHIVO_SALIDA}")
