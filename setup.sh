#!/bin/bash
# setup.sh - Script de instalación para Streamlit Cloud

# Actualizar pip
python -m pip install --upgrade pip

# Instalar dependencias desde requirements.txt
pip install -r requirements.txt

# Instalar cualquier dependencia adicional necesaria
pip install html5lib==1.1
