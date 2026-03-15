"""
conftest.py — sets environment variables BEFORE importing the app.
This is necessary because pydantic-settings validates the vars when importing config.py.
"""
import os

# Variables required by pydantic-settings (test values)
os.environ.setdefault("GOOGLE_API_KEY", "test-key-for-unit-tests")
os.environ.setdefault("QDRANT_HOST", "localhost")
