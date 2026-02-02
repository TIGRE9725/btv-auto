import requests
import re
import urllib.parse
import os
from urllib.parse import urljoin, unquote

# ==========================================
# ⚙️ CONFIGURACIÓN SERIES (LISTA BLANCA)
# ==========================================

HOST = os.environ.get("URL_SERVER_IP")

RUTAS_A_ESCANEAR = [
    "/contenido/",
    "/server2/contenido/",
    "/server3/contenido/series/" 
]

ARCHIVO_SALIDA = "lista_server_series.m3u"
PROFUNDIDAD_MAX = 8

# 1. LISTA NEGRA DE ARCHIVOS (Lo que NUNCA debe entrar)
PROHIBIDO = [
    "XXX", "xxx", "ADULT", "18+", "PORN", "XVIDEOS", "HENTAI", "SEX", "sex", 
    "peliculas", "Peliculas", "PELICULAS", "CINE%20CAM", "PELICULAS%204K", 
    "PELICULAS%2060%20FPS", "SAGA", "CINECAN", "CLASICAST", "ESTRENOS%20PELICULAS%202", 
    "KIDS", "MEXICANAST", "Navidad", "PELICULAS%2060%20FPS", "PELICULAS%202023", 
    "PELICULAS2024", "PELICULAS%20DC", "PELICULAS%20DE%20ACCION", "PELICULAS%20DISNEY"
]

# 2. EXTENSIONES VÁLIDAS
EXTENSIONES_VIDEO = ['.mp4', '.mkv', '.avi']

# 3. CARPETAS A IGNORAR AL BUSCAR EL NOMBRE DE LA SERIE
IGNORAR_EN_GRUPO = [
    'contenido', 'server2', 'server3', 'series', 'series 4k', 'series 4k', 
    'lat', 'sub', 'cast', 'dual', 'latino', 'spa', 'eng', 'english', 'spanish',
    '1080p', '720p', '4k', 'hd', 'sd', 'web-dl',
    'temp', 'temporada', 'season', 's', 't', 'vol', 'volume'
]

# ==========================================
# 🛠️ FUNCIONES
# ==========================================

def limpiar_texto(texto):
    """Decodifica URL y limpia caracteres"""
    texto = unquote(texto)
    return texto

def es_contenido_permitido(url):
    """Filtra pornografía y películas en el escaneo de series"""
    url_lower = url.lower()
    for mal in PROHIBIDO:
        if mal.lower() in url_lower:
            return False
    return True

def obtener_grupo_inteligente(url_completa):
    """
    Recorre la URL de atrás hacia adelante para encontrar el nombre REAL de la serie.
    Ignora carpetas de idiomas (lat/sub), números (1, 2) y sistema.
    """
    # 1. Decodificar y separar
    path = urllib.parse.urlparse(url_completa).path
    path = unquote(path)
    partes = path.split('/')
    
    # Eliminar vacíos y el nombre del archivo final
    partes = [p for p in partes if p.strip()]
    if partes: partes.pop() # Quitamos archivo.mp4

    # 2. Recorrer hacia atrás
    for carpeta in reversed(partes):
        carpeta_lower = carpeta.lower()
        
        # A. Ignorar números sueltos (ej: "1", "042")
        if re.match(r'^\d+$', carpeta):
            continue
            
        # B. Ignorar patrones de temporada (Season X, Temp X)
        if re.search(r'^(season|temporada|temp|t\d+|s\d+|vol|volume)', carpeta_lower):
            continue

        # C. Ignorar carpetas técnicas o de idioma (SUB, LAT, 4K, CONTENIDO)
        ignorar_este = False
        for basura in IGNORAR_EN_GRUPO:
            if basura == carpeta_lower:
                ignorar_este = True
                break
        if ignorar_este: continue

        # --- SI LLEGAMOS AQUÍ, ES PROBABLEMENTE LA SERIE ---
        
        # Limpieza final del nombre de la serie (ej: "Serie 4k" -> "Serie")
        nombre_final = re.sub(r'\s+4k$', '', carpeta, flags=re.IGNORECASE)
        nombre_final = nombre_final.strip()
        
        return nombre_final

    return "Series Varias" # Fallback

lista_final = ["#EXTM3U"]

def escanear(url, nivel):
    if nivel > PROFUNDIDAD_MAX: return

    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200: return

        # Buscar enlaces en el HTML del servidor (Apache/Nginx listing)
        # Buscamos href="..."
        enlaces = re.findall(r'href=["\'](.*?)["\']', r.text)

        for link_raw in enlaces:
            # Ignorar enlaces de navegación
            if link_raw in ['../', './', '?', '#'] or link_raw.startswith('?'):
                continue
            
            full_link = urljoin(url, link_raw)
            
            # --- CASO A: ARCHIVO DE VIDEO ---
            if any(link_raw.lower().endswith(ext) for ext in EXTENSIONES_VIDEO):
                
                # Filtro estricto (Nada de XXX ni Peliculas mezcladas)
                if not es_contenido_permitido(full_link):
                    continue

                # Preparar Titulo
                titulo = limpiar_texto(link_raw)
                for ext in EXTENSIONES_VIDEO:
                    titulo = titulo.replace(ext, "")
                
                # --- NUEVA LÓGICA DE GRUPO INTELIGENTE ---
                grupo = obtener_grupo_inteligente(full_link)
                
                # Generar entrada M3U
                # Usamos el grupo en el título para mejor visualización
                # Ej: group="Umbrella Academy", title="Umbrella Academy S01E01..."
                entry = f'#EXTINF:-1 tvg-id="" tvg-logo="" group-title="{grupo}",{titulo}\n{full_link}'
                lista_final.append(entry)

            # --- CASO B: CARPETA ---
            elif link_raw.endswith('/'):
                # Filtro previo: Si la carpeta es XXX, ni entramos
                if not es_contenido_permitido(full_link):
                    continue
                    
                escanear(full_link, nivel + 1)

    except Exception as e:
        print(f"⚠️ Error en {url}: {e}")

# ==========================================
# 🚀 EJECUCIÓN
# ==========================================

print(f"--- ESCANEO INTELIGENTE SERVER V2 (SMART GROUPS) ---")
print(f"Host: {HOST}")

urls_objetivo = [urljoin(HOST, ruta) for ruta in RUTAS_A_ESCANEAR]

for url_raiz in urls_objetivo:
    print(f"\n🌍 Iniciando en: {url_raiz}")
    escanear(url_raiz, 1)

print(f"\n✅ FINALIZADO. Episodios encontrados: {len(lista_final)-1}")

with open(ARCHIVO_SALIDA, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lista_final))

print(f"📄 Lista guardada en: {ARCHIVO_SALIDA}")
