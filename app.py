# app.py - VERSIÓN CON LISTA LATERAL QUE SÍ FUNCIONA
import streamlit as st
import pandas as pd
from rdflib import Graph, Namespace
import folium
from streamlit_folium import st_folium
import html

# Configuración
st.set_page_config(
    page_title="Mapa Qoyllur Rit'i",
    page_icon="⛰️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Session state
if 'grafo_cargado' not in st.session_state:
    st.session_state.grafo_cargado = False
    st.session_state.lugares_data = []
    st.session_state.grafo = None
    st.session_state.lugar_seleccionado = None

# Namespaces
EX = Namespace("http://example.org/festividades#")
GEO = Namespace("http://www.w3.org/2003/01/geo/wgs84_pos#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")

# -------------------------------------------------------------------
# FUNCIONES BÁSICAS (igual que antes, simplificadas)
# -------------------------------------------------------------------

def cargar_grafo(url):
    try:
        g = Graph()
        g.parse(url, format="turtle")
        return g, True, f"✅ {len(g)} triples"
    except Exception as e:
        return None, False, f"❌ {str(e)}"

def extraer_lugares(grafo):
    query = """
    PREFIX : <http://example.org/festividades#>
    PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?uri ?nombre ?lat ?lon ?desc
    WHERE {
      ?uri a :Lugar ;
           rdfs:label ?nombre .
      OPTIONAL { ?uri geo:lat ?lat ; geo:long ?lon . }
      OPTIONAL { ?uri :descripcionBreve ?desc . }
    }
    ORDER BY ?nombre
    """
    
    lugares = []
    for row in grafo.query(query):
        lugares.append({
            'uri': str(row.uri),
            'nombre': str(row.nombre),
            'lat': float(row.lat) if row.lat else None,
            'lon': float(row.lon) if row.lon else None,
            'descripcion': str(row.desc) if row.desc else "Sin descripción"
        })
    return lugares

def crear_mapa(lat=-13.53, lon=-71.97, zoom=10, lugar_destacado=None):
    """Crea mapa básico"""
    mapa = folium.Map(location=[lat, lon], zoom_start=zoom, tiles='OpenStreetMap')
    
    # Si hay un lugar para destacar, añadirlo
    if lugar_destacado and lugar_destacado['lat'] and lugar_destacado['lon']:
        folium.Marker(
            [lugar_destacado['lat'], lugar_destacado['lon']],
            popup=f"<b>{lugar_destacado['nombre']}</b>",
            icon=folium.Icon(color='red', icon='star')
        ).add_to(mapa)
    
    return mapa

# -------------------------------------------------------------------
# INTERFAZ PRINCIPAL - ESTO SÍ FUNCIONA
# -------------------------------------------------------------------

st.title("🗺️ Mapa Qoyllur Rit'i")

# Barra lateral para carga de datos
with st.sidebar:
    st.header("📥 Cargar Datos")
    
    ttl_url = st.text_input(
        "URL del grafo TTL:",
        value="https://raw.githubusercontent.com/javier-vz/geo_qoyllurity/main/data/grafo.ttl"
    )
    
    if st.button("Cargar Grafo", type="primary", use_container_width=True):
        with st.spinner("Cargando..."):
            grafo, ok, msg = cargar_grafo(ttl_url)
            if ok:
                st.session_state.grafo = grafo
                st.session_state.lugares_data = extraer_lugares(grafo)
                st.session_state.grafo_cargado = True
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

# Si no hay datos cargados
if not st.session_state.grafo_cargado:
    st.info("👈 Primero carga el grafo desde la barra lateral")
    st.stop()

# ------------------------------------------------------------
# PARTE PRINCIPAL QUE SÍ FUNCIONA: LISTA + MAPA
# ------------------------------------------------------------

# Dividir pantalla: Lista a la izquierda, Mapa a la derecha
col_lista, col_mapa = st.columns([1, 2])

# COLUMNA IZQUIERDA: Lista de lugares CLICKABLE
with col_lista:
    st.header("📍 Lugares")
    
    # Buscador
    buscar = st.text_input("Buscar lugar:", placeholder="Ej: Paucartambo")
    
    # Filtrar lugares
    lugares_filtrados = [
        l for l in st.session_state.lugares_data 
        if not buscar or buscar.lower() in l['nombre'].lower()
    ]
    
    lugares_con_coords = [l for l in lugares_filtrados if l['lat']]
    lugares_sin_coords = [l for l in lugares_filtrados if not l['lat']]
    
    # Mostrar lugares CON coordenadas (clickables)
    if lugares_con_coords:
        st.subheader(f"🟢 Con ubicación ({len(lugares_con_coords)})")
        
        # Botón para limpiar selección
        if st.session_state.get('lugar_seleccionado'):
            if st.button("❌ Limpiar selección", use_container_width=True):
                st.session_state.lugar_seleccionado = None
                st.rerun()
        
        # Lista de lugares como botones clickables
        for lugar in lugares_con_coords:
            # Determinar si este lugar está seleccionado
            seleccionado = (st.session_state.get('lugar_seleccionado') and 
                          st.session_state.lugar_seleccionado['nombre'] == lugar['nombre'])
            
            # Botón para seleccionar el lugar
            if st.button(
                f"📍 {lugar['nombre']}",
                key=f"btn_{lugar['nombre']}",
                type="primary" if seleccionado else "secondary",
                use_container_width=True
            ):
                st.session_state.lugar_seleccionado = lugar
                st.rerun()
            
            # Mostrar mini-info debajo del botón
            if seleccionado:
                with st.expander("Ver detalles", expanded=True):
                    st.write(f"**Descripción:** {lugar['descripcion']}")
                    st.write(f"**Coordenadas:** {lugar['lat']:.4f}, {lugar['lon']:.4f}")
    
    # Mostrar lugares SIN coordenadas (no clickables)
    if lugares_sin_coords:
        st.subheader(f"⚪ Sin ubicación ({len(lugares_sin_coords)})")
        for lugar in lugares_sin_coords[:10]:  # Mostrar solo primeros 10
            st.button(
                f"❓ {lugar['nombre']}",
                disabled=True,
                use_container_width=True,
                help="Faltan coordenadas en el grafo"
            )

# COLUMNA DERECHA: Mapa que REACCIONA a la selección
with col_mapa:
    st.header("🗺️ Mapa")
    
    # Determinar qué mostrar en el mapa
    if st.session_state.get('lugar_seleccionado'):
        lugar = st.session_state.lugar_seleccionado
        st.success(f"📍 Mostrando: **{lugar['nombre']}**")
        
        # Crear mapa centrado en el lugar seleccionado
        mapa = crear_mapa(
            lat=lugar['lat'],
            lon=lugar['lon'],
            zoom=14,
            lugar_destacado=lugar
        )
    else:
        st.info("👈 Selecciona un lugar de la lista")
        # Mapa general centrado en Cusco
        mapa = crear_mapa(lat=-13.53, lon=-71.97, zoom=10)
    
    # Mostrar el mapa
    st_folium(mapa, width=700, height=500)
    
    # Información adicional debajo del mapa
    if st.session_state.get('lugar_seleccionado'):
        lugar = st.session_state.lugar_seleccionado
        with st.expander("📋 Información detallada", expanded=True):
            st.write(f"**Nombre:** {lugar['nombre']}")
            st.write(f"**Coordenadas:** {lugar['lat']:.6f}, {lugar['lon']:.6f}")
            st.write(f"**Descripción:** {lugar['descripcion']}")
            st.write(f"**URI:** `{lugar['uri']}`")

# ------------------------------------------------------------
# SECCIÓN INFERIOR: Estadísticas y controles
# ------------------------------------------------------------

st.divider()

# Estadísticas
col_stats1, col_stats2, col_stats3 = st.columns(3)
with col_stats1:
    st.metric("Total lugares", len(st.session_state.lugares_data))
with col_stats2:
    st.metric("Con coordenadas", len([l for l in st.session_state.lugares_data if l['lat']]))
with col_stats3:
    st.metric("Sin coordenadas", len([l for l in st.session_state.lugares_data if not l['lat']]))

# Instrucciones
with st.expander("ℹ️ Cómo usar esta aplicación"):
    st.markdown("""
    1. **Carga el grafo** desde la barra lateral
    2. **Busca lugares** en la lista izquierda
    3. **Haz click** en cualquier lugar CON coordenadas
    4. **El mapa se centrará** automáticamente en ese lugar
    5. **Usa 'Limpiar selección'** para volver al mapa general
    
    **Notas:**
    - Los botones 🟢 tienen coordenadas y son clickables
    - Los botones ⚪ necesitan añadir coordenadas al grafo
    - El marcador rojo (⭐) indica el lugar seleccionado
    """)

# Pie de página
st.caption("© Mapa interactivo de Qoyllur Rit'i - Datos desde grafo TTL")