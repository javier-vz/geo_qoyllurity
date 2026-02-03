# app_qoyllur_mejorado.py
import streamlit as st
import pandas as pd
from rdflib import Graph, Namespace, URIRef, Literal
import folium
from streamlit_folium import st_folium
from folium import plugins
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
    st.session_state.last_clicked = None

# Namespaces
EX = Namespace("http://example.org/festividades#")
GEO = Namespace("http://www.w3.org/2003/01/geo/wgs84_pos#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")

# -------------------------------------------------------------------
# FUNCIONES DE CONSULTA RELACIONAL
# -------------------------------------------------------------------

def obtener_relaciones_lugar(grafo, uri_lugar):
    """Obtiene todas las relaciones de un lugar desde el grafo"""
    relaciones = {
        'eventos': [],
        'festividades': [],
        'recursos': [],
        'ubicado_en': [],
        'rutas': [],
        'naciones': []
    }
    
    # 1. Eventos que ocurren en este lugar
    query_eventos = f"""
    PREFIX : <http://example.org/festividades#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?evento ?nombre ?descripcion
    WHERE {{
      ?evento a :EventoRitual ;
              rdfs:label ?nombre ;
              :estaEnLugar <{uri_lugar}> .
      OPTIONAL {{ ?evento :descripcionBreve ?descripcion . }}
    }}
    """
    
    for row in grafo.query(query_eventos):
        relaciones['eventos'].append({
            'nombre': str(row.nombre),
            'descripcion': str(row.descripcion) if row.descripcion else None
        })
    
    # 2. Festividades que se celebran aquí
    query_festividades = f"""
    PREFIX : <http://example.org/festividades#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?festividad ?nombre ?descripcion
    WHERE {{
      ?festividad a :Festividad ;
                  rdfs:label ?nombre ;
                  :SeCelebraEn <{uri_lugar}> .
      OPTIONAL {{ ?festividad :descripcionBreve ?descripcion . }}
    }}
    """
    
    for row in grafo.query(query_festividades):
        relaciones['festividades'].append({
            'nombre': str(row.nombre),
            'descripcion': str(row.descripcion) if row.descripcion else None
        })
    
    # 3. Recursos multimedia que documentan este lugar
    query_recursos = f"""
    PREFIX : <http://example.org/festividades#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?recurso ?codigo ?tipo ?ruta
    WHERE {{
      ?recurso a :RecursoMedial ;
               :documentaA <{uri_lugar}> ;
               :codigoRecurso ?codigo ;
               :rutaArchivo ?ruta .
      
      BIND(
        IF(CONTAINS(?codigo, "-FOTO-"), "📸 Foto",
          IF(CONTAINS(?codigo, "-VID-"), "🎥 Video",
            IF(CONTAINS(?codigo, "-AUD-"), "🎧 Audio",
              IF(CONTAINS(?codigo, "-DOC-"), "📄 Documento", "📁 Recurso")
            )
          )
        ) AS ?tipo
      )
    }}
    LIMIT 5
    """
    
    for row in grafo.query(query_recursos):
        relaciones['recursos'].append({
            'codigo': str(row.codigo),
            'tipo': str(row.tipo),
            'ruta': str(row.ruta)
        })
    
    # 4. Lugares en los que está ubicado
    query_ubicado_en = f"""
    PREFIX : <http://example.org/festividades#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?lugarSuperior ?nombre
    WHERE {{
      <{uri_lugar}> :ubicadoEn ?lugarSuperior .
      ?lugarSuperior rdfs:label ?nombre .
    }}
    """
    
    for row in grafo.query(query_ubicado_en):
        relaciones['ubicado_en'].append(str(row.nombre))
    
    # 5. Rutas que pasan por aquí
    query_rutas = f"""
    PREFIX : <http://example.org/festividades#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?ruta ?nombre ?descripcion
    WHERE {{
      {{
        ?ruta a :Ruta ;
              rdfs:label ?nombre ;
              :conduceA <{uri_lugar}> .
      }} UNION {{
        ?ruta a :Ruta ;
              rdfs:label ?nombre ;
              :conectaCon <{uri_lugar}> .
      }}
      OPTIONAL {{ ?ruta :descripcionBreve ?descripcion . }}
    }}
    """
    
    for row in grafo.query(query_rutas):
        relaciones['rutas'].append({
            'nombre': str(row.nombre),
            'descripcion': str(row.descripcion) if row.descripcion else None
        })
    
    # 6. Naciones rituales relacionadas
    query_naciones = f"""
    PREFIX : <http://example.org/festividades#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?nacion ?nombre ?descripcion
    WHERE {{
      ?nacion a :NacionRitual ;
              rdfs:label ?nombre .
      
      {{ ?nacion :relacionadoCon <{uri_lugar}> . }}
      UNION
      {{ ?nacion :tieneBaseEn <{uri_lugar}> . }}
      UNION
      {{ ?nacion :participaEnFestividad ?festividad .
         ?festividad :SeCelebraEn <{uri_lugar}> . }}
      
      OPTIONAL {{ ?nacion :descripcionBreve ?descripcion . }}
    }}
    """
    
    for row in grafo.query(query_naciones):
        relaciones['naciones'].append({
            'nombre': str(row.nombre),
            'descripcion': str(row.descripcion) if row.descripcion else None
        })
    
    return relaciones

