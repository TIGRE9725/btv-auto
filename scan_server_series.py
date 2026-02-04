import requests
import re
import urllib.parse
import os
import concurrent.futures
import threading
import time
from urllib.parse import urljoin, unquote

# ==========================================
# ⚙️ CONFIGURACIÓN V7.1 (MATCH TOTAL)
# ==========================================

HOST = os.environ.get("URL_SERVER_IP")

RUTAS_A_ESCANEAR = [
    "/contenido/",
    "/server2/contenido/",
    "/server3/contenido/series/"
]

ARCHIVO_SALIDA = "lista_server_series.m3u"

# --- AJUSTES DE RENDIMIENTO ---
PROFUNDIDAD_MAX = 15  
HILOS = 15            
TIMEOUT = 40          
MAX_RETRIES = 5       

# --- CONFIGURACIÓN DE CONEXIÓN (RECUPERADO) ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# --- 1. LISTA NEGRA (Lo que NUNCA debe entrar) ---
PROHIBIDO = [
    "XXX", "xxx", "ADULT", "18+", "PORN", "XVIDEOS", "HENTAI", "SEX", "sex", 
    "peliculas", "Peliculas", "PELICULAS", "CINE%20CAM", "PELICULAS%204K", 
    "PELICULAS%2060%20FPS", "SAGA", "CINECAN", "CLASICAST", "ESTRENOS%20PELICULAS%202", 
    "KIDS", "MEXICANAST", "Navidad", "PELICULAS%2060%20FPS", "PELICULAS%202023", 
    "PELICULAS2024", "PELICULAS%20DC", "PELICULAS%20DE%20ACCION", "PELICULAS%20DISNEY"
]

# --- 2. LISTA BLANCA (OBLIGATORIO: Debe tener al menos una de estas palabras) ---
PERMITIDOS = [
    "Game of Thrones", "Game%20of%20Thrones", "Game%20of%20Thrones4k", 
    "Dave,%20El%20Barbaro", "Monster%20High", "Monster%20High%20Serie", 
    "Rupaul's%20Drag%20Race%20All%20Stars", "Switch%20Drag%20Race", 
    "The_Neighborhoodt", "Yin%20Yang%20Yo", "Ahsoka%204k", 
    "Game%20Of%20Thrones", "Game%20Of%20Thrones%204k",
    "Season", "Temporada", "Capitulo", "Episodio",
    "S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08",
    "E01", "E02", "Series", "Serie", "series", "serie", 
    "SERIES%204K", "ANIME", "ANIME%202023", "DORAMAS", 
    "ESTRENO%20SERIES", "REPARTIR", "Primo", "RETROSV", 
    "SEIRES%202023", "SERIES%202024", "Series_2", "TURKASS", 
    "Telenovelas", "Tv%20Novelas%202", "SERIES%20DOBLE%20AUIDO%202"
]

EXTENSIONES_VIDEO = ['.mp4', '.mkv', '.avi']

# --- 3. CARPETAS A IGNORAR AL BUSCAR EL NOMBRE DEL GRUPO ---
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

# Iniciamos sesión persistente (Mejora de rendimiento del código original)
session = requests.Session()
session.headers.update(HEADERS)

def limpiar_texto(texto):
    return unquote(texto)

def pasa_los_filtros(url):
    """
    Aplica la lógica estricta:
    1. NO debe estar en PROHIBIDO.
    2. DEBE estar en PERMITIDOS (Whitelist).
    """
    url_lower = url.lower() 
    
    # 1. Chequeo de Lista Negra
    for mal in PROHIBIDO:
        if mal.lower() in url_lower:
            return False
            
    # 2. Chequeo de Lista Blanca
    # Debe contener al menos una palabra clave de PERMITIDOS
    for bien in PERMITIDOS:
        if bien in url: 
            return True
            
    return False

def obtener_grupo_inteligente(url_completa):
    """
    Lógica 'Inteligente' (Reverse Path) para limpiar nombres de grupos
    """
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
    """Recuperador de archivos usando la SESIÓN global"""
    for intento in range(MAX_RETRIES):
        try:
            # Usamos 'session.get' en lugar de 'requests.get' para mantener headers y cookies
            r = session.get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                return r
            elif r.status_code == 404:
                return None 
        except requests.RequestException:
            pass 
        time.sleep(1 + intento)
    return None

def escanear_url(url):
    subcarpetas_nuevas = []
    
    r = request_con_retry(url)
    
    if not r:
        with lock_lista:
            errores_log.append(url)
        return []

    try:
        enlaces = re.findall(r'href=["\'](.*?)["\']', r.text)

        for link_raw in enlaces:
            if link_raw in ['../', './', '?', '#'] or link_raw.startswith('?'): continue
            
            full_link = urljoin(url, link_raw)
            
            # --- CASO VIDEO ---
            if any(link_raw.lower().endswith(ext) for ext in EXTENSIONES_VIDEO):
                # AQUI APLICAMOS TU FILTRO ESTRICTO (WHITELIST)
                if not pasa_los_filtros(full_link): continue

                titulo = limpiar_texto(link_raw)
                for ext in EXTENSIONES_VIDEO:
                    titulo = titulo.replace(ext, "")
                
                grupo = obtener_grupo_inteligente(full_link)
                
                entry = f'#EXTINF:-1 tvg-id="" tvg-logo="" group-title="{grupo}",{titulo}\n{full_link}'
                
                with lock_lista:
                    lista_final.append(entry)

            # --- CASO CARPETA ---
            elif link_raw.endswith('/'):
                # Filtro de seguridad solo para carpetas (PROHIBIDO)
                es_valida = True
                for mal in PROHIBIDO:
                    if mal.lower() in full_link.lower():
                        es_valida = False; break
                
                if es_valida:
                    subcarpetas_nuevas.append(full_link)

    except:
        pass
        
    return subcarpetas_nuevas

# ==========================================
# 🚀 EJECUCIÓN
# ==========================================

print(f"--- ESCANEO SERIES V7.1 (FINAL CODE MATCH) ---")

if not HOST:
    print("❌ Error: Variable URL_SERVER_IP no definida.")
    exit(1)

print(f"Host: {HOST}")

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
    print(f"⚠️ {len(errores_log)} carpetas fallaron tras {MAX_RETRIES} intentos.")

with open(ARCHIVO_SALIDA, "w", encoding="utf-8", newline="\n") as f:
    f.write("#EXTM3U\n")
    f.write("\n".join(lista_final))

print(f"📄 Lista guardada en: {ARCHIVO_SALIDA}")
