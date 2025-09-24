"""Cliente simple para interactuar con la API de Gemini (Google Generative Language).

Extraído de app.py para desacoplar la vista Streamlit de las llamadas HTTP.

Funciones expuestas:
    get_feature_interpretations(detalles: str) -> str
    get_short_recommendation(paciente: str, sano_p: float, park_p: float) -> str
    get_long_recommendation(paciente: str, sano_p: float, park_p: float) -> str

Nota: Por seguridad se recomienda mover el API key a una variable de entorno
      y leerla con os.getenv('GEMINI_KEY'). Aquí se mantiene literal
      porque así estaba en el código original del usuario.
"""
from __future__ import annotations

import os
import requests
from typing import Optional, Iterable
from pathlib import Path

# Carga manual de .env (sin dependencia externa) si existe en el directorio del proyecto.
# Se parsean líneas KEY=VALUE simples (sin comillas ni escapes avanzados).
def _load_dotenv():
    root = Path(__file__).resolve().parent
    env_path = root / '.env'
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        # Silencioso: si falla no debe romper la app
        pass

_load_dotenv()

# Builders de prompts separados (para mantener este cliente limpio)
try:
    from .gemini_prompts import (
        build_feature_interpretations_prompt,
        build_short_recommendation_prompt,
        build_long_recommendation_prompt,
    )  # type: ignore
except ImportError:
    from gemini_prompts import (
        build_feature_interpretations_prompt,
        build_short_recommendation_prompt,
        build_long_recommendation_prompt,
    )  # type: ignore

# Claves disponibles (failover). Se permiten 3 nombres por compatibilidad.
GEMINI_KEY: str | None = os.getenv("GEMINI_KEY")  # retro-compatibilidad
PRIMARY_ENV = os.getenv("PRIMARY_GEMINI_KEY")
SECONDARY_ENV = os.getenv("SECONDARY_GEMINI_KEY")

_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"


class GeminiError(RuntimeError):
    pass


def _iter_keys() -> Iterable[str]:
        """Devuelve las claves en orden de prioridad.

        Orden:
            1. GEMINI_KEY
            2. PRIMARY_GEMINI_KEY
            3. SECONDARY_GEMINI_KEY
        Filtra duplicados y valores vacíos.
        """
        seen = set()
        for k in [GEMINI_KEY, PRIMARY_ENV, SECONDARY_ENV]:
                if k and k not in seen:
                        seen.add(k)
                        yield k


def _post_prompt(prompt: str, timeout: int = 12) -> str:
    last_error: Optional[Exception] = None
    for key in _iter_keys():
        try:
            res = requests.post(
                _API_URL,
                params={"key": key},
                headers={"Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=timeout,
            )
        except requests.RequestException as e:
            # Error de red, prueba siguiente clave
            last_error = e
            continue

        if res.status_code >= 400:
            # Errores 4xx/5xx: intentar siguiente clave (p.e. 403 quota agotada)
            last_error = GeminiError(
                f"Gemini devolvió {res.status_code} con la clave terminada en ...{key[-6:]}: {res.text[:160]}"
            )
            continue

        data = res.json()
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        return text or ""

    if last_error is None:
        raise GeminiError("No hay claves Gemini configuradas.")
    if isinstance(last_error, GeminiError):
        raise last_error
    raise GeminiError(f"Error de red al llamar Gemini: {last_error}")


def get_feature_interpretations(detalles: str) -> str:
    """Genera interpretaciones por variable.

    'detalles' es el bloque multilinea que arma la vista/servicio con:
        feature: descripcion | Valor actual (clip): X.YYY
    """
    prompt = build_feature_interpretations_prompt(detalles)
    return _post_prompt(prompt, timeout=15)


def get_short_recommendation(paciente: str, sano_p: float, park_p: float) -> str:
    prompt = build_short_recommendation_prompt(paciente, sano_p, park_p)
    return _post_prompt(prompt, timeout=10)


def get_long_recommendation(paciente: str, sano_p: float, park_p: float) -> str:
    prompt = build_long_recommendation_prompt(paciente, sano_p, park_p)
    return _post_prompt(prompt, timeout=18)


__all__ = [
    "GeminiError",
    "get_feature_interpretations",
    "get_short_recommendation",
    "get_long_recommendation",
    "GEMINI_KEY",
]
