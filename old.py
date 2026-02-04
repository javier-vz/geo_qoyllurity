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
    page_title="Mapa del Señor de Qoyllur Rit'i",
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
    st.session_state.mapa_cargado = False

# Namespaces
EX = Namespace("http://example.org/festividades#")
GEO = Namespace("http://www.w3.org/2003/01/geo/wgs84_pos#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")

# -------------------------------------------------------------------
# FUNCIONES DE CONSULTA RELACIONAL (MANTENIDAS)
# -------------------------------------------------------------------

def obtener_relaciones_lugar(grafo, uri_lugar):
    """Obtiene relaciones para un lugar - VERSIÓN CON AGRUPACIÓN"""
    
    nombre_lugar = uri_lugar.split('#')[-1] if '#' in uri_lugar else uri_lugar.split('/')[-1]
    
    relaciones = {
        'eventos': [],
        'festividades': [],
        'recursos': [],
        'ubicado_en': [],
        'rutas': [],
        'naciones': []
    }
    
    # 1. Eventos que ocurren en ESTE lugar específico
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
    except Exception as e:
        pass
    
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
    except Exception as e:
        pass
    
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
            if "-FOTO-" in codigo: tipo_recurso = "Foto"
            elif "-VID-" in codigo: tipo_recurso = "Video"
            elif "-AUD-" in codigo: tipo_recurso = "Audio"
            elif "-DOC-" in codigo: tipo_recurso = "Documento"
            else: tipo_recurso = "Recurso"
            
            relaciones['recursos'].append({
                'codigo': codigo,
                'tipo': tipo_recurso,
                'ruta': ""
            })
    except Exception as e:
        pass
    
    return relaciones

def crear_popup_html(lugar, relaciones):
    """Crea HTML enriquecido para el popup con relaciones"""
    
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
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                margin: 0;
                padding: 0;
                font-family: 'Segoe UI', Tahoma, Geneva, sans-serif;
                font-size: 14px;
                color: #333;
                line-height: 1.4;
            }}
            .popup-container {{
                width: 350px;
                max-height: 450px;
                overflow-y: auto;
                padding: 0;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            }}
            .popup-header {{
                background-color: {color};
                color: white;
                padding: 12px 15px;
                border-radius: 8px 8px 0 0;
            }}
            .popup-body {{
                padding: 15px;
                background-color: #ffffff;
            }}
            .info-section {{
                margin-bottom: 12px;
                padding-bottom: 12px;
                border-bottom: 1px solid #eee;
            }}
            .info-section:last-child {{
                border-bottom: none;
            }}
            .section-title {{
                color: {color};
                font-size: 13px;
                font-weight: 600;
                margin: 0 0 8px 0;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .item {{
                background: #f8f9fa;
                padding: 6px 8px;
                margin: 3px 0;
                border-radius: 4px;
                font-size: 12px;
                border-left: 2px solid {color};
            }}
            .coordenadas {{
                background: #f0f7ff;
                padding: 8px 10px;
                border-radius: 6px;
                font-size: 11px;
                color: #2c3e50;
                margin: 10px 0;
            }}
        </style>
    </head>
    <body>
        <div class="popup-container">
            <div class="popup-header">
                <h3 style="margin: 0; font-size: 16px; font-weight: 600;">{nombre}</h3>
                <p style="margin: 4px 0 0 0; font-size: 12px; opacity: 0.9;">
                    {lugar['tipo_especifico'] or lugar['tipo_general']} • Nivel {lugar['nivel']}
                </p>
            </div>
            
            <div class="popup-body">
                <!-- Descripción -->
                <div class="info-section">
                    <p style="margin: 0; font-size: 13px; color: #444;">{descripcion}</p>
                </div>
                
                <!-- Coordenadas -->
                <div class="coordenadas">
                    <div style="font-weight: 600;">Coordenadas:</div>
                    <div>{lugar['lat']:.6f}, {lugar['lon']:.6f}</div>
                    {f'<div style="margin-top: 4px;"><span style="font-weight: 600;">Ubicado en:</span> {html.escape(lugar["ubicado_en"])}</div>' if lugar['ubicado_en'] else ''}
                </div>
    """
    
    # Eventos
    if relaciones['eventos']:
        html_content += '<div class="info-section">'
        html_content += '<div class="section-title">Eventos Rituales</div>'
        for evento in relaciones['eventos'][:3]:
            nombre_evento = html.escape(evento['nombre'])
            html_content += f'<div class="item">• {nombre_evento}</div>'
        if len(relaciones['eventos']) > 3:
            html_content += f'<div style="font-size: 11px; color: #666; margin-top: 5px;">+ {len(relaciones["eventos"]) - 3} eventos más</div>'
        html_content += '</div>'
    
    # Festividades
    if relaciones['festividades']:
        html_content += '<div class="info-section">'
        html_content += '<div class="section-title">Festividades</div>'
        for fest in relaciones['festividades']:
            nombre_fest = html.escape(fest['nombre'])
            html_content += f'<div class="item">• {nombre_fest}</div>'
        html_content += '</div>'
    
    # Recursos
    if relaciones['recursos']:
        html_content += '<div class="info-section">'
        html_content += '<div class="section-title">Recursos Multimedia</div>'
        for recurso in relaciones['recursos'][:2]:
            html_content += f'<div class="item">{recurso["tipo"]}: {html.escape(recurso["codigo"])}</div>'
        html_content += '</div>'
    
    # Cerrar HTML
    html_content += """
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content

# -------------------------------------------------------------------
# FUNCIONES PRINCIPALES (MANTENIDAS)
# -------------------------------------------------------------------

def cargar_grafo_desde_url(url):
    """Carga el grafo TTL desde una URL"""
    try:
        grafo = Graph()
        grafo.parse(url, format="turtle")
        return grafo, True, f"Grafo cargado: {len(grafo)} triples"
    except Exception as e:
        return None, False, f"Error: {str(e)}"

def extraer_lugares(grafo):
    """Extrae lugares del grafo - EVITANDO DUPLICADOS por producto cartesiano"""
    
    query = """
    PREFIX : <http://example.org/festividades#>
    PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    
    SELECT DISTINCT ?uri 
           (MIN(?nombre) as ?primerNombre)
           ?lat ?lon 
           (MIN(?tipoEspecifico) as ?primerTipoEspe)
           ?tipoGeneral
           (MIN(?descBreve) as ?primerDesc)
           (MIN(?nivelEmbeddings) as ?primerNivel)
           (MIN(?nombreUbicadoEn) as ?primerUbicadoEn)
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
    GROUP BY ?uri ?lat ?lon ?tipoGeneral
    ORDER BY ?tipoGeneral ?primerNombre
    """
    
    resultados = []
    
    for row in grafo.query(query):
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
    
    return resultados

def crear_mapa_interactivo(grafo, lugares_data, center_lat=-13.53, center_lon=-71.97, zoom=10, estilo_mapa="Relieve"):
    """Crea un mapa Folium con múltiples estilos de mapa"""
    
    lugares_con_coords = [l for l in lugares_data if l['lat'] and l['lon']]
    
    if not lugares_con_coords:
        return folium.Map(location=[center_lat, center_lon], zoom_start=zoom)
    
    # Seleccionar estilo de mapa según elección
    if estilo_mapa == "Relieve":
        tiles = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        attr = "Esri, Maxar, Earthstar Geographics"
        name = "Imagen satelital"
    elif estilo_mapa == "Topográfico":
        tiles = "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
        attr = "OpenTopoMap"
        name = "Mapa topográfico"
    else:
        tiles = "OpenStreetMap"
        attr = "OpenStreetMap"
        name = "OpenStreetMap"
    
    # Crear mapa base
    mapa = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom,
        tiles=tiles,
        attr=attr,
        control_scale=True,
        prefer_canvas=True
    )
    
    # Añadir capas adicionales
    folium.TileLayer(
        tiles='OpenStreetMap',
        attr='OpenStreetMap',
        name='Mapa básico',
        overlay=False,
        control=True
    ).add_to(mapa)
    
    folium.TileLayer(
        tiles='Stamen Terrain',
        attr='Stamen Terrain',
        name='Relieve',
        overlay=False,
        control=True
    ).add_to(mapa)
    
    folium.TileLayer(
        tiles='Stamen Toner',
        attr='Stamen Toner',
        name='Blanco y negro',
        overlay=False,
        control=True
    ).add_to(mapa)
    
    folium.TileLayer(
        tiles='CartoDB positron',
        attr='CartoDB',
        name='Claro',
        overlay=False,
        control=True
    ).add_to(mapa)
    
    # Configurar iconos
    icon_configs = {
        'Localidad': {'color': 'blue', 'icon': 'home'},
        'Santuario': {'color': 'red', 'icon': 'star'},
        'Glaciar': {'color': 'lightblue', 'icon': 'mountain'},
        'Iglesia': {'color': 'purple', 'icon': 'place-of-worship'},
        'Ruta': {'color': 'orange', 'icon': 'road'},
        'Lugar': {'color': 'green', 'icon': 'map-marker'}
    }
    
    from collections import defaultdict
    
    # Agrupar lugares por coordenadas
    lugares_por_punto = defaultdict(list)
    for lugar in lugares_con_coords:
        if lugar['lat'] and lugar['lon']:
            key = (round(lugar['lat'], 5), round(lugar['lon'], 5))
            lugares_por_punto[key].append(lugar)
    
    # Para cada punto
    for (lat, lon), lugares in lugares_por_punto.items():
        if len(lugares) == 1:
            # Un solo lugar
            lugar = lugares[0]
            relaciones = obtener_relaciones_lugar(grafo, lugar['uri'])
            popup_html = crear_popup_html(lugar, relaciones)
            
            tipo = lugar['tipo_general']
            icon_config = icon_configs.get(tipo, {'color': 'gray', 'icon': 'info-circle'})
            
            # Crear iframe para el popup
            iframe = folium.IFrame(
                html=popup_html,
                width=370,
                height=450
            )
            
            # Crear marcador
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(iframe, max_width=370),
                tooltip=f"{lugar['nombre']}",
                icon=folium.Icon(
                    color=icon_config['color'],
                    icon=icon_config['icon'],
                    prefix='fa'
                )
            ).add_to(mapa)
            
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
                        font-family: 'Segoe UI', sans-serif;
                        font-size: 14px;
                    }}
                    .container {{
                        width: 380px;
                        max-height: 400px;
                        overflow-y: auto;
                        padding: 0;
                    }}
                    .header {{
                        background: #2c3e50;
                        color: white;
                        padding: 12px 15px;
                        border-radius: 6px 6px 0 0;
                    }}
                    .lugar-card {{
                        background: white;
                        margin: 8px 0;
                        padding: 10px;
                        border-radius: 5px;
                        border: 1px solid #e0e0e0;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h3 style="margin: 0; font-size: 15px;">{len(lugares)} lugares en esta ubicación</h3>
                        <p style="margin: 4px 0 0 0; font-size: 11px; opacity: 0.9;">
                            Coordenadas: {lat:.6f}, {lon:.6f}
                        </p>
                    </div>
                    <div style="padding: 12px;">
            """
            
            # Añadir cada lugar
            for i, lugar in enumerate(lugares):
                color_lugar = '#3498db' if lugar['tipo_general'] == 'Localidad' else '#9b59b6'
                
                popup_html += f"""
                <div class="lugar-card" style="border-left: 3px solid {color_lugar};">
                    <div style="display: flex; align-items: center; margin-bottom: 6px;">
                        <div style="background: {color_lugar}; color: white; width: 22px; height: 22px; 
                                 border-radius: 50%; display: flex; align-items: center; 
                                 justify-content: center; margin-right: 8px; font-weight: bold; font-size: 11px;">
                            {i+1}
                        </div>
                        <div>
                            <div style="font-weight: 600; font-size: 13px; color: #2c3e50;">
                                {html.escape(lugar['nombre'])}
                            </div>
                            <div style="font-size: 11px; color: #666;">
                                {lugar['tipo_general']}
                            </div>
                        </div>
                    </div>
                </div>
                """
            
            popup_html += """
                    </div>
                </div>
            </body>
            </html>
            """
            
            iframe_grupo = folium.IFrame(
                html=popup_html,
                width=400,
                height=450
            )
            
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(iframe_grupo, max_width=400),
                tooltip=f"{len(lugares)} lugares",
                icon=folium.Icon(
                    color='orange',
                    icon='layer-group',
                    prefix='fa'
                )
            ).add_to(mapa)
    
    # Añadir control de capas
    folium.LayerControl(position='topleft').add_to(mapa)
    
    return mapa

# -------------------------------------------------------------------
# INTERFAZ STREAMLIT REORGANIZADA - 2 COLUMNAS SUPERIORES
# -------------------------------------------------------------------

# ============================================
# 1. CARGA AUTOMÁTICA DE DATOS (SILENCIOSA)
# ============================================
if not st.session_state.grafo_cargado:
    with st.spinner("Cargando datos del grafo..."):
        ttl_url = "https://raw.githubusercontent.com/javier-vz/kg-llm/main/data/grafo.ttl"
        grafo, exito, mensaje = cargar_grafo_desde_url(ttl_url)
        
        if exito:
            lugares = extraer_lugares(grafo)
            st.session_state.grafo_cargado = True
            st.session_state.lugares_data = lugares
            st.session_state.grafo = grafo
            st.session_state.mapa_cargado = True
        else:
            st.error(f"Error al cargar datos: {mensaje}")

# ============================================
# 2. CABECERA EN 2 COLUMNAS
# ============================================
col_titulo, col_instrucciones = st.columns([2, 1])

with col_titulo:
    # Título principal
    st.markdown("# Mapa Interactivo de la Festividad del Señor de Qoyllur Rit'i")
    
    # Subtítulo
    st.markdown("Exploración interactiva de lugares rituales basada en información registrada durante 2025. La información es parcial y está en proceso de verificación.")

with col_instrucciones:
    # Instrucciones en una tarjeta
    with st.container():
        st.markdown("### Cómo usar el mapa")
        st.markdown("""
        - **Haga click** en cualquier marcador para ver información detallada
        - **Use el control de capas** para cambiar el estilo del mapa
        - **Ajuste el zoom** con los controles o la rueda del mouse
        - **Filtre por tipo** usando el panel lateral
        """)

st.divider()

# ============================================
# 3. CONTROLES DEL MAPA COMPACTOS
# ============================================
col_estilo, col_zoom, col_lat, col_lon, col_centrar = st.columns([2, 2, 2, 2, 1])

with col_estilo:
    estilo_mapa = st.selectbox(
        "**Estilo del mapa**",
        ["Relieve", "Topográfico", "Mapa básico", "Blanco y negro", "Claro"],
        index=0
    )

with col_zoom:
    zoom_level = st.slider("**Nivel de zoom**", 8, 15, 10)

with col_lat:
    centro_lat = st.number_input("**Latitud**", value=-13.53, format="%.4f", key="lat_input")

with col_lon:
    centro_lon = st.number_input("**Longitud**", value=-71.97, format="%.4f", key="lon_input")

with col_centrar:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 **Centrar**", use_container_width=True, type="secondary"):
        st.session_state.mapa_cargado = True
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ============================================
# 4. MAPA PRINCIPAL - GRANDE
# ============================================
if st.session_state.grafo_cargado:
    try:
        # Crear el mapa
        mapa = crear_mapa_interactivo(
            st.session_state.grafo,
            st.session_state.lugares_data,
            centro_lat,
            centro_lon,
            zoom_level,
            estilo_mapa
        )
        
        # Mostrar mapa EN GRANDE
        mapa_data = st_folium(
            mapa,
            width=None,
            height=600,
            returned_objects=["last_clicked", "last_object_clicked"]
        )
        
        # ============================================
        # 5. INFORMACIÓN DE CLICK (DEBAJO DEL MAPA)
        # ============================================
        if mapa_data and mapa_data.get("last_object_clicked"):
            clicked_lat = mapa_data["last_object_clicked"]["lat"]
            clicked_lon = mapa_data["last_object_clicked"]["lng"]
            
            # Buscar lugares en ese punto
            lugares_en_punto = []
            
            for lugar in st.session_state.lugares_data:
                if lugar['lat'] and lugar['lon']:
                    if (abs(lugar['lat'] - clicked_lat) < 0.0001 and 
                        abs(lugar['lon'] - clicked_lon) < 0.0001):
                        lugares_en_punto.append(lugar)
            
            if lugares_en_punto:
                st.divider()
                st.subheader("📍 Información del lugar seleccionado")
                
                if len(lugares_en_punto) == 1:
                    lugar = lugares_en_punto[0]
                    relaciones = obtener_relaciones_lugar(st.session_state.grafo, lugar['uri'])
                    
                    # Mostrar información en columnas compactas
                    col_info1, col_info2 = st.columns([2, 1])
                    
                    with col_info1:
                        st.markdown(f"### {lugar['nombre']}")
                        st.write(f"**Descripción:** {lugar['descripcion']}")
                    
                    with col_info2:
                        st.markdown(f"**Tipo:** {lugar['tipo_general']}")
                        st.markdown(f"**Nivel:** {lugar['nivel']}")
                        if lugar['ubicado_en']:
                            st.markdown(f"**Ubicado en:** {lugar['ubicado_en']}")
                    
                    # Coordenadas
                    st.markdown(f"**Coordenadas:** `{lugar['lat']:.6f}, {lugar['lon']:.6f}`")
                    
                    # Relaciones
                    if relaciones['eventos']:
                        with st.expander(f"📅 Eventos asociados ({len(relaciones['eventos'])})"):
                            for evento in relaciones['eventos']:
                                st.markdown(f"**• {evento['nombre']}**")
                                if evento['descripcion']:
                                    st.caption(evento['descripcion'])
                    
                    if relaciones['festividades']:
                        with st.expander(f"🎉 Festividades ({len(relaciones['festividades'])})"):
                            for fest in relaciones['festividades']:
                                st.markdown(f"**• {fest['nombre']}**")
                    
                else:
                    # Múltiples lugares
                    st.write(f"**Múltiples lugares ({len(lugares_en_punto)}) en esta ubicación**")
                    
                    opciones = [f"{l['nombre']} ({l['tipo_general']})" for l in lugares_en_punto]
                    seleccion = st.selectbox("Seleccionar lugar:", opciones, key="selector_lugar")
                    
                    idx = opciones.index(seleccion)
                    lugar = lugares_en_punto[idx]
                    relaciones = obtener_relaciones_lugar(st.session_state.grafo, lugar['uri'])
                    
                    col_ml1, col_ml2 = st.columns([2, 1])
                    with col_ml1:
                        st.markdown(f"**{lugar['nombre']}**")
                        st.write(lugar['descripcion'])
                    with col_ml2:
                        st.markdown(f"*{lugar['tipo_general']}*")
                        st.caption(f"Nivel: {lugar['nivel']}")
        
    except Exception as e:
        st.error(f"Error al crear el mapa: {str(e)}")
else:
    st.warning("Cargando datos del grafo... por favor espere.")

# ============================================
# 6. INFORMACIÓN DEL PROYECTO (DEBAJO DEL MAPA)
# ============================================
st.divider()
st.markdown("### Información del Proyecto de Investigación")

col_proyecto1, col_proyecto2 = st.columns([1, 2])

with col_proyecto1:
    st.markdown("#### Responsable del Proyecto")
    st.markdown("""
    **Javier Vera Zúñiga**
    
    *Investigador Principal*
    
    Proyecto: *"Grafos de conocimiento para la documentación de festividades andinas: 
    Señor de Qoyllur Rit'i y Virgen del Carmen de Paucartambo"*
    
    Universidad Tecnológica del Perú (UTP)
    """)
    

with col_proyecto2:
    st.markdown("#### Equipo de Investigación")
    
    col_equipo1, col_equipo2 = st.columns(2)
    
    with col_equipo1:
        st.markdown("**🏔️ Paucartambo (Cusco)**")
        st.markdown("""
        -
        """)
    
    with col_equipo2:
        st.markdown("**🏛️ Lima**")
        st.markdown("""
        - 
        """)
    
    st.markdown("#### Objetivo Principal")
    st.markdown("""
    *Desarrollar una infraestructura basada en grafos de conocimiento para organizar y recuperar 
    información patrimonial compleja asociada a las festividades del Señor de Qoyllur Rit'i 
    y la Virgen del Carmen de Paucartambo.*
    """)

# Nota metodológica
st.markdown("---")
st.markdown("""
*Este mapa interactivo forma parte del sistema de visualización del proyecto de investigación, 
mostrando los lugares rituales documentados en el grafo de conocimiento. La información presentada 
se basa en datos recopilados durante 2025-2026 mediante trabajo de campo, entrevistas estructuradas 
y documentación institucional, siguiendo protocolos éticos de consentimiento informado y 
confidencialidad.*
""")

# ============================================
# 7. SIDEBAR CON INFORMACIÓN ADICIONAL
# ============================================
with st.sidebar:
    st.header("Información del dataset")
    
    if st.session_state.grafo_cargado:
        total_lugares = len(st.session_state.lugares_data)
        lugares_con_coords = len([l for l in st.session_state.lugares_data if l['lat'] and l['lon']])
        
        col_metric1, col_metric2 = st.columns(2)
        with col_metric1:
            st.metric("Total lugares", total_lugares)
        with col_metric2:
            st.metric("Con coords", lugares_con_coords)
    
    st.divider()
    
    st.subheader("Tipos de lugares")
    
    tipos_lugares = [
        {"icono": "🏘️", "tipo": "Localidad", "descripcion": "Poblados y comunidades"},
        {"icono": "⛪", "tipo": "Santuario", "descripcion": "Espacios sagrados"},
        {"icono": "🏔️", "tipo": "Glaciar", "descripcion": "Áreas de hielo ritual"},
        {"icono": "✝️", "tipo": "Iglesia", "descripcion": "Templos y capillas"},
        {"icono": "🛣️", "tipo": "Ruta", "descripcion": "Caminos rituales"},
        {"icono": "📍", "tipo": "Lugar", "descripcion": "Otros espacios"}
    ]
    
    for tipo_info in tipos_lugares:
        st.markdown(f"**{tipo_info['icono']} {tipo_info['tipo']}**")
        st.caption(tipo_info['descripcion'])
    
    st.divider()
    
    st.subheader("📈 Distribución por tipo")
    if st.session_state.grafo_cargado and st.session_state.lugares_data:
        df_lugares = pd.DataFrame(st.session_state.lugares_data)
        distribucion = df_lugares['tipo_general'].value_counts()
        
        for tipo, cantidad in distribucion.items():
            porcentaje = (cantidad / total_lugares) * 100
            st.markdown(f"• **{tipo}**: {cantidad} ({porcentaje:.1f}%)")
    
    st.divider()
    
    st.subheader("Niveles de importancia")
    st.markdown("""
    **A**: Entidades centrales  
    **B**: Contextuales  
    **C**: Estructurales
    
    *Basado en el estándar del grafo TTL*
    """)
