# app.py - VERSIÓN COMPLETA Y FUNCIONAL
import streamlit as st
import pandas as pd
from rdflib import Graph, Namespace
import folium
from streamlit_folium import st_folium
import html

# Configuración de la página
st.set_page_config(
    page_title="Mapa Qoyllur Rit'i",
    page_icon="⛰️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar session state
if 'grafo_cargado' not in st.session_state:
    st.session_state.grafo_cargado = False
    st.session_state.lugares_data = []
    st.session_state.grafo = None

# Namespaces
EX = Namespace("http://example.org/festividades#")
GEO = Namespace("http://www.w3.org/2003/01/geo/wgs84_pos#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")

# -------------------------------------------------------------------
# FUNCIONES DE CONSULTA
# -------------------------------------------------------------------

def obtener_relaciones_lugar(grafo, uri_lugar):
    """Obtiene relaciones de un lugar desde el grafo"""
    relaciones = {'eventos': [], 'festividades': [], 'recursos': []}
    
    # Eventos
    query = f"""
    PREFIX : <http://example.org/festividades#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?nombre ?descripcion WHERE {{
      ?evento a :EventoRitual ;
              rdfs:label ?nombre ;
              :estaEnLugar <{uri_lugar}> .
      OPTIONAL {{ ?evento :descripcionBreve ?descripcion . }}
    }}
    """
    for row in grafo.query(query):
        relaciones['eventos'].append({'nombre': str(row.nombre), 'descripcion': str(row.descripcion) if row.descripcion else None})
    
    # Festividades
    query = f"""
    PREFIX : <http://example.org/festividades#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?nombre WHERE {{
      ?festividad a :Festividad ;
                  rdfs:label ?nombre ;
                  :SeCelebraEn <{uri_lugar}> .
    }}
    """
    for row in grafo.query(query):
        relaciones['festividades'].append({'nombre': str(row.nombre)})
    
    return relaciones

def crear_popup_html(lugar, relaciones):
    """Crea HTML para el popup"""
    nombre = html.escape(lugar['nombre'])
    descripcion = html.escape(lugar['descripcion'][:150] + "..." if len(lugar['descripcion']) > 150 else lugar['descripcion'])
    
    # Color según tipo
    colores = {'Localidad': '#3498db', 'Iglesia': '#9b59b6', 'Santuario': '#e74c3c', 'Glaciar': '#1abc9c'}
    color = colores.get(lugar['tipo_general'], '#95a5a6')
    
    html_content = f"""
    <div style="width: 300px; font-family: Arial;">
        <div style="background-color: {color}; color: white; padding: 10px; border-radius: 5px 5px 0 0;">
            <h3 style="margin: 0; font-size: 16px;">{nombre}</h3>
            <p style="margin: 5px 0 0 0; font-size: 12px;">
                {lugar['tipo_especifico'] or lugar['tipo_general']}
            </p>
        </div>
        <div style="padding: 12px; background-color: #f9f9f9;">
            <p style="margin: 0; font-size: 13px; color: #333;">{descripcion}</p>
            <div style="margin-top: 10px; padding: 8px; background-color: #ecf0f1; border-radius: 4px;">
                <p style="margin: 0; font-size: 12px; color: #2c3e50;">
                    📍 Lat: {lugar['lat']:.6f}, Lon: {lugar['lon']:.6f}
                </p>
            </div>
    """
    
    if relaciones['eventos']:
        html_content += """
            <div style="margin-top: 12px;">
                <h4 style="margin: 0 0 6px 0; font-size: 14px; color: #e74c3c;">🎭 Eventos</h4>
        """
        for evento in relaciones['eventos'][:2]:
            nombre_evento = html.escape(evento['nombre'])
            html_content += f"""
                <div style="background-color: #ffebee; padding: 6px; margin: 4px 0; border-radius: 3px;">
                    <p style="margin: 0; font-size: 12px; font-weight: bold;">{nombre_evento}</p>
                </div>
            """
        html_content += "</div>"
    
    if relaciones['festividades']:
        html_content += """
            <div style="margin-top: 12px;">
                <h4 style="margin: 0 0 6px 0; font-size: 14px; color: #9b59b6;">🎉 Festividades</h4>
        """
        for fest in relaciones['festividades']:
            html_content += f"""
                <div style="background-color: #f3e5f5; padding: 6px; margin: 4px 0; border-radius: 3px;">
                    <p style="margin: 0; font-size: 12px;">{html.escape(fest['nombre'])}</p>
                </div>
            """
        html_content += "</div>"
    
    html_content += """
        </div>
    </div>
    """
    
    return html_content

# -------------------------------------------------------------------
# FUNCIONES PRINCIPALES
# -------------------------------------------------------------------

def cargar_grafo_desde_url(url):
    """Carga el grafo TTL"""
    try:
        grafo = Graph()
        grafo.parse(url, format="turtle")
        return grafo, True, f"✅ Grafo cargado: {len(grafo)} triples"
    except Exception as e:
        return None, False, f"❌ Error: {str(e)}"

def extraer_lugares(grafo):
    """Extrae todos los lugares del grafo"""
    query = """
    PREFIX : <http://example.org/festividades#>
    PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    
    SELECT DISTINCT ?uri ?nombre ?lat ?lon ?tipoEspecifico ?tipoGeneral ?descBreve
    WHERE {
      ?uri rdf:type/rdfs:subClassOf* :Lugar ;
           rdfs:label ?nombre .
      
      OPTIONAL { ?uri geo:lat ?lat ; geo:long ?lon . }
      
      OPTIONAL {
        ?uri rdf:type ?tipoEspe .
        FILTER(?tipoEspe != :Lugar)
        ?tipoEspe rdfs:label ?tipoEspecifico .
      }
      
      BIND(
        IF(EXISTS{?uri rdf:type :Localidad}, "Localidad",
          IF(EXISTS{?uri rdf:type :Glaciar}, "Glaciar",
            IF(EXISTS{?uri rdf:type :Santuario}, "Santuario",
              IF(EXISTS{?uri rdf:type :Iglesia}, "Iglesia", "Lugar")
            )
          )
        ) AS ?tipoGeneral
      )
      
      OPTIONAL { ?uri :descripcionBreve ?descBreve . }
    }
    ORDER BY ?nombre
    """
    
    resultados = []
    for row in grafo.query(query):
        resultados.append({
            'uri': str(row.uri),
            'nombre': str(row.nombre),
            'lat': float(row.lat) if row.lat else None,
            'lon': float(row.lon) if row.lon else None,
            'tipo_especifico': str(row.tipoEspecifico) if row.tipoEspecifico else None,
            'tipo_general': str(row.tipoGeneral),
            'descripcion': str(row.descBreve) if row.descBreve else "Sin descripción"
        })
    
    return resultados

def crear_mapa_interactivo(grafo, lugares_data):
    """Crea mapa donde CADA lugar tiene su marcador VISIBLE y CLICKABLE"""
    
    # Separar coordenadas duplicadas VISUALMENTE
    from collections import defaultdict
    coordenadas_vistas = defaultdict(int)
    lugares_con_coords = [l for l in lugares_data if l['lat'] and l['lon']]
    
    mapa = folium.Map(
        location=[-13.53, -71.97],
        zoom_start=10,
        tiles='OpenStreetMap'
    )
    
    # Añadir cada lugar
    for lugar in lugares_con_coords:
        # Contar cuántos ya hay en estas coordenadas
        coord_key = (lugar['lat'], lugar['lon'])
        coordenadas_vistas[coord_key] += 1
        num_en_coord = coordenadas_vistas[coord_key]
        
        # Si hay más de uno, separar VISUALMENTE para que se vean todos
        if num_en_coord > 1:
            # Separación pequeña pero visible (0.0003 grados ≈ 33 metros)
            separacion = 0.0003 * (num_en_coord - 1)
            lat = lugar['lat'] + separacion
            lon = lugar['lon'] + separacion
        else:
            lat = lugar['lat']
            lon = lugar['lon']
        
        # Obtener relaciones y crear popup
        relaciones = obtener_relaciones_lugar(grafo, lugar['uri'])
        popup_html = crear_popup_html(lugar, relaciones)
        
        # Color por tipo
        color = 'blue'
        if lugar['tipo_general'] == 'Iglesia':
            color = 'purple'
        elif lugar['tipo_general'] == 'Santuario':
            color = 'red'
        elif lugar['tipo_general'] == 'Glaciar':
            color = 'lightblue'
        
        # Añadir marcador
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=350),
            tooltip=lugar['nombre'],
            icon=folium.Icon(color=color, icon='info-sign')
        ).add_to(mapa)
    
    return mapa