def crear_popup_html(lugar, relaciones):
    """Crea HTML enriquecido para el popup con relaciones"""
    
    # Escapar caracteres HTML
    nombre = html.escape(lugar['nombre'])
    descripcion = html.escape(lugar['descripcion'][:200] + "..." if len(lugar['descripcion']) > 200 else lugar['descripcion'])
    
    # Color según tipo
    colores_tipo = {
        'Localidad': '#3498db',
        'Santuario': '#e74c3c',
        'Glaciar': '#1abc9c',
        'Iglesia': '#9b59b6',
        'Ruta': '#e67e22',
        'Lugar': '#2ecc71'
    }
    color = colores_tipo.get(lugar['tipo_general'], '#95a5a6')
    
    html_content = f"""
    <div style="width: 320px; font-family: Arial, sans-serif; max-height: 500px; overflow-y: auto;">
        <!-- Encabezado -->
        <div style="background-color: {color}; color: white; padding: 10px; border-radius: 5px 5px 0 0;">
            <h3 style="margin: 0; font-size: 16px;">{nombre}</h3>
            <p style="margin: 5px 0 0 0; font-size: 12px; opacity: 0.9;">
                {lugar['tipo_especifico'] or lugar['tipo_general']} • Nivel {lugar['nivel']}
            </p>
        </div>
        
        <!-- Cuerpo -->
        <div style="padding: 12px; background-color: #f9f9f9;">
            <!-- Descripción -->
            <div style="margin-bottom: 12px;">
                <p style="margin: 0; font-size: 13px; color: #333;">{descripcion}</p>
            </div>
            
            <!-- Coordenadas -->
            <div style="background-color: #ecf0f1; padding: 8px; border-radius: 4px; margin-bottom: 12px;">
                <p style="margin: 0; font-size: 12px; color: #2c3e50;">
                    📍 Lat: {lugar['lat']:.6f}, Lon: {lugar['lon']:.6f}<br>
                    {f'📍 En: {html.escape(lugar["ubicado_en"])}' if lugar['ubicado_en'] else ''}
                </p>
            </div>
    """
    
    # Sección de Eventos
    if relaciones['eventos']:
        html_content += """
            <div style="margin-bottom: 12px;">
                <h4 style="margin: 0 0 6px 0; font-size: 14px; color: #e74c3c;">🎭 Eventos Rituales</h4>
        """
        for evento in relaciones['eventos'][:3]:  # Mostrar máximo 3
            nombre_evento = html.escape(evento['nombre'])
            html_content += f"""
                <div style="background-color: #ffebee; padding: 6px; margin: 4px 0; border-radius: 3px; border-left: 3px solid #e74c3c;">
                    <p style="margin: 0; font-size: 12px; font-weight: bold;">{nombre_evento}</p>
                    {f'<p style="margin: 2px 0 0 0; font-size: 11px; color: #666;">{html.escape(evento["descripcion"][:80])}...</p>' if evento['descripcion'] else ''}
                </div>
            """
        if len(relaciones['eventos']) > 3:
            html_content += f'<p style="margin: 4px 0 0 0; font-size: 11px; color: #7f8c8d;">+ {len(relaciones["eventos"]) - 3} eventos más</p>'
        html_content += "</div>"
    
    # Sección de Festividades
    if relaciones['festividades']:
        html_content += """
            <div style="margin-bottom: 12px;">
                <h4 style="margin: 0 0 6px 0; font-size: 14px; color: #9b59b6;">🎉 Festividades</h4>
        """
        for fest in relaciones['festividades']:
            nombre_fest = html.escape(fest['nombre'])
            html_content += f"""
                <div style="background-color: #f3e5f5; padding: 6px; margin: 4px 0; border-radius: 3px; border-left: 3px solid #9b59b6;">
                    <p style="margin: 0; font-size: 12px; font-weight: bold;">{nombre_fest}</p>
                </div>
            """
        html_content += "</div>"
    
    # Sección de Recursos Multimedia
    if relaciones['recursos']:
        html_content += """
            <div style="margin-bottom: 12px;">
                <h4 style="margin: 0 0 6px 0; font-size: 14px; color: #3498db;">📁 Recursos Multimedia</h4>
        """
        for recurso in relaciones['recursos'][:2]:  # Mostrar máximo 2
            html_content += f"""
                <div style="background-color: #e3f2fd; padding: 6px; margin: 4px 0; border-radius: 3px; border-left: 3px solid #3498db;">
                    <p style="margin: 0; font-size: 12px;">{recurso['tipo']}: {html.escape(recurso['codigo'])}</p>
                </div>
            """
        if len(relaciones['recursos']) > 2:
            html_content += f'<p style="margin: 4px 0 0 0; font-size: 11px; color: #7f8c8d;">+ {len(relaciones["recursos"]) - 2} recursos más</p>'
        html_content += "</div>"
    
    # Sección de Rutas
    if relaciones['rutas']:
        html_content += """
            <div style="margin-bottom: 12px;">
                <h4 style="margin: 0 0 6px 0; font-size: 14px; color: #e67e22;">🛣️ Rutas</h4>
        """
        for ruta in relaciones['rutas']:
            nombre_ruta = html.escape(ruta['nombre'])
            html_content += f"""
                <div style="background-color: #fff3e0; padding: 6px; margin: 4px 0; border-radius: 3px; border-left: 3px solid #e67e22;">
                    <p style="margin: 0; font-size: 12px; font-weight: bold;">{nombre_ruta}</p>
                </div>
            """
        html_content += "</div>"
    
    # Pie de popup
    html_content += f"""
            <!-- Información adicional -->
            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #ddd; font-size: 10px; color: #95a5a6;">
                <p style="margin: 0;">
                    📌 Haz click fuera para cerrar<br>
                    URI: {lugar['uri'].split('#')[-1][:30]}...
                </p>
            </div>
        </div>
    </div>
    """
    
    return html_content

