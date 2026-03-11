"""
conftest.py — configura variables de entorno ANTES de importar la app.
Esto es necesario porque pydantic-settings valida las vars al importar config.py.
"""
import os

# Variables requeridas por pydantic-settings (valores de prueba)
os.environ.setdefault("GOOGLE_API_KEY", "test-key-for-unit-tests")
os.environ.setdefault("QDRANT_HOST", "localhost")
