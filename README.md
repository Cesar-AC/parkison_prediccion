# 🩺 Parkinson Detector – Voz como biomarcador temprano

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/) 
[![Streamlit Cloud](https://img.shields.io/badge/Streamlit-Cloud-success)](https://streamlit.io/cloud) 
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) 
[![Model: KNN](https://img.shields.io/badge/Model-KNN-blueviolet)](#cómo-funciona)

**Parkinson Detector** es una aplicación web que analiza una grabación de voz de ≥ 5 segundos (vocal sostenida) y, mediante un modelo **K‑Nearest Neighbors** entrenado sobre el *Oxford Parkinson’s Disease Detection Dataset*, estima la probabilidad de enfermedad de Parkinson.  
Incluye un módulo de **IA explicable (XAI)** que genera interpretaciones en lenguaje natural y un informe PDF descargable con todas las métricas.

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

## Cómo funciona

### 1. Extracción de características vocales
* **Parselmouth + Praat** para calcular 14 variables clave (*jitter*, *shimmer*, F0, HNR, PPE, Spread 1/2, RPDE…).  
  * Repo oficial → <https://github.com/YannickJadoul/Parselmouth>  
* Recorte de silencios, normalización y *clipping* a rangos aprendidos durante el entrenamiento.

### 2. Modelo de clasificación
* **K‑Nearest Neighbors** (k = 5, ponderación por distancia) + escalado *Min‑Max*.  
* Validación cruzada estratificada 10‑fold  
  * **Accuracy ≈ 90 %**  
  * **AUC ≈ 0.95**  
  * **MCC ≈ 0.79**  
* Artefactos serializados en `models/modelo_knn.pkl` y `models/scalador.pkl`.

### 3. IA explicable (XAI)
* Importancia de variables por permutación + aproximación **SHAP** para KNN.  
* Generación de explicaciones cortas mediante **Gemini API** [[Docs]](https://ai.google.dev/gemini-api/docs/text-generation) y creación de informe **PDF**.

### 4. Front‑end
* **Streamlit** con un *wizard* de tres pasos, grabación por [`streamlit‑mic‑recorder`](https://pypi.org/project/streamlit-mic-recorder/) y tarjetas de resultado.  
* Diseño inspirado en ejemplos de la comunidad y repos médicos de referencia.

---

## Estructura del proyecto

```text
📦 Parkinson‑Detector
├─ app.py                # interfaz Streamlit
├─ funcion.py            # extracción de features + predicción
├─ models/
│  ├─ modelo_knn.pkl
│  └─ scalador.pkl
├─ entrenamiento/        # notebooks y dataset
│  ├─ Parkiston_Prediccion.ipynb
│  └─ parkinsons.data
├─ requirements.txt
├─ Dockerfile
├─ tests/
├─ docs/                 # capturas y GIFs
└─ README.md

