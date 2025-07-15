# 🩺 Parkinson Detector – Voz como biomarcador temprano

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/) 
[![Streamlit Cloud](https://img.shields.io/badge/Streamlit-Cloud-success)](https://streamlit.io/cloud) 
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) 
[![Model: KNN](https://img.shields.io/badge/Model-KNN-blueviolet)](#cómo-funciona)

**Parkinson Detector** es una aplicación web que analiza una grabación de voz de ≥ 5 segundos (vocal sostenida) y, mediante un modelo **SVM** entrenado sobre el *Oxford Parkinson’s Disease Detection Dataset*, estima la probabilidad de enfermedad de Parkinson. Además, incluye un módulo de **IA explicable (XAI)** que genera interpretaciones en lenguaje natural y un informe PDF descargable con todas las métricas. 


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

* **Parselmouth + Praat** para calcular 3 variables clave (**Spread1**, **MDVP:APQ**, **MDVP:Shimmer**).  

### 2. Modelo de clasificación
* **Support Vector Machine (SVM)** con los mejores hiperparámetros:  
  ```python
  best_params = {'kernel': 'rbf', 'C': 100, 'gamma': 1}
  svm_final = SVC(**best_params, probability=True, random_state=42)
  svm_final.fit(X_train_s, y_train)
  ```
* Métricas de rendimiento (validación cruzada estratificada 10‑fold):  
  | Métrica      | Train | Test  |
  |--------------|-------|-------|
  | **AUC‑ROC**  | 0.951 | 0.921 |
  | **Accuracy** | 0.885 | 0.949 |
  | **Precision**| 0.879 | 0.935 |
  | **Recall**   | 0.983 | 1.000 |
  | **F1**       | 0.928 | 0.967 |
  | **MCC**      | 0.669 | 0.865 |
 
  * Repo oficial → <https://github.com/YannickJadoul/Parselmouth>  
* Recorte de silencios, normalización y *clipping* a rangos aprendidos durante el entrenamiento.

* Artefactos serializados en `svm_mcc_final`.

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
│  └─ svm_mcc_final.joblib
├─ entrenamiento/        # notebooks y dataset
│  ├─ Parkiston_Prediccion.ipynb
│  └─ parkinsons.data
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
source .venv/bin/activate      # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
El archivo requirements.txt instala streamlit, parselmouth, librosa, scikit‑learn, soundfile, fpdf, nolds, etc.

### 2 · Ejecución local
```bash
streamlit run app.py
```
La aplicación quedará disponible en http://localhost:8501; graba tu voz y visualiza el resultado en tiempo real.

## Dataset
Oxford Parkinson’s Disease Detection Dataset
https://archive.ics.uci.edu/ml/datasets/Parkinsons

Este conjunto de 195 grabaciones (23 pacientes, 8 controles) se emplea para entrenar el modelo K‑Nearest Neighbors incluido en models/modelo_knn.pkl.

## Licencia
Este proyecto se distribuye bajo licencia MIT.
Consulta el archivo LICENSE para más detalles.
Badges generados con Shields.io.

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

