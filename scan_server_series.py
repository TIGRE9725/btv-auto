import requests
import re
import urllib.parse
import os
import concurrent.futures
import threading
from urllib.parse import urljoin, unquote

# ==========================================
# ⚙️ CONFIGURACIÓN TURBO V3
# ==========================================

HOST = os.environ.get("URL_SERVER_IP")
if not HOST: HOST = "http://15.235.51.60"

# Rutas iniciales
RUTAS_SEMILLA = [
    "/contenido/",
    "/server2/contenido/",
    "/server3/contenido/series/"
]

ARCHIVO_SALIDA = "lista_server_series.m3u"
PROFUNDIDAD_MAX = 6  # Bajamos un poco para asegurar terminación
HILOS = 30           # 30 Conexiones simultáneas
TIMEOUT = 5          # 5 segundos máximo por carpeta

# Listas de Filtro
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

# Candado para escribir en la lista compartida por los hilos
lock_lista = threading.Lock()
lista_final = []
visitados = set()

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

def escanear_url(url):
    """Procesa UNA carpeta y devuelve las subcarpetas encontradas"""
    subcarpetas_nuevas = []
    
    try:
        r = requests.get(url, timeout=TIMEOUT)
        if r.status_code != 200: return []

        enlaces = re.findall(r'href=["\'](.*?)["\']', r.text)

        for link_raw in enlaces:
            if link_raw in ['../', './', '?', '#'] or link_raw.startswith('?'): continue
            
            full_link = urljoin(url, link_raw)
            
            # Si es VIDEO
            if any(link_raw.lower().endswith(ext) for ext in EXTENSIONES_VIDEO):
                if not es_contenido_permitido(full_link): continue

                titulo = limpiar_texto(link_raw)
                for ext in EXTENSIONES_VIDEO:
                    titulo = titulo.replace(ext, "")
                
                grupo = obtener_grupo_inteligente(full_link)
                
                entry = f'#EXTINF:-1 tvg-id="" tvg-logo="" group-title="{grupo}",{titulo}\n{full_link}'
                
                with lock_lista:
                    lista_final.append(entry)

            # Si es CARPETA
            elif link_raw.endswith('/'):
                if not es_contenido_permitido(full_link): continue
                # Añadir a la lista para escanear en el siguiente nivel
                subcarpetas_nuevas.append(full_link)

    except:
        pass
        
    return subcarpetas_nuevas

# ==========================================
# 🚀 EJECUCIÓN POR NIVELES (Anti-Overflow)
# ==========================================

print(f"--- ESCANEO TURBO SERIES V3 (THREADS + BFS) ---")
print(f"Host: {HOST}")

# Nivel 0: Las semillas
urls_actuales = [urljoin(HOST, ruta) for ruta in RUTAS_SEMILLA]
for u in urls_actuales: visitados.add(u)

for nivel in range(1, PROFUNDIDAD_MAX + 1):
    print(f"\n📂 NIVEL {nivel}: Escaneando {len(urls_actuales)} carpetas...")
    
    siguientes_urls = []
    
    # Usamos ThreadPool para procesar este nivel en paralelo
    with concurrent.futures.ThreadPoolExecutor(max_workers=HILOS) as executor:
        futuros = {executor.submit(escanear_url, url): url for url in urls_actuales}
        
        completados = 0
        total_nivel = len(urls_actuales)
        
        for future in concurrent.futures.as_completed(futuros):
            nuevas = future.result()
            
            # Filtramos las que ya visitamos para evitar bucles
            for n in nuevas:
                if n not in visitados:
                    visitados.add(n)
                    siguientes_urls.append(n)
            
            completados += 1
            if completados % 50 == 0:
                print(f"   Progreso Nivel {nivel}: {completados}/{total_nivel} ... Videos hallados: {len(lista_final)}", end="\r")

    # Preparamos el siguiente nivel
    urls_actuales = siguientes_urls
    if not urls_actuales:
        print("\n   No hay más subcarpetas. Terminando.")
        break

print(f"\n\n✅ FINALIZADO. Episodios totales: {len(lista_final)}")

with open(ARCHIVO_SALIDA, "w", encoding="utf-8", newline="\n") as f:
    f.write("#EXTM3U\n")
    f.write("\n".join(lista_final))

print(f"📄 Lista guardada en: {ARCHIVO_SALIDA}")
