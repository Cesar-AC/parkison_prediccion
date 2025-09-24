"""Gestión centralizada de claves y variables de entorno.

Define dos claves para Gemini: PRIMARY_GEMINI_KEY y SECONDARY_GEMINI_KEY.
Se leen primero de variables de entorno y, si no existen, se hace fallback a los valores
proporcionados originalmente en el proyecto (no recomendado para producción).

Para configurarlas de forma segura en PowerShell (sesión actual):
    $env:PRIMARY_GEMINI_KEY="TU_CLAVE_1"
    $env:SECONDARY_GEMINI_KEY="TU_CLAVE_2"

Persistente (usuario):
    [Environment]::SetEnvironmentVariable('PRIMARY_GEMINI_KEY','TU_CLAVE_1','User')
    [Environment]::SetEnvironmentVariable('SECONDARY_GEMINI_KEY','TU_CLAVE_2','User')

Luego reinicia la terminal / VS Code para que se apliquen.
"""
from __future__ import annotations
import os

PRIMARY_GEMINI_KEY: str | None = os.getenv(
    "PRIMARY_GEMINI_KEY",
    "AIzaSyAoReEdMLGBFiNG3oS089XrPc2OiW43-Fc",  # fallback legacy
)

SECONDARY_GEMINI_KEY: str | None = os.getenv(
    "SECONDARY_GEMINI_KEY",
    "AIzaSyBRup_GtM7g0Z-_VexcN8zvN-b12fER-0k",  # fallback legacy
)

__all__ = ["PRIMARY_GEMINI_KEY", "SECONDARY_GEMINI_KEY"]