# -------------------------------------------------------------------
# FUNCIONES PRINCIPALES
# -------------------------------------------------------------------

def cargar_grafo_desde_url(url):
    """Carga el grafo TTL desde una URL"""
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
    
    SELECT DISTINCT ?uri ?nombre ?lat ?lon ?tipoEspecifico ?tipoGeneral 
           ?descBreve ?nivelEmbeddings ?ubicadoEn ?nombreUbicadoEn
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
              IF(EXISTS{?uri rdf:type :Iglesia}, "Iglesia",
                IF(EXISTS{?uri rdf:type :Ruta}, "Ruta", "Lugar")
              )
            )
          )
        ) AS ?tipoGeneral
      )
      
      OPTIONAL { ?uri :descripcionBreve ?descBreve . }
      OPTIONAL { ?uri :nivelEmbeddings ?nivelEmbeddings . }
      OPTIONAL { 
        ?uri :ubicadoEn ?ubicadoEn .
        ?ubicadoEn rdfs:label ?nombreUbicadoEn .
      }
    }
    ORDER BY ?tipoGeneral ?nombre
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
            'descripcion': str(row.descBreve) if row.descBreve else "Sin descripción",
            'nivel': str(row.nivelEmbeddings) if row.nivelEmbeddings else "No especificado",
            'ubicado_en': str(row.nombreUbicadoEn) if row.nombreUbicadoEn else None
        })
    
    return resultados

