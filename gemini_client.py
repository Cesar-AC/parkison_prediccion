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

# Claves gestionadas centralmente
try:
    from .env_keys import PRIMARY_GEMINI_KEY, SECONDARY_GEMINI_KEY  # type: ignore
except ImportError:  # fallback si import relativo falla
    from env_keys import PRIMARY_GEMINI_KEY, SECONDARY_GEMINI_KEY  # type: ignore

# Conserva compatibilidad con código previo que esperaba GEMINI_KEY única
GEMINI_KEY: str | None = os.getenv("GEMINI_KEY") or PRIMARY_GEMINI_KEY

_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"


class GeminiError(RuntimeError):
    pass


def _iter_keys() -> Iterable[str]:
    """Devuelve las claves en orden de prioridad.

    Orden:
      1. Variable de entorno GEMINI_KEY (si existe) para retro-compatibilidad.
      2. PRIMARY_GEMINI_KEY
      3. SECONDARY_GEMINI_KEY
    """
    seen = set()
    for k in [os.getenv("GEMINI_KEY"), PRIMARY_GEMINI_KEY, SECONDARY_GEMINI_KEY]:
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
    """Genera interpretaciones por variable (prompt fijo en español)."""
    prompt = (
        "Eres un experto en análisis de voz y Parkinson. "
        "A continuación verás una lista de variables extraídas de la voz, con su descripción y su valor actual (clip). "
        "Para cada variable, haz lo siguiente:\n"
        "1. Explica en una sola frase y SIN REPETIR, qué mide esa variable (usa la descripción).\n"
        "2. Da una pequeña recomendación, comentario o feedback positivo sobre la voz, usando sólo el valor actual (clip). "
        "Habla directo al usuario, con lenguaje humano y cálido.\n\n"
        f"Variables:\n{detalles}"
    )
    return _post_prompt(prompt, timeout=15)


def get_short_recommendation(paciente: str, sano_p: float, park_p: float) -> str:
    prompt = (
        f"Paciente: {paciente}. Probabilidades: Sano {sano_p:.1%}, Parkinson {park_p:.1%}. "
        "Dame una recomendación breve y empática (máx 30 palabras)."
    )
    return _post_prompt(prompt, timeout=10)


def get_long_recommendation(paciente: str, sano_p: float, park_p: float) -> str:
    prompt = (
        f"Eres un médico empático experto en Parkinson. Explica al paciente {paciente} "
        f"el resultado de su análisis de voz (Sano: {sano_p:.1%}, Parkinson: {park_p:.1%}), "
        "qué significa para su salud, y da consejos útiles para la vida diaria y cuándo consultar "
        "con un especialista. Máx 170 palabras."
    )
    return _post_prompt(prompt, timeout=18)


__all__ = [
    "GeminiError",
    "get_feature_interpretations",
    "get_short_recommendation",
    "get_long_recommendation",
    "GEMINI_KEY",
]
