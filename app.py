# -*- coding: utf-8 -*-
"""
Created on Tue Feb  3 17:04:27 2026

@author: jvera
"""

# app_qoyllur_mejorado.py
import streamlit as st
import pandas as pd
from rdflib import Graph, Namespace, URIRef, Literal
import folium
from streamlit_folium import st_folium
from folium import plugins
import html
import math

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
    """Obtiene relaciones para un lugar - VERSIÓN CON AGRUPACIÓN"""
    
    # Extraer nombre del lugar de la URI para debug
    nombre_lugar = uri_lugar.split('#')[-1] if '#' in uri_lugar else uri_lugar.split('/')[-1]
    print(f"🔍 Buscando relaciones para: {nombre_lugar}")
    
    relaciones = {
        'eventos': [],
        'festividades': [],
        'recursos': [],
        'ubicado_en': [],
        'rutas': [],
        'naciones': []
    }
    
    # 1. Eventos que ocurren en ESTE lugar específico (por URI exacta)
    query_eventos = f"""
    PREFIX : <http://example.org/festividades#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT DISTINCT ?nombre ?descripcion
    WHERE {{
      ?evento a :EventoRitual ;
              rdfs:label ?nombre ;
              :estaEnLugar <{uri_lugar}> .
      OPTIONAL {{ ?evento :descripcionBreve ?descripcion . }}
    }}
    ORDER BY ?nombre
    """
    
    try:
        for row in grafo.query(query_eventos):
            relaciones['eventos'].append({
                'nombre': str(row.nombre),
                'descripcion': str(row.descripcion) if row.descripcion else None
            })
        print(f"  ✅ Eventos encontrados: {len(relaciones['eventos'])}")
    except Exception as e:
        print(f"  ❌ Error en query eventos: {str(e)}")
    
    # 2. Festividades que se celebran en ESTE lugar específico
    query_festividades = f"""
    PREFIX : <http://example.org/festividades#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT DISTINCT ?nombre ?descripcion
    WHERE {{
      ?festividad a :Festividad ;
                  rdfs:label ?nombre ;
                  :SeCelebraEn <{uri_lugar}> .
      OPTIONAL {{ ?festividad :descripcionBreve ?descripcion . }}
    }}
    ORDER BY ?nombre
    """
    
    try:
        for row in grafo.query(query_festividades):
            relaciones['festividades'].append({
                'nombre': str(row.nombre),
                'descripcion': str(row.descripcion) if row.descripcion else None
            })
        print(f"  ✅ Festividades encontradas: {len(relaciones['festividades'])}")
    except Exception as e:
        print(f"  ❌ Error en query festividades: {str(e)}")
    
    # 3. Recursos multimedia que documentan ESTE lugar
    query_recursos = f"""
    PREFIX : <http://example.org/festividades#>
    
    SELECT DISTINCT ?codigo
    WHERE {{
      ?recurso a :RecursoMedial ;
               :documentaA <{uri_lugar}> ;
               :codigoRecurso ?codigo .
    }}
    LIMIT 5
    """
    
    try:
        for row in grafo.query(query_recursos):
            codigo = str(row.codigo)
            # Determinar tipo basado en el código
            if "-FOTO-" in codigo: tipo_recurso = "📸 Foto"
            elif "-VID-" in codigo: tipo_recurso = "🎥 Video"
            elif "-AUD-" in codigo: tipo_recurso = "🎧 Audio"
            elif "-DOC-" in codigo: tipo_recurso = "📄 Documento"
            else: tipo_recurso = "📁 Recurso"
            
            relaciones['recursos'].append({
                'codigo': codigo,
                'tipo': tipo_recurso,
                'ruta': ""
            })
        print(f"  ✅ Recursos encontrados: {len(relaciones['recursos'])}")
    except Exception as e:
        print(f"  ❌ Error en query recursos: {str(e)}")
    
    return relaciones