# -------------------------------------------------------------------
# INTERFAZ STREAMLIT
# -------------------------------------------------------------------

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    
    ttl_url = st.text_input(
        "URL del grafo TTL:",
        value="https://raw.githubusercontent.com/javier-vz/geo_qoyllurity/main/data/grafo.ttl"
    )
    
    if st.button("📥 Cargar Datos", type="primary"):
        with st.spinner("Cargando grafo..."):
            grafo, exito, mensaje = cargar_grafo_desde_url(ttl_url)
            
            if exito:
                lugares = extraer_lugares(grafo)
                st.session_state.grafo_cargado = True
                st.session_state.lugares_data = lugares
                st.session_state.grafo = grafo
                st.success(mensaje)
                st.rerun()
            else:
                st.error(mensaje)
    
    if st.session_state.grafo_cargado:
        st.divider()
        st.header("📊 Estadísticas")
        total = len(st.session_state.lugares_data)
        con_coords = len([l for l in st.session_state.lugares_data if l['lat'] and l['lon']])
        st.metric("Total Lugares", total)
        st.metric("Con Coordenadas", con_coords)

# Contenido principal
st.title("🗺️ Mapa Interactivo - Qoyllur Rit'i")

if not st.session_state.grafo_cargado:
    st.info("👈 Haz clic en 'Cargar Datos' en la barra lateral para comenzar")
else:
    # Mostrar mapa
    mapa = crear_mapa_interactivo(st.session_state.grafo, st.session_state.lugares_data)
    st_folium(mapa, width=1200, height=600)
    
    # Mostrar lista de lugares
    st.divider()
    st.subheader("📋 Lugares Cargados")
    
    # Convertir a DataFrame para mostrar
    df = pd.DataFrame(st.session_state.lugares_data)
    if not df.empty:
        st.dataframe(
            df[['nombre', 'tipo_general', 'lat', 'lon']],
            use_container_width=True,
            column_config={
                "nombre": "Nombre",
                "tipo_general": "Tipo",
                "lat": "Latitud",
                "lon": "Longitud"
            }
        )
    
    # Leyenda
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **🎨 Leyenda:**
        - 🔵 **Localidad**: Pueblos y comunidades
        - 🟣 **Iglesia**: Templos y capillas  
        - 🔴 **Santuario**: Espacios sagrados
        - 🔷 **Glaciar**: Áreas de hielo ritual
        """)
    with col2:
        st.markdown("""
        **💡 Notas:**
        - Los marcadores se separan automáticamente si comparten coordenadas
        - Haz click en cualquier marcador para ver detalles
        - Usa el zoom para navegar por el mapa
        """)

# Pie de página
st.caption("Mapa Interactivo de Qoyllur Rit'i | Datos desde grafo de conocimiento TTL")