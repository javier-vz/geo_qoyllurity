"""
Script para identificar lugares sin coordenadas y sugerir acciones
"""
import pandas as pd

def verificar_coordenadas_faltantes(lugares_data):
    """Identifica lugares sin coordenadas y sugiere acciones"""
    
    lugares_sin_coords = [l for l in lugares_data if l['lat'] is None or l['lon'] is None]
    
    if not lugares_sin_coords:
        print("✅ Todos los lugares tienen coordenadas definidas.")
        return
    
    print(f"⚠️  {len(lugares_sin_coords)} lugares sin coordenadas:\n")
    
    # Clasificar por tipo para priorizar
    prioridad_alta = ['Santuario', 'Localidad', 'Iglesia']
    prioridad_media = ['LugarRitual', 'Glaciar']
    prioridad_baja = ['Capilla', 'Cementerio', 'Plaza']
    
    for prioridad, tipos in [('ALTA', prioridad_alta), 
                            ('MEDIA', prioridad_media), 
                            ('BAJA', prioridad_baja)]:
        
        lugares_prioridad = [l for l in lugares_sin_coords 
                           if l['tipo_general'] in tipos or 
                           (l['tipo_especifico'] and any(t in l['tipo_especifico'] for t in tipos))]
        
        if lugares_prioridad:
            print(f"\n📋 Prioridad {prioridad}:")
            for lugar in lugares_prioridad[:5]:  # Mostrar solo 5 por categoría
                ubicado_en = f" (en {lugar['ubicado_en']})" if lugar['ubicado_en'] else ""
                print(f"  • {lugar['nombre']} - {lugar['tipo_general']}{ubicado_en}")
            
            if len(lugares_prioridad) > 5:
                print(f"    ... y {len(lugares_prioridad) - 5} más")

# Uso del script
if __name__ == "__main__":
    # Ejemplo de uso
    from cargar_mapa_qoyllur import QoyllurRitiMapa
    
    mapa = QoyllurRitiMapa("https://raw.githubusercontent.com/javier-vz/geo_qoyllurity/main/data/grafo.ttl")
    
    if mapa.cargar_grafo():
        lugares = mapa.extraer_lugares_completos()
        verificar_coordenadas_faltantes(lugares)
        
        # Mostrar estadísticas
        df = pd.DataFrame(lugares)
        print(f"\n📊 Estadísticas:")
        print(f"  Total lugares: {len(df)}")
        print(f"  Con coordenadas: {len(df[df['lat'].notna()])}")
        print(f"  Sin coordenadas: {len(df[df['lat'].isna()])}")
        
        # Lugares más importantes sin coordenadas
        print(f"\n🎯 Lugares Nivel A sin coordenadas:")
        nivel_a_sin_coords = df[(df['nivel'] == 'A') & (df['lat'].isna())]
        for _, row in nivel_a_sin_coords.iterrows():
            print(f"  • {row['nombre']} ({row['tipo_general']})")