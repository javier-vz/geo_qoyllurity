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
    """Crea un mapa Folium con popups enriquecidos"""
    
    # Filtrar lugares con coordenadas
    lugares_con_coords = [l for l in lugares_data if l['lat'] and l['lon']]
    
    if not lugares_con_coords:
        return folium.Map(location=[center_lat, center_lon], zoom_start=zoom)
    
    # Crear mapa base
    mapa = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom,
        tiles='CartoDB positron',
        control_scale=True
    )
    
    # Configurar iconos personalizados
    icon_configs = {
        'Localidad': {'color': 'blue', 'icon': 'home', 'prefix': 'fa'},
        'Santuario': {'color': 'red', 'icon': 'star', 'prefix': 'fa'},
        'Glaciar': {'color': 'lightblue', 'icon': 'mountain', 'prefix': 'fa'},
        'Iglesia': {'color': 'purple', 'icon': 'place-of-worship', 'prefix': 'fa'},
        'Ruta': {'color': 'orange', 'icon': 'road', 'prefix': 'fa'},
        'Lugar': {'color': 'green', 'icon': 'map-marker-alt', 'prefix': 'fa'}
    }
    
    # --- NUEVO: Controlar coordenadas duplicadas ---
    from collections import defaultdict
    coordenadas_vistas = defaultdict(int)
    
    # Añadir marcadores con popups enriquecidos
    for lugar in lugares_con_coords:
        # Obtener relaciones para este lugar
        relaciones = obtener_relaciones_lugar(grafo, lugar['uri'])
        
        # Crear popup HTML con relaciones
        popup_html = crear_popup_html(lugar, relaciones)
        
        # Configurar icono
        tipo = lugar['tipo_general']
        icon_config = icon_configs.get(tipo, {'color': 'gray', 'icon': 'info-circle', 'prefix': 'fa'})
        
        # --- NUEVO: Manejar coordenadas duplicadas ---
        coord_key = (round(lugar['lat'], 6), round(lugar['lon'], 6))
        desplazamiento = 0
        
        # Si ya hay un marcador en estas coordenadas, desplazar ligeramente
        if coordenadas_vistas[coord_key] > 0:
            # Desplazar en un patrón circular
            angle = coordenadas_vistas[coord_key] * 0.1  # Radianes
            desplazamiento_lat = 0.001 * (coordenadas_vistas[coord_key] % 3)
            desplazamiento_lon = 0.001 * (coordenadas_vistas[coord_key] // 3)
            
            lat_final = lugar['lat'] + desplazamiento_lat
            lon_final = lugar['lon'] + desplazamiento_lon
            desplazamiento = coordenadas_vistas[coord_key]
        else:
            lat_final = lugar['lat']
            lon_final = lugar['lon']
        
        # Incrementar contador para estas coordenadas
        coordenadas_vistas[coord_key] += 1
        
        # Añadir indicador de desplazamiento al tooltip si es necesario
        tooltip_text = f"📍 {lugar['nombre']}"
        if desplazamiento > 0:
            tooltip_text += f" (desplazado {desplazamiento})"
        
        # Crear marcador
        folium.Marker(
            location=[lat_final, lon_final],
            popup=folium.Popup(popup_html, max_width=350, max_height=500),
            tooltip=tooltip_text,
            icon=folium.Icon(
                color=icon_config['color'],
                icon=icon_config['icon'],
                prefix=icon_config['prefix']
            )
        ).add_to(mapa)
    
    # --- NUEVO: Añadir capa de relieve (mejor visualización) ---
    folium.TileLayer(
        tiles='https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
        attr='OpenTopoMap',
        name='🗺️ Topografía',
        overlay=False,
        control=True
    ).add_to(mapa)
    
    folium.TileLayer(
        tiles='Stamen Terrain',
        attr='Stamen Terrain',
        name='🏔️ Relieve',
        overlay=False,
        control=True
    ).add_to(mapa)
    
    # Añadir clustering para muchos marcadores
    if len(lugares_con_coords) > 15:
        marker_cluster = plugins.MarkerCluster(
            name="Lugares",
            options={
                'maxClusterRadius': 50,
                'iconCreateFunction': '''
                function(cluster) {
                    var count = cluster.getChildCount();
                    var size = count < 10 ? 'small' : count < 50 ? 'medium' : 'large';
                    return L.divIcon({
                        html: '<div style="background-color: rgba(52, 152, 219, 0.7); color: white; border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; font-weight: bold;">' + count + '</div>',
                        className: 'marker-cluster-' + size,
                        iconSize: new L.Point(40, 40)
                    });
                }
                '''
            }
        ).add_to(mapa)
        
        for lugar in lugares_con_coords:
            relaciones = obtener_relaciones_lugar(grafo, lugar['uri'])
            popup_html = crear_popup_html(lugar, relaciones)
            
            folium.Marker(
                [lugar['lat'], lugar['lon']],
                popup=folium.Popup(popup_html, max_width=350)
            ).add_to(marker_cluster)
    
    # Añadir control de capas
    folium.LayerControl().add_to(mapa)
    
    # --- NUEVO: Añadir mini mapa ---
    plugins.MiniMap(position='bottomright').add_to(mapa)
    
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