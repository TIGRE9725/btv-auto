import requests
import re
import urllib.parse
import os
from urllib.parse import urljoin

# ==========================================
# ⚙️ CONFIGURACIÓN SERIES (LISTA BLANCA)
# ==========================================

HOST = os.environ.get("URL_SERVER_IP")
if not HOST: HOST = "http://15.235.51.60"

RUTAS_A_ESCANEAR = [
    "/contenido/",
    "/server2/contenido/",
    "/server3/contenido/series/" # En esta carpeta específica, podríamos relajar el filtro, pero mejor ser estrictos globalmente
]

ARCHIVO_SALIDA = "lista_server_series.m3u"
PROFUNDIDAD_MAX = 8

# 1. LISTA NEGRA (Lo que NUNCA debe entrar, prioridad máxima)
PROHIBIDO = [
    "XXX", "xxx", "ADULT", "18+", "PORN", "XVIDEOS", "HENTAI", "SEX", "sex", "peliculas", "Peliculas", "PELICULAS", "CINE%20CAM", "PELICULAS%204K", "PELICULAS%2060%20FPS", "SAGA", "CINECAN", "CLASICAST", "ESTRENOS%20PELICULAS%202", "KIDS", "MEXICANAST", "Navidad", "PELICULAS%2060%20FPS", "PELICULAS%202023", "PELICULAS2024", "PELICULAS%20DC", "PELICULAS%20DE%20TEMPORADA%20HALLOWEEN",
]

# 2. LISTA BLANCA (SOLO entra si tiene alguna de estas palabras)
# Aquí pegué TU LISTA exacta. Si una carpeta no tiene esto, SE IGNORA.
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

EXTENSIONES_VIDEO = ('.mp4', '.mkv', '.avi', '.ts', '.m3u8')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

urls_visitadas = set()
lista_final = []

session = requests.Session()
session.headers.update(HEADERS)

def limpiar_texto(texto):
    texto = urllib.parse.unquote(texto)
    texto = texto.replace("_", " ").replace(".", " ")
    return texto.strip()

def es_contenido_prohibido(texto):
    """Filtro de Seguridad (Anti-Porn)"""
    texto_lower = texto.lower()
    for mala in PROHIBIDO:
        if mala.lower() in texto_lower:
            return True
    return False

def es_contenido_permitido(texto):
    """
    Filtro de Inclusión (Solo Series).
    Devuelve True si el texto contiene alguna palabra de la lista PERMITIDOS.
    """
    # Si la lista de permitidos está vacía, dejamos pasar todo (modo inseguro)
    if not PERMITIDOS: return True
    
    texto_lower = texto.lower()
    for buena in PERMITIDOS:
        if buena.lower() in texto_lower:
            return True
    return False

def obtener_grupo_serie(url_completa):
    try:
        partes = url_completa.split("/")
        carpeta_inmediata = limpiar_texto(partes[-2])
        
        es_temporada = re.search(r'(?i)(Season|Temporada|Volume|S\d+|T\d+|Libro)', carpeta_inmediata)
        
        if es_temporada and len(partes) >= 3:
            nombre_serie = limpiar_texto(partes[-3])
        else:
            nombre_serie = carpeta_inmediata

        if nombre_serie.lower() in ["contenido", "series", "server2", "server3", "4kl", "peliculas"]:
            return "SERIES - VARIAS"
            
        return f"SERIES - {nombre_serie}"
    except:
        return "SERIES - VARIAS"

def escanear(url, nivel):
    if nivel > PROFUNDIDAD_MAX: return
    if url in urls_visitadas: return
    
    urls_visitadas.add(url)
    print(f"📂 Escaneando: {url}")

    try:
        r = session.get(url, timeout=10)
        if r.status_code != 200: return
        
        html = r.text
        enlaces = re.findall(r'href=["\']([^"\']+)["\']', html)
        
        for link_raw in enlaces:
            if link_raw in ['../', './', '/', '?C=N;O=D', '?C=M;O=A', '?C=S;O=A', '?C=D;O=A']:
                continue
            
            full_link = urljoin(url, link_raw)
            
            # 1. FILTRO DE SEGURIDAD (Si es XXX, adiós)
            if es_contenido_prohibido(link_raw) or es_contenido_prohibido(full_link):
                continue

            # 2. FILTRO ESTRICTO DE SERIES (Aquí está la magia)
            # Para entrar a una carpeta o guardar un video, DEBE tener una palabra clave de serie.
            # PERO: Las carpetas raíz (/4KL/, /contenido/) no suelen tener esas palabras.
            # Así que aplicamos la lógica:
            # - Si es un VIDEO: Verificamos si la ruta completa cumple con PERMITIDOS.
            # - Si es CARPETA: Entramos para explorar (salvo que sea prohibida), 
            #   la validación real ocurre al encontrar los videos o subcarpetas clave.
            
            # --- CASO A: VIDEO ---
            if full_link.lower().endswith(EXTENSIONES_VIDEO):
                # AQUI ES EL FILTRO FUERTE:
                # Si la URL completa NO tiene ninguna palabra de PERMITIDOS, es una película (John Wick), IGNORAR.
                if not es_contenido_permitido(full_link):
                    # print(f"   🚫 Ignorando Película/Otro: {link_raw}")
                    continue

                titulo = limpiar_texto(link_raw)
                for ext in EXTENSIONES_VIDEO:
                    titulo = titulo.replace(ext, "")
                
                grupo = obtener_grupo_serie(full_link)
                entry = f'#EXTINF:-1 tvg-id="" tvg-logo="" group-title="{grupo}",{titulo}\n{full_link}'
                lista_final.append(entry)

            # --- CASO B: CARPETA ---
            elif link_raw.endswith('/'):
                # Dejamos que explore carpetas genéricas (como /4KL/) 
                # porque dentro podría estar 'Game of Thrones'.
                # Si dentro está 'John Wick', cuando llegue al video .mp4, el filtro de arriba lo matará.
                escanear(full_link, nivel + 1)

    except Exception as e:
        print(f"⚠️ Error en {url}: {e}")

# ==========================================
# 🚀 EJECUCIÓN
# ==========================================

print(f"--- INICIANDO ESCANEO ESTRICTO DE SERIES ---")

urls_objetivo = [urljoin(HOST, ruta) for ruta in RUTAS_A_ESCANEAR]

for url_raiz in urls_objetivo:
    print(f"\n🌍 Iniciando en: {url_raiz}")
    escanear(url_raiz, 1)

print(f"\n✅ FINALIZADO. Episodios encontrados: {len(lista_final)}")

with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    f.write("\n".join(lista_final))

print(f"💾 Guardado en: {ARCHIVO_SALIDA}")
