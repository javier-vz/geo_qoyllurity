# -*- coding: utf-8 -*-
"""
Created on Tue Feb  3 11:43:11 2026

@author: jvera
"""

# create_config.py - Ejecuta este script una vez
import os

# Crear directorio .streamlit si no existe
os.makedirs('.streamlit', exist_ok=True)

# Contenido del config.toml
config_content = '''[server]
maxUploadSize = 50
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false
serverAddress = "localhost"

[theme]
primaryColor = "#3498db"
backgroundColor = "#f8f9fa"
secondaryBackgroundColor = "#ecf0f1"
textColor = "#2c3e50"
font = "sans serif"
'''

# Escribir el archivo
with open('.streamlit/config.toml', 'w', encoding='utf-8') as f:
    f.write(config_content)

print("✅ Archivo .streamlit/config.toml creado exitosamente")