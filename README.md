# 🩺 Parkinson Detector – Voz como biomarcador temprano

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/) 
[![Streamlit Cloud](https://img.shields.io/badge/Streamlit-Cloud-success)](https://streamlit.io/cloud) 
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) 
[![Model: KNN](https://img.shields.io/badge/Model-KNN-blueviolet)](#cómo-funciona)

**Parkinson Detector** es una aplicación web que analiza una grabación de voz (vocal sostenida ≥ 5 s) y estima la probabilidad de enfermedad de Parkinson usando pipelines de clasificación basados en **Voting / Stacking (SVC y otros modelos)** entrenados sobre el *Oxford Parkinson’s Disease Detection Dataset*. Incorpora:

- Extracción acústica (Parselmouth + Librosa) de 3 indicadores clave optimizados para rapidez: `spread1`, `MDVP:APQ`, `MDVP:Shimmer`.
- Interpretaciones automáticas en lenguaje natural generadas con **Gemini API**.
- Traducción dinámica (multi‑idioma) vía **deep-translator**.
- Informe **PDF clínico estilizado** con diagnóstico, tablas centradas, barra de probabilidades y recomendaciones.
- Interfaz tipo **wizard** simplificada y barra visual de probabilidades en la vista de diagnóstico.


<p align="center">
  <img src="docs/images/demo_workflow.gif" width="620" alt="GIF de la aplicación">
</p>

---

## Demo rápida

1. Accede a la demo desplegada en **Streamlit Cloud** (haz click en el badge superior).  
2. Escribe tu nombre, graba la vocal **“A”** durante ≥ 5 s y pulsa **Analizar**.  
3. Recibe la clasificación (**Saludable / Intermedio / Alto riesgo**) con la explicación de cada variable.  
4. Descarga el **informe PDF** generado automáticamente.  

> La app sigue la guía oficial de despliegue de Streamlit Community Cloud. [[Docs]](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app)  

---

## Arquitectura y flujo

1. **Extracción acústica** (`funcion.py`):
  - Carga audio WAV, recorte de silencios, normalización segura.
  - Parselmouth (Praat) para jitter/shimmer y procesamiento de f0 → cálculo de `spread1`, `MDVP:APQ`, `MDVP:Shimmer`.
  - Clipping a rangos predefinidos para robustez frente a outliers.
2. **Modelos** (`models/*.joblib`):
  - Pipelines pre‑entrenados: Soft Voting y Stacking (incluyen escalado). Por defecto se usa la variante “soft”.
3. **Inferencia**:
  - Se generan probabilidades `[P(Parkinson), P(Sano)]` y se clasifica en tres estados: Saludable, Intermedio, Riesgo.
4. **Interpretaciones IA** (`gemini_client.py` + `gemini_prompts.py`):
  - Construcción de prompt con descripciones neuro‑acústicas.
  - Llamadas a Gemini con failover de múltiples claves.
  - Traducción posterior si el usuario selecciona idioma distinto de español.
5. **PDF clínico** (`pdf_report.py`):
  - Plantilla con encabezado, caja de paciente, tablas centradas, barra visual de probabilidades con porcentajes y bloque de recomendaciones extendidas.
6. **UI Streamlit** (`app.py`):
  - Wizard de 3 pasos (Datos, Grabación, Resultados).
  - Grabación vía `streamlit-mic-recorder` (mínimo 5 s validado) y tarjetas de estado.
  - Descarga de reporte propio + reportes multilingües estáticos.

### Diseño de probabilidades
Se presenta barra segmentada (verde/naranja) con porcentaje superpuesto y, en el PDF, caja de diagnóstico independiente y explicación ampliada.

---

## Estructura del proyecto

```text
📦 Parkinson‑Detector
├─ app.py                # interfaz Streamlit + flujo principal
├─ funcion.py            # extracción de features + predicción (3 variables actuales)
├─ gemini_client.py      # cliente HTTP Gemini + manejo de claves
├─ gemini_prompts.py     # prompts y parser de interpretaciones
├─ pdf_report.py         # generación de PDF estilizado
├─ styles/theme.py       # inyección de CSS base
├─ ui_components/wizard.py # componente visual wizard
├─ models/
│  ├─ soft_voting_parkinson.joblib
│  ├─ stacking_parkinson.joblib
│  └─ svm_mcc_final.joblib (referencia / histórico)
├─ entrenamiento/        # notebook y dataset original
│  ├─ Parkiston_Prediccion_Actualizado.ipynb
│  └─ dataset/parkinsons.data
├─ requirements.txt
├─ tests/
├─ docs/                 # capturas y GIFs
└─ README.md

```


## Instalación

### Requisitos

| Software | Versión |
|----------|---------|
| **Python** | ≥ 3.10 |
| **Praat**  | 6.3 o superior (se instala automáticamente vía Parselmouth) |
| **FFmpeg** | Opcional, para operaciones avanzadas con WAV |

### 1 · Entorno virtual

```bash
git clone https://github.com/Cesar-AC/parkison_prediccion.git
cd parkison_prediccion
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```
Incluye: streamlit, praat-parselmouth, librosa, scikit-learn, soundfile, nolds, xgboost, fpdf2, deep-translator, etc.

### 2 · Variables de entorno (opcional/seguridad)
Crea un archivo `.env` (no lo subas a Git) si quieres usar tus propias claves Gemini y token de ngrok:
```
GEMINI_KEY=xxxxxxxxxxxxxxxx
PRIMARY_GEMINI_KEY=...
SECONDARY_GEMINI_KEY=...
NGROK_AUTH_TOKEN=xxxxxxxx
```

### 3 · Ejecución local
```bash
streamlit run app.py
```
Abre http://localhost:8501 y sigue el wizard.

### 4 · Uso de túnel (ngrok) – opcional
```bash
python ngrok.py
```

---

## Generación de PDF
El módulo `pdf_report.py` produce un informe clínico con:
- Encabezado con fecha y título.
- Caja de datos del paciente.
- Tabla de variables centrada (valores Bruto/Clip + explicación).
- Interpretaciones IA por variable.
- Diagnóstico en caja + barra de probabilidades con porcentajes.
- Recomendaciones ampliadas + texto educativo y disclaimer.

Formato en latín‑1 para compatibilidad; se sanitiza texto para evitar caracteres no soportados.

---

## Traducciones
Se usa `deep-translator` (GoogleTranslator). Política de fallback: ante error se retorna el texto original en español para no romper la UI.

Idiomas actuales: Español (base), Inglés, Portugués, Francés, Chino simplificado.

---

## Buenas prácticas y seguridad
- No subir `.env` ni tokens (Gemini / ngrok).
- API Gemini: se implementa failover de múltiples claves.
- Sanitización de strings en PDF y truncado defensivo de texto largo (> 5000 chars).
- Validación mínima de duración de audio (≥ 4.5 s -> se exige 5 s al usuario).

---

## Roadmap breve
- Añadir gráficos comparativos (barras) en el PDF.
- Resumen semafórico (bajo/medio/alto) dentro del PDF.
- Integración de cache para respuestas IA repetidas.
- Tests unitarios mínimos para extracción de features.

---

## Dataset
Oxford Parkinson’s Disease Detection Dataset
https://archive.ics.uci.edu/ml/datasets/Parkinsons

195 registros (23 pacientes, 8 controles). Se usaron para entrenar varias configuraciones antes de consolidar pipelines Voting/Stacking presentes en `models/`.

## Licencia
MIT. Consulta `LICENSE`. Badges: Shields.io.

## Fuentes consultadas

Parselmouth – “Praat in Python, the Pythonic way”
https://github.com/YannickJadoul/Parselmouth

Streamlit Community Cloud Docs
https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app

UCI Machine Learning Repository – Parkinson’s Dataset
https://archive.ics.uci.edu/ml/datasets/Parkinsons

streamlit‑mic‑recorder – PyPI
https://pypi.org/project/streamlit-mic-recorder/

Gemini API – Text Generation Docs
https://ai.google.dev/gemini-api/docs/text-generation

Shields.io – License Badges
https://gist.github.com/lukas-h/2a5d00690736b4c3a7ba


---

