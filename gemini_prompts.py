"""Construcción y parseo de prompts para Gemini.

Este módulo separa:
  1. La CONSTRUCCIÓN de los prompts (texto que se envía a la IA)
  2. El PARSEO de la respuesta (para estructurar datos en la UI)

De esta forma, `gemini_client.py` queda enfocado en transporte HTTP y
`app.py` (vista) sólo consume funciones de alto nivel.

Relación con la vista (app.py):
  - build_feature_interpretations_prompt -> Se utiliza en la sección "Interpretaciones de cada variable (IA)".
  - build_short_recommendation_prompt -> Se usa en la tarjeta de "Recomendación breve".
  - build_long_recommendation_prompt -> Se usa antes de generar el bloque PDF y el texto extenso.
  - parse_feature_interpretations_response -> Convierte el texto crudo de Gemini en un dict {feature: interpretacion}.

Si deseas cambiar la redacción de la IA, modifica aquí SIN tocar la vista.
"""
from __future__ import annotations

from typing import Dict, List


# ---------------------------------------------------------------------------
# BUILDERS (Prompts)
# ---------------------------------------------------------------------------

def build_feature_interpretations_prompt(detalles: str) -> str:
    """Prompt para obtener interpretaciones por variable.

    Parametros:
        detalles: Lista formateada (string) con líneas del tipo:
            "feature: descripcion | Valor actual (clip): X.YYY"
    """
    return (
        "Eres un experto en análisis de voz y Parkinson. "
        "A continuación verás una lista de variables extraídas de la voz, con su descripción y su valor actual (clip). "
        "Para cada variable, haz lo siguiente:\n"
        "1. Explica en una sola frase y SIN REPETIR, qué mide esa variable (usa la descripción).\n"
        "2. Da una pequeña recomendación, comentario o feedback positivo sobre la voz, usando sólo el valor actual (clip). "
        "Habla directo al usuario, con lenguaje humano y cálido.\n\n"
        f"Variables:\n{detalles}"
    )


def build_short_recommendation_prompt(paciente: str, sano_p: float, park_p: float) -> str:
    """Prompt para recomendación breve (máx 30 palabras)."""
    return (
        f"Paciente: {paciente}. Probabilidades: Sano {sano_p:.1%}, Parkinson {park_p:.1%}. "
        "Dame una recomendación breve y empática (máx 30 palabras)."
    )


def build_long_recommendation_prompt(paciente: str, sano_p: float, park_p: float) -> str:
    """Prompt para recomendación médica extendida (usado en PDF y vista)."""
    return (
        f"Eres un médico empático experto en Parkinson. Explica al paciente {paciente} "
        f"el resultado de su análisis de voz (Sano: {sano_p:.1%}, Parkinson: {park_p:.1%}), "
        "qué significa para su salud, y da consejos útiles para la vida diaria y cuándo consultar "
        "con un especialista. Máx 170 palabras."
    )


# ---------------------------------------------------------------------------
# PARSER (Respuesta de interpretaciones por variable)
# ---------------------------------------------------------------------------

def parse_feature_interpretations_response(text: str) -> Dict[str, str]:
    """Parsea la respuesta de Gemini para interpretaciones por variable.

    Soporta formatos:
      - Una línea con entradas separadas por ';'
      - Varias líneas con formato 'feature: texto'
      - Líneas con bullets ('-', '*', '•')

    Retorna:
        dict { nombre_feature: descripcion_interpretacion }
    """
    if not text:
        return {}

    lines: List[str] = [l.strip() for l in text.splitlines() if l.strip()]
    # Caso: todo en una sola línea separada por ';'
    if len(lines) == 1 and ';' in lines[0]:
        lines = [seg.strip() for seg in lines[0].split(';') if seg.strip()]

    parsed: Dict[str, str] = {}
    for ln in lines:
        # Remover bullets
        ln = ln.lstrip('-*• ').strip()
        if ':' in ln:
            var, desc = ln.split(':', 1)
            var_key = var.strip()
            desc_val = desc.strip()
            if var_key and desc_val:
                parsed[var_key] = desc_val
    return parsed


__all__ = [
    'build_feature_interpretations_prompt',
    'build_short_recommendation_prompt',
    'build_long_recommendation_prompt',
    'parse_feature_interpretations_response'
]