def crear_popup_html(lugar, relaciones):
    """Crea HTML enriquecido para el popup con relaciones"""
    
    # Escapar caracteres HTML
    nombre = html.escape(lugar['nombre'])
    descripcion = html.escape(lugar['descripcion'])
    
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
    
    # HTML básico que SIEMPRE funciona
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                margin: 0;
                padding: 0;
                font-family: Arial, sans-serif;
                font-size: 14px;
                color: #333;
            }}
            .popup-container {{
                width: 350px;
                max-height: 500px;
                overflow-y: auto;
                padding: 0;
            }}
            .popup-header {{
                background-color: {color};
                color: white;
                padding: 12px;
                border-radius: 5px 5px 0 0;
            }}
            .popup-body {{
                padding: 15px;
                background-color: #f9f9f9;
            }}
            .lugar-info {{
                background: white;
                padding: 10px;
                margin-bottom: 10px;
                border-radius: 5px;
                border-left: 4px solid {color};
            }}
            .section-title {{
                color: {color};
                font-size: 14px;
                font-weight: bold;
                margin: 15px 0 8px 0;
            }}
            .item {{
                background: #f5f5f5;
                padding: 6px;
                margin: 4px 0;
                border-radius: 3px;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="popup-container">
            <div class="popup-header">
                <h3 style="margin: 0; font-size: 16px;">{nombre}</h3>
                <p style="margin: 5px 0 0 0; font-size: 12px; opacity: 0.9;">
                    {lugar['tipo_especifico'] or lugar['tipo_general']} • Nivel {lugar['nivel']}
                </p>
            </div>
            
            <div class="popup-body">
                <!-- Descripción -->
                <div class="lugar-info">
                    <p style="margin: 0; font-size: 13px; line-height: 1.5;">{descripcion}</p>
                </div>
                
                <!-- Coordenadas -->
                <div style="background: #ecf0f1; padding: 10px; border-radius: 5px; margin-bottom: 15px;">
                    <p style="margin: 0; font-size: 12px; color: #2c3e50;">
                        <strong>📍 Coordenadas:</strong> {lugar['lat']:.6f}, {lugar['lon']:.6f}
                    </p>
                    {f'<p style="margin: 5px 0 0 0; font-size: 12px;"><strong>En:</strong> {html.escape(lugar["ubicado_en"])}</p>' if lugar['ubicado_en'] else ''}
                </div>
    """
    
    # Eventos
    if relaciones['eventos']:
        html_content += '<div class="section-title">🎭 Eventos Rituales</div>'
        for evento in relaciones['eventos'][:3]:
            nombre_evento = html.escape(evento['nombre'])
            html_content += f'<div class="item">• {nombre_evento}</div>'
        if len(relaciones['eventos']) > 3:
            html_content += f'<div style="font-size: 11px; color: #777; margin-top: 5px;">+ {len(relaciones["eventos"]) - 3} más</div>'
    
    # Festividades
    if relaciones['festividades']:
        html_content += '<div class="section-title">🎉 Festividades</div>'
        for fest in relaciones['festividades']:
            nombre_fest = html.escape(fest['nombre'])
            html_content += f'<div class="item">• {nombre_fest}</div>'
    
    # Recursos
    if relaciones['recursos']:
        html_content += '<div class="section-title">📁 Recursos Multimedia</div>'
        for recurso in relaciones['recursos'][:2]:
            html_content += f'<div class="item">{recurso["tipo"]}: {html.escape(recurso["codigo"])}</div>'
    
    # Rutas
    if relaciones['rutas']:
        html_content += '<div class="section-title">🛣️ Rutas</div>'
        for ruta in relaciones['rutas']:
            nombre_ruta = html.escape(ruta['nombre'])
            html_content += f'<div class="item">• {nombre_ruta}</div>'
    
    # Cerrar HTML
    html_content += """
            </div>
        </div>
    </body>
    </html>
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
    """Extrae lugares del grafo - EVITANDO DUPLICADOS por producto cartesiano"""
    
    # CONSULTA CORREGIDA: Usar GROUP_CONCAT o tomar solo el primer valor
    query = """
    PREFIX : <http://example.org/festividades#>
    PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    
    SELECT DISTINCT ?uri 
           (MIN(?nombre) as ?primerNombre)  # Toma solo el primer nombre
           ?lat ?lon 
           (MIN(?tipoEspecifico) as ?primerTipoEspe)  # Primer tipo específico
           ?tipoGeneral
           (MIN(?descBreve) as ?primerDesc)  # Primera descripción
           (MIN(?nivelEmbeddings) as ?primerNivel)  # Primer nivel
           (MIN(?nombreUbicadoEn) as ?primerUbicadoEn)  # Primer lugar superior
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
    GROUP BY ?uri ?lat ?lon ?tipoGeneral  # Agrupa por URI y coordenadas
    ORDER BY ?tipoGeneral ?primerNombre
    """
    
    resultados = []
    
    for row in grafo.query(query):
        # Usar MIN() asegura un solo valor por propiedad
        resultados.append({
            'uri': str(row.uri),
            'nombre': str(row.primerNombre) if row.primerNombre else "Sin nombre",
            'lat': float(row.lat) if row.lat else None,
            'lon': float(row.lon) if row.lon else None,
            'tipo_especifico': str(row.primerTipoEspe) if row.primerTipoEspe else None,
            'tipo_general': str(row.tipoGeneral),
            'descripcion': str(row.primerDesc) if row.primerDesc else "Sin descripción",
            'nivel': str(row.primerNivel) if row.primerNivel else "No especificado",
            'ubicado_en': str(row.primerUbicadoEn) if row.primerUbicadoEn else None
        })
    
    print(f"📍 Lugares únicos extraídos: {len(resultados)}")
    
    # Debug: mostrar los primeros 5 lugares
    for i, lugar in enumerate(resultados[:5]):
        print(f"  {i+1}. {lugar['nombre']} - {lugar['uri']}")
    
    return resultados


def crear_mapa_interactivo(grafo, lugares_data, center_lat=-13.53, center_lon=-71.97, zoom=10):
    """Crea un mapa Folium con popups enriquecidos"""
    
    # Filtrar lugares con coordenadas
    lugares_con_coords = [l for l in lugares_data if l['lat'] and l['lon']]
    
    if not lugares_con_coords:
        return folium.Map(location=[center_lat, center_lon], zoom_start=zoom)
    
    # Mapa base
    mapa = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom,
        tiles='CartoDB positron',
        control_scale=True,
        prefer_canvas=True  # Mejor rendimiento
    )
    
    # Configurar iconos
    icon_configs = {
        'Localidad': {'color': 'blue', 'icon': 'home', 'prefix': 'fa'},
        'Santuario': {'color': 'red', 'icon': 'star', 'prefix': 'fa'},
        'Glaciar': {'color': 'lightblue', 'icon': 'mountain', 'prefix': 'fa'},
        'Iglesia': {'color': 'purple', 'icon': 'place-of-worship', 'prefix': 'fa'},
        'Ruta': {'color': 'orange', 'icon': 'road', 'prefix': 'fa'},
        'Lugar': {'color': 'green', 'icon': 'map-marker-alt', 'prefix': 'fa'}
    }
    
    from collections import defaultdict
    
    # Agrupar lugares por coordenadas
    lugares_por_punto = defaultdict(list)
    for lugar in lugares_con_coords:
        key = (round(lugar['lat'], 5), round(lugar['lon'], 5))
        lugares_por_punto[key].append(lugar)
    
    # Contadores para debug
    marcadores_individiales = 0
    marcadores_grupo = 0
    
    # Para cada punto
    for (lat, lon), lugares in lugares_por_punto.items():
        if len(lugares) == 1:
            # Un solo lugar
            lugar = lugares[0]
            relaciones = obtener_relaciones_lugar(grafo, lugar['uri'])
            popup_html = crear_popup_html(lugar, relaciones)
            
            tipo = lugar['tipo_general']
            icon_config = icon_configs.get(tipo, {'color': 'gray', 'icon': 'info-circle', 'prefix': 'fa'})
            
            # Crear iframe para el popup
            iframe = folium.IFrame(
                html=popup_html,
                width=370,    # Ancho en píxeles
                height=500    # Alto en píxeles
            )
            
            # Crear marcador
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(iframe, max_width=370),
                tooltip=f"📍 {lugar['nombre']}",
                icon=folium.Icon(
                    color=icon_config['color'],
                    icon=icon_config['icon'],
                    prefix=icon_config['prefix']
                )
            ).add_to(mapa)
            
            marcadores_individiales += 1
            
        else:
            # Múltiples lugares - crear popup especial
            popup_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{
                        margin: 0;
                        padding: 0;
                        font-family: Arial, sans-serif;
                        font-size: 14px;
                    }}
                    .container {{
                        width: 400px;
                        max-height: 500px;
                        overflow-y: auto;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #f39c12, #e67e22);
                        color: white;
                        padding: 15px;
                        border-radius: 5px 5px 0 0;
                    }}
                    .lugar-card {{
                        background: white;
                        margin: 10px 0;
                        padding: 12px;
                        border-radius: 5px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2 style="margin: 0;">📍 {len(lugares)} lugares aquí</h2>
                        <p style="margin: 5px 0 0 0; font-size: 12px;">
                            Coordenadas: {lat:.6f}, {lon:.6f}
                        </p>
                    </div>
                    <div style="padding: 15px;">
            """
            
            # Añadir cada lugar
            for i, lugar in enumerate(lugares):
                color_lugar = '#3498db' if lugar['tipo_general'] == 'Localidad' else '#9b59b6'
                icono = '🏘️' if lugar['tipo_general'] == 'Localidad' else '⛪'
                
                popup_html += f"""
                <div class="lugar-card" style="border-left: 4px solid {color_lugar};">
                    <div style="display: flex; align-items: center; margin-bottom: 8px;">
                        <div style="background: {color_lugar}; color: white; width: 26px; height: 26px; 
                                 border-radius: 50%; display: flex; align-items: center; 
                                 justify-content: center; margin-right: 10px; font-weight: bold;">
                            {i+1}
                        </div>
                        <div>
                            <h3 style="margin: 0; font-size: 15px; color: #2c3e50;">
                                {icono} {html.escape(lugar['nombre'])}
                            </h3>
                            <p style="margin: 3px 0 0 0; font-size: 12px; color: #666;">
                                {lugar['tipo_general']} • Nivel {lugar['nivel']}
                            </p>
                        </div>
                    </div>
                    <p style="margin: 8px 0; font-size: 13px; color: #444;">
                        {html.escape(lugar['descripcion'])}
                    </p>
                </div>
                """
            
            # Cerrar HTML
            popup_html += """
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Crear iframe para el popup del grupo
            iframe_grupo = folium.IFrame(
                html=popup_html,
                width=420,
                height=550
            )
            
            # Crear marcador para el grupo
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(iframe_grupo, max_width=420),
                tooltip=f"📍 {len(lugares)} lugares",
                icon=folium.Icon(
                    color='orange',
                    icon='layer-group',
                    prefix='fa'
                )
            ).add_to(mapa)
            
            marcadores_grupo += 1
    
    # Añadir capas adicionales
    folium.TileLayer(
        tiles='OpenStreetMap',
        attr='OpenStreetMap',
        name='🗺️ OpenStreetMap',
        overlay=False,
        control=True
    ).add_to(mapa)
    
    # Añadir control de capas
    folium.LayerControl().add_to(mapa)
    
    # Debug info en consola
    print(f"✅ Marcadores individuales: {marcadores_individiales}")
    print(f"✅ Marcadores de grupo: {marcadores_grupo}")
    print(f"✅ Total marcadores: {marcadores_individiales + marcadores_grupo}")
    
    return mapa

# -------------------------------------------------------------------
# INTERFAZ STREAMLIT
# -------------------------------------------------------------------

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    
    ttl_url = st.text_input(
        "URL del grafo TTL:",
        value="https://raw.githubusercontent.com/javier-vz/kg-llm/main/data/grafo.ttl"
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
    # Panel de información de click - VERSIÓN MEJORADA
    # En la sección después de st_folium(), REEMPLAZA el código actual con esto:

    if mapa_data and mapa_data.get("last_object_clicked"):
        clicked_lat = mapa_data["last_object_clicked"]["lat"]
        clicked_lon = mapa_data["last_object_clicked"]["lng"]
        
        # Buscar TODOS los lugares en ese punto exacto
        lugares_en_punto = []
        
        for lugar in st.session_state.lugares_data:
            if lugar['lat'] and lugar['lon']:
                # Usar tolerancia muy pequeña para el mismo punto
                if (abs(lugar['lat'] - clicked_lat) < 0.00001 and 
                    abs(lugar['lon'] - clicked_lon) < 0.00001):
                    lugares_en_punto.append(lugar)
        
        if lugares_en_punto:
            st.markdown("---")
            
            if len(lugares_en_punto) == 1:
                # Un solo lugar
                lugar = lugares_en_punto[0]
                relaciones = obtener_relaciones_lugar(st.session_state.grafo, lugar['uri'])
                
                st.subheader(f"📍 {lugar['nombre']}")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Tipo", lugar['tipo_general'])
                    st.write(f"**Nivel:** {lugar['nivel']}")
                    if lugar['ubicado_en']:
                        st.write(f"**Ubicado en:** {lugar['ubicado_en']}")
                
                with col2:
                    st.metric("Coordenadas", f"{lugar['lat']:.6f}, {lugar['lon']:.6f}")
                    st.write(f"**Tipo específico:** {lugar['tipo_especifico'] or 'N/A'}")
                
                st.write(f"**Descripción:** {lugar['descripcion']}")
                
                # Mostrar relaciones
                if relaciones['eventos']:
                    with st.expander(f"🎭 Eventos ({len(relaciones['eventos'])})"):
                        for evento in relaciones['eventos']:
                            st.write(f"**{evento['nombre']}**")
                            if evento['descripcion']:
                                st.caption(evento['descripcion'])
                
                if relaciones['festividades']:
                    with st.expander(f"🎉 Festividades ({len(relaciones['festividades'])})"):
                        for fest in relaciones['festividades']:
                            st.write(f"**{fest['nombre']}**")
                
            else:
                # Múltiples lugares - mostrar selector
                st.subheader(f"📍 {len(lugares_en_punto)} lugares en este punto")
                
                # Selector para elegir qué lugar ver
                opciones = [f"{l['nombre']} ({l['tipo_general']})" for l in lugares_en_punto]
                seleccion = st.selectbox("Selecciona un lugar para ver detalles:", opciones)
                
                # Obtener el lugar seleccionado
                idx = opciones.index(seleccion)
                lugar_seleccionado = lugares_en_punto[idx]
                relaciones = obtener_relaciones_lugar(st.session_state.grafo, lugar_seleccionado['uri'])
                
                # Mostrar detalles del lugar seleccionado
                st.markdown(f"### {lugar_seleccionado['nombre']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Tipo", lugar_seleccionado['tipo_general'])
                    st.write(f"**Nivel:** {lugar_seleccionado['nivel']}")
                
                with col2:
                    st.metric("Coordenadas", f"{lugar_seleccionado['lat']:.6f}, {lugar_seleccionado['lon']:.6f}")
                
                st.write(f"**Descripción:** {lugar_seleccionado['descripcion']}")
                
                # Mostrar relaciones
                if relaciones['eventos']:
                    with st.expander(f"🎭 Eventos ({len(relaciones['eventos'])})"):
                        for evento in relaciones['eventos']:
                            st.write(f"**{evento['nombre']}**")
                            if evento['descripcion']:
                                st.caption(evento['descripcion'])
    
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