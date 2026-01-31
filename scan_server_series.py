import requests
import re
import urllib.parse
import os
from urllib.parse import urljoin

# ==========================================
# ⚙️ CONFIGURACIÓN DE SERIES
# ==========================================

# 1. RECUPERAR IP DEL SECRETO
HOST = os.environ.get("URL_SERVER_IP")
# Fallback por si pruebas en local (borrar en prod si quieres)
if not HOST: HOST = "http://15.235.51.60"

# 2. LAS RUTAS DONDE BUSCAREMOS SERIES
RUTAS_A_ESCANEAR = [
    "/contenido/",
    "/server2/contenido/",
    "/server3/contenido/series/"
]

ARCHIVO_SALIDA = "lista_server_series.m3u"
PROFUNDIDAD_MAX = 8

# 3. FILTROS (Solo bloqueamos Adultos)
# ¡IMPORTANTE! Aquí YA NO están "Season", "Temporada", etc.
PROHIBIDO = [
    "XXX", "xxx", "ADULT", "18+", "PORN", "XVIDEOS", "HENTAI", "SEX", "sex"
]

EXTENSIONES_VIDEO = ('.mp4', '.mkv', '.avi', '.ts', '.m3u8')

# ==========================================
# 🛠️ MOTOR INTELIGENTE
# ==========================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

urls_visitadas = set()
lista_final = []

session = requests.Session()
session.headers.update(HEADERS)

def limpiar_texto(texto):
    """Limpia nombres de archivos y carpetas"""
    texto = urllib.parse.unquote(texto)
    texto = texto.replace("_", " ").replace(".", " ")
    return texto.strip()

def obtener_grupo_serie(url_completa):
    """
    Logica para decidir el nombre de la Serie.
    Estructura típica: .../Nombre Serie/Season X/capitulo.mp4
    """
    try:
        # Rompemos la URL en partes
        partes = url_completa.split("/")
        
        # partes[-1] es el archivo (capitulo.mp4)
        # partes[-2] es la carpeta contenedora (Season 1 o Nombre Serie)
        # partes[-3] es la carpeta anterior (Nombre Serie si hay Season)

        carpeta_inmediata = limpiar_texto(partes[-2])
        
        # Detectamos si la carpeta contenedora es una Temporada
        es_temporada = re.search(r'(?i)(Season|Temporada|Volume|S\d+|T\d+|Libro)', carpeta_inmediata)
        
        if es_temporada and len(partes) >= 3:
            # Si estamos en "Season 1", el nombre de la serie es la carpeta de atrás
            nombre_serie = limpiar_texto(partes[-3])
        else:
            # Si no hay carpeta de Season, asumimos que la carpeta inmediata es la serie
            nombre_serie = carpeta_inmediata

        # Limpieza final por si acaso se coló algo raro
        if nombre_serie.lower() in ["contenido", "series", "server2", "server3"]:
            return "SERIES - VARIAS"
            
        return f"SERIES - {nombre_serie}"

    except:
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
        r = session.get(url, timeout=10)
        if r.status_code != 200: return
        
        html = r.text
        enlaces = re.findall(r'href=["\']([^"\']+)["\']', html)
        
        for link_raw in enlaces:
            if link_raw in ['../', './', '/', '?C=N;O=D', '?C=M;O=A', '?C=S;O=A', '?C=D;O=A']:
                continue
            
            full_link = urljoin(url, link_raw)
            
            # Filtro Anti-XXX
            if es_contenido_prohibido(link_raw) or es_contenido_prohibido(full_link):
                continue

            # CASO A: VIDEO
            if full_link.lower().endswith(EXTENSIONES_VIDEO):
                # 1. Limpiar Título del Capítulo
                titulo = limpiar_texto(link_raw)
                for ext in EXTENSIONES_VIDEO:
                    titulo = titulo.replace(ext, "")
                
                # 2. Calcular el Grupo (Nombre de la Serie)
                grupo = obtener_grupo_serie(full_link)
                
                entry = f'#EXTINF:-1 tvg-id="" tvg-logo="" group-title="{grupo}",{titulo}\n{full_link}'
                lista_final.append(entry)

            # CASO B: CARPETA
            elif link_raw.endswith('/'):
                escanear(full_link, nivel + 1)

    except Exception as e:
        print(f"⚠️ Error en {url}: {e}")

# ==========================================
# 🚀 EJECUCIÓN
# ==========================================

print(f"--- INICIANDO ESCANEO DE SERIES SERVER ---")

# Generar URLs completas
urls_objetivo = [urljoin(HOST, ruta) for ruta in RUTAS_A_ESCANEAR]

for url_raiz in urls_objetivo:
    print(f"\n🌍 Iniciando en: {url_raiz}")
    escanear(url_raiz, 1)

print(f"\n✅ FINALIZADO. Episodios encontrados: {len(lista_final)}")

with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    f.write("\n".join(lista_final))

print(f"💾 Guardado en: {ARCHIVO_SALIDA}")