def crear_mapa_interactivo(grafo, lugares_data, center_lat=-13.53, center_lon=-71.97, zoom=10):
    """Crea un mapa Folium con popups enriquecidos - VERSIÓN CORREGIDA"""
    
    # Filtrar lugares con coordenadas
    lugares_con_coords = [l for l in lugares_data if l['lat'] and l['lon']]
    
    if not lugares_con_coords:
        return folium.Map(location=[center_lat, center_lon], zoom_start=zoom)
    
    # IMPORTANTE: Usar tiles que FUNCIONEN
    # OpenStreetMap es el más confiable
    mapa = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom,
        tiles='OpenStreetMap',  # Tile confiable que siempre funciona
        control_scale=True
    )
    
    # Añadir capas alternativas (pero OpenStreetMap como base)
    folium.TileLayer(
        tiles='CartoDB positron',
        attr='CartoDB',
        name='🗺️ Mapa Claro',
        overlay=False,
        control=True
    ).add_to(mapa)
    
    folium.TileLayer(
        tiles='CartoDB dark_matter',
        attr='CartoDB',
        name='🌙 Mapa Oscuro',
        overlay=False,
        control=True
    ).add_to(mapa)
    
    # Configurar iconos personalizados
    icon_configs = {
        'Localidad': {'color': 'blue', 'icon': 'home', 'prefix': 'fa'},
        'Santuario': {'color': 'red', 'icon': 'star', 'prefix': 'fa'},
        'Glaciar': {'color': 'lightblue', 'icon': 'mountain', 'prefix': 'fa'},
        'Iglesia': {'color': 'purple', 'icon': 'place-of-worship', 'prefix': 'fa'},
        'Ruta': {'color': 'orange', 'icon': 'road', 'prefix': 'fa'},
        'Lugar': {'color': 'green', 'icon': 'map-marker-alt', 'prefix': 'fa'}
    }
    
    # --- Agrupar lugares por coordenadas (solución simple) ---
    from collections import defaultdict
    lugares_por_coordenada = defaultdict(list)
    
    for lugar in lugares_con_coords:
        # Redondear a 4 decimales (~11 metros) para agrupar
        coord_key = (round(lugar['lat'], 4), round(lugar['lon'], 4))
        lugares_por_coordenada[coord_key].append(lugar)
    
    # Añadir marcadores
    for coord_key, lugares_en_punto in lugares_por_coordenada.items():
        lat, lon = coord_key
        
        if len(lugares_en_punto) == 1:
            # Un solo lugar en este punto
            lugar = lugares_en_punto[0]
            relaciones = obtener_relaciones_lugar(grafo, lugar['uri'])
            popup_html = crear_popup_html(lugar, relaciones)
            
            tipo = lugar['tipo_general']
            icon_config = icon_configs.get(tipo, {'color': 'gray', 'icon': 'info-circle', 'prefix': 'fa'})
            
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=350),
                tooltip=f"{lugar['nombre']}",
                icon=folium.Icon(
                    color=icon_config['color'],
                    icon=icon_config['icon'],
                    prefix=icon_config['prefix']
                )
            ).add_to(mapa)
            
        else:
            # Múltiples lugares en mismo punto - MOSTRAR TODOS
            # Determinar color principal
            color_principal = 'blue'  # default
            
            # Prioridad de colores
            for lugar in lugares_en_punto:
                if lugar['tipo_general'] == 'Iglesia':
                    color_principal = 'purple'
                    break
                elif lugar['tipo_general'] == 'Santuario':
                    color_principal = 'red'
                    break
                elif lugar['tipo_general'] == 'Localidad':
                    color_principal = 'blue'
            
            # Crear popup SIMPLE que funcione
            nombres_html = ""
            for i, lugar in enumerate(lugares_en_punto):
                icono = '📍'
                if lugar['tipo_general'] == 'Localidad':
                    icono = '🏘️'
                elif lugar['tipo_general'] == 'Iglesia':
                    icono = '⛪'
                elif lugar['tipo_general'] == 'Santuario':
                    icono = '🛐'
                
                nombres_html += f'<div style="padding: 4px; border-bottom: 1px solid #eee;">{icono} <strong>{html.escape(lugar["nombre"])}</strong><br><small>{lugar["tipo_general"]}</small></div>'
            
            popup_html = f"""
            <div style="width: 250px; font-family: Arial;">
                <div style="background: {color_principal}; color: white; padding: 10px; border-radius: 5px 5px 0 0;">
                    <strong>📍 {len(lugares_en_punto)} lugares</strong><br>
                    <small>Misma ubicación</small>
                </div>
                <div style="padding: 10px; background: white; max-height: 300px; overflow-y: auto;">
                    {nombres_html}
                    <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #ddd; font-size: 11px; color: #777;">
                        Lat: {lat:.4f}, Lon: {lon:.4f}
                    </div>
                </div>
            </div>
            """
            
            # Marcador especial para múltiples lugares
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"{len(lugares_en_punto)} lugares aquí",
                icon=folium.Icon(
                    color=color_principal,
                    icon='layer-group',
                    prefix='fa'
                )
            ).add_to(mapa)
    
    # Añadir control de capas
    folium.LayerControl().add_to(mapa)
    
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
    
    if st.button("📥 Cargar Datos", type="primary", use_container_width=True):
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
        
        # Tipo más común
        if st.session_state.lugares_data:
            tipos = pd.DataFrame(st.session_state.lugares_data)['tipo_general'].value_counts()
            tipo_mas_comun = tipos.index[0] if len(tipos) > 0 else "N/A"
            st.metric("Tipo Principal", tipo_mas_comun)

# Contenido principal
st.title("🗺️ Mapa Interactivo - Qoyllur Rit'i")
st.markdown("### Explora lugares rituales con sus relaciones del grafo de conocimiento")

if not st.session_state.grafo_cargado:
    # Pantalla de bienvenida
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("https://cdn-icons-png.flaticon.com/512/825/825526.png", width=120)
        st.markdown("""
        ### Bienvenido
        
        **Para comenzar:**
        1. Verifica la URL del grafo en la barra lateral
        2. Haz clic en **"Cargar Datos"**
        3. Explora los lugares haciendo click en los marcadores
        
        **✨ Nuevas características:**
        - Popups con información relacional
        - Eventos, festividades y recursos multimedia
        - Iconos personalizados por tipo
        """)
else:
    # Controles del mapa
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown("**Haz click en cualquier marcador para ver relaciones detalladas**")
    with col2:
        centro_lat = st.number_input("Latitud", value=-13.53, key="lat_map")
    with col3:
        centro_lon = st.number_input("Longitud", value=-71.97, key="lon_map")
    
    # Crear y mostrar mapa
    mapa = crear_mapa_interactivo(
        st.session_state.grafo,
        st.session_state.lugares_data,
        centro_lat,
        centro_lon,
        10
    )
    
    # Mostrar mapa y capturar interacciones
    mapa_data = st_folium(
        mapa,
        width=1200,
        height=600,
        returned_objects=["last_clicked", "last_object_clicked"]
    )
    
    # Panel de información de click
    if mapa_data and mapa_data.get("last_object_clicked"):
        clicked_lat = mapa_data["last_object_clicked"]["lat"]
        clicked_lon = mapa_data["last_object_clicked"]["lng"]
        
        # Encontrar el lugar clickeado más cercano
        lugar_mas_cercano = None
        min_distancia = float('inf')
        
        for lugar in st.session_state.lugares_data:
            if lugar['lat'] and lugar['lon']:
                distancia = ((lugar['lat'] - clicked_lat)**2 + (lugar['lon'] - clicked_lon)**2)**0.5
                if distancia < min_distancia and distancia < 0.01:  # Radio de 0.01 grados
                    min_distancia = distancia
                    lugar_mas_cercano = lugar
        
        if lugar_mas_cercano:
            st.session_state.last_clicked = lugar_mas_cercano
            
            # Mostrar panel detallado
            st.markdown("---")
            st.subheader(f"📋 Información Detallada: {lugar_mas_cercano['nombre']}")
            
            # Obtener relaciones para este lugar
            relaciones = obtener_relaciones_lugar(
                st.session_state.grafo, 
                lugar_mas_cercano['uri']
            )
            
            # Crear columnas para información
            col_info1, col_info2, col_info3 = st.columns(3)
            
            with col_info1:
                st.metric("Tipo", lugar_mas_cercano['tipo_general'])
                if lugar_mas_cercano['ubicado_en']:
                    st.write(f"**Ubicado en:** {lugar_mas_cercano['ubicado_en']}")
            
            with col_info2:
                st.metric("Nivel", lugar_mas_cercano['nivel'])
                st.write(f"**Coordenadas:** {lugar_mas_cercano['lat']:.6f}, {lugar_mas_cercano['lon']:.6f}")
            
            with col_info3:
                st.metric("Eventos", len(relaciones['eventos']))
                st.metric("Recursos", len(relaciones['recursos']))
            
            # Mostrar relaciones en expanders
            if relaciones['eventos']:
                with st.expander(f"🎭 Eventos Rituales ({len(relaciones['eventos'])})", expanded=True):
                    for evento in relaciones['eventos']:
                        st.write(f"**• {evento['nombre']}**")
                        if evento['descripcion']:
                            st.caption(f"{evento['descripcion']}")
            
            if relaciones['festividades']:
                with st.expander(f"🎉 Festividades ({len(relaciones['festividades'])})"):
                    for fest in relaciones['festividades']:
                        st.write(f"**• {fest['nombre']}**")
            
            if relaciones['recursos']:
                with st.expander(f"📁 Recursos Multimedia ({len(relaciones['recursos'])})"):
                    for recurso in relaciones['recursos']:
                        st.write(f"**{recurso['tipo']}:** {recurso['codigo']}")
                        if recurso['ruta'] and ('http' in recurso['ruta'] or '/' in recurso['ruta']):
                            st.caption(f"Ruta: {recurso['ruta']}")
            
            if relaciones['rutas']:
                with st.expander(f"🛣️ Rutas ({len(relaciones['rutas'])})"):
                    for ruta in relaciones['rutas']:
                        st.write(f"**• {ruta['nombre']}**")
                        if ruta['descripcion']:
                            st.caption(f"{ruta['descripcion']}")
    
    # Leyenda del mapa
    st.markdown("---")
    col_leyenda1, col_leyenda2 = st.columns(2)
    
    with col_leyenda1:
        st.markdown("""
        **🎨 Leyenda de Iconos:**
        - 🔵 **Localidad**: Lugares poblados (Paucartambo, Tayancani)
        - 🔴 **Santuario**: Espacios sagrados principales
        - 🟢 **Glaciar**: Áreas de hielo ritual (Colque Punku)
        - 🟣 **Iglesia**: Templos y capillas
        - 🟠 **Ruta**: Caminos y trayectos rituales
        """)
    
    with col_leyenda2:
        st.markdown("""
        **📊 Niveles de Importancia:**
        - **A**: Entidades centrales (siempre en respuestas)
        - **B**: Contextuales (enriquecen contexto)
        - **C**: Estructurales (no aparecen en respuestas)
        
        *Los popups muestran relaciones del grafo TTL*
        """)

# Pie de página
st.markdown("---")
st.caption("""
**Mapa Interactivo Relacional de Qoyllur Rit'i** | 
Datos extraídos en tiempo real del grafo TTL | 
Popups muestran eventos, festividades y recursos relacionados
""")