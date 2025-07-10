import streamlit as st
import pandas as pd
import requests
import io
import wave
from streamlit_mic_recorder import mic_recorder
from fpdf import FPDF
from datetime import datetime

# backend
from funcion import predict_parkinson, MODEL_FEATURES, RANGE

FEATURE_DESCRIPTIONS = {
    "MDVP:Fo(Hz)"   : "Mide la frecuencia fundamental de tu voz, relacionada con cuán aguda o grave suena.",
    "MDVP:Fhi(Hz)"  : "Refleja el tono más alto que alcanza tu voz en la grabación.",
    "MDVP:Flo(Hz)"  : "Refleja el tono más bajo que alcanza tu voz en la grabación.",
    "MDVP:Jitter(%)": "Mide la estabilidad de la frecuencia; cambios bruscos pueden indicar irregularidad al hablar.",
    "MDVP:Jitter(Abs)": "Evalúa cambios mínimos entre ciclos de voz; muestra precisión en el control vocal.",
    "MDVP:RAP"      : "Indica pequeñas variaciones en el tono entre tres ciclos seguidos de voz.",
    "MDVP:PPQ"      : "Similar a RAP, pero promedia cambios en cinco ciclos seguidos de voz.",
    "Jitter:DDP"    : "Valora fluctuaciones rápidas del tono en períodos muy cortos.",
    "MDVP:Shimmer"  : "Mide la variación en la intensidad (volumen) de la voz de un ciclo a otro.",
    "MDVP:Shimmer(dB)": "Es la variabilidad del volumen expresada en decibelios.",
    "Shimmer:APQ3"  : "Promedia los cambios de intensidad de la voz en tres ciclos seguidos.",
    "Shimmer:APQ5"  : "Promedia los cambios de intensidad de la voz en cinco ciclos seguidos.",
    "Shimmer:DDA"   : "Indica variabilidad extrema de la intensidad entre ciclos cercanos.",
    "NHR"           : "Compara la cantidad de ruido frente a la parte armónica de tu voz.",
    "HNR"           : "Compara la claridad de tu voz frente al ruido de fondo; valores altos indican voz clara.",
    "RPDE"          : "Evalúa la complejidad y la regularidad del patrón vocal.",
    "DFA"           : "Analiza la presencia de patrones repetitivos o fluctuaciones en la voz.",
    "spread1"       : "Estudia cómo se dispersa la frecuencia de tu voz en el tiempo.",
    "spread2"       : "Analiza cambios bruscos o curvaturas en la trayectoria vocal.",
    "PPE"           : "Evalúa la variabilidad en el ciclo de los tonos; refleja lo predecible o variable que es tu voz."
}

#GEMINI_KEY = "AIzaSyAoReEdMLGBFiNG3oS089XrPc2OiW43-Fc"
GEMINI_KEY = "AIzaSyBRup_GtM7g0Z-_VexcN8zvN-b12fER-0k"
st.set_page_config(page_title="🎤 Parkinson Detector", layout="wide")
st.markdown("""
<style>
.main .block-container { background-color: #f9fafb; padding: 2rem 4rem; }
.stButton>button { background-color: #0052cc; color: white; border-radius: .4rem;
  padding: .6rem 1.2rem; font-weight: bold; }
.stButton>button:hover { background-color: #003d99; }
.stMetric { box-shadow: 0 2px 6px rgba(0,0,0,.1); border-radius: 1rem; padding: 1rem; }
.stDataFrame>div { border-radius: .6rem; box-shadow: 0 2px 4px rgba(0,0,0,.08); }
.progress-step {display: flex; gap:1rem; margin-bottom:1.5rem;}
.progress-step > div {
    display: flex; align-items: center; justify-content:center;
    font-weight: bold; font-size: 1.05rem; border-radius:2rem; padding:0.4rem 1.2rem;
    border: 2px solid #bbb;
    background: #eee;
    color: #666;
    transition: all 0.2s;
}
.progress-step .active {background: #0052cc; color:white; border-color:#0052cc;}
.progress-step .done {background: #36d66c; color:white; border-color:#36d66c;}
.progress-step .wait {background: #eee;}
.tooltip {display:inline-block; position:relative;}
.tooltip .tiptext {
    visibility:hidden; background:#222; color:#fff; text-align:center; border-radius:6px; padding:4px 7px;
    position:absolute; z-index:1; bottom:110%; left:50%; transform:translateX(-50%);
    opacity:0; transition:opacity .2s; font-size:0.95em; width:250px;
}
.tooltip:hover .tiptext {visibility:visible; opacity:1;}
</style>
""", unsafe_allow_html=True)

# Barra de progreso tipo wizard
steps = ["Datos", "Grabación", "Resultados"]
step_status = ["wait", "wait", "wait"]

if "paciente" in st.session_state and st.session_state["paciente"]:
    step_status[0] = "done"
else:
    step_status[0] = "active"

if "audio" in st.session_state:
    step_status[1] = "done"
    if st.session_state.get("analyzed"):
        step_status[2] = "active"
    else:
        step_status[2] = "wait"
    if not st.session_state.get("analyzed"):
        step_status[1] = "active"
else:
    if step_status[0] == "done":
        step_status[1] = "active"

# Render wizard
st.markdown('<div class="progress-step">' + "".join(
    f'<div class="{cls}">{i+1}. {name}</div>'
    for i,(cls,name) in enumerate(zip(step_status, steps))
) + '</div>', unsafe_allow_html=True)

# ── 0 · Bienvenida y datos del paciente ─────────────────────────────
st.markdown("""
# 👋 ¡Bienvenido(a) a Parkinson Detector!

Antes de comenzar:
- Ingresa tu **nombre y apellido**.
- Procura estar en un lugar **tranquilo**, sin mucho ruido de fondo.
- Cuando grabes tu voz, mantén una distancia adecuada del micrófono.
- Graba por **más de 5 segundos** diciendo una vocal clara (por ejemplo: “A” o “E”).
""")

paciente = st.text_input("👤 nombre y Apellido", value=st.session_state.get("paciente", ""))
if paciente:
    st.session_state["paciente"] = paciente

# Validación de paciente
if not paciente:
    st.warning("Por favor, ingresa tu paciente y apellido antes de continuar.")
    st.stop()

# ── 1 · Grabar audio ────────────────────────────────────────────
audio_state = st.session_state.get("audio")
audio_ok = False
if not audio_state:
    rec = mic_recorder("▶️ Iniciar", "⏹️ Detener", just_once=True, format="wav")
    if not rec or not rec.get("bytes"):
        st.info("Pulsa ▶️ para grabar tu voz. Recuerda repetir una vocal, como 'A' o 'E'.")
        st.stop()
    # Chequea duración mínima (5 segundos)
    try:
        audio_bytes = rec["bytes"]
        with io.BytesIO(audio_bytes) as wav_buffer:
            with wave.open(wav_buffer, "rb") as w:
                dur = w.getnframes() / w.getframerate()
        if dur < 4.5:
            st.error(f"El audio es muy corto ({dur:.1f} s). Por favor, graba al menos 5 segundos.")
            st.stop()
        else:
            audio_ok = True
    except Exception:
        st.error("No se pudo analizar la duración del audio. Intenta grabar de nuevo.")
        st.stop()
    st.session_state.audio = audio_bytes
    st.success("✅ ¡Audio guardado correctamente!")
else:
    audio_ok = True

# ── 2 · Reproducir y salvar ────────────────────────────────────
if audio_ok:
    st.audio(st.session_state.audio, format="audio/wav")
    with open("recording.wav", "wb") as f:
        f.write(st.session_state.audio)

# ── 3 · ANALIZAR & REINTENTAR ─────────────────────────────────
c1, c2 = st.columns(2)
with c1:
    if st.button("🔍 Analizar", key="analyze") and audio_ok:
        st.session_state.analyzed = True

# ── 4 · Tras Analizar ──────────────────────────────────────────
if st.session_state.get("analyzed"):
    with st.spinner("Extrayendo variables…"):
        raw, clip, scl, y, proba = predict_parkinson("recording.wav")

    # 4.1 Tabla Variables con tooltip
    st.markdown(
        '<h3 style="display:inline;">📊 Variables (Bruto vs Clip)</h3> '
        '<span class="tooltip">❔'
        '<span class="tiptext">Se comparan los valores extraídos de tu voz (“Bruto”) '
        'con los valores ajustados al rango de entrenamiento (“Clip”).</span>'
        '</span>', 
        unsafe_allow_html=True
    )

    rows = [(f, raw[f], clip[f], *RANGE[f]) for f in MODEL_FEATURES]
    df_vars = pd.DataFrame(rows, columns=["Variable","Bruto","Clip","Min","Max"])
    st.dataframe(df_vars, hide_index=True, use_container_width=True)

    rows = [(f, raw[f], clip[f], *RANGE[f]) for f in MODEL_FEATURES]
# Y también aquí puedes obtener final_interps, diag_label, etc.
    # 4.2 Interpretaciones IA
    st.markdown(
        '<h3 style="display:inline;">🔍 Interpretaciones de cada variable (IA)</h3> '
        '<span class="tooltip">❔'
        '<span class="tiptext">Interpretaciones automáticas y personalizadas, fáciles de entender, generadas con IA.</span>'
        '</span>', 
        unsafe_allow_html=True
    )

    # --- Generación del prompt para Gemini ---
    detalles = []
    for f, _, clip_val, _, _ in rows:
        desc = FEATURE_DESCRIPTIONS.get(f, "")
        detalles.append(f"{f}: {desc} | Valor actual (clip): {clip_val:.3f}")

    detalle = "\n".join(detalles)
    prompt = (
        "Eres un experto en análisis de voz y Parkinson. "
        "A continuación verás una lista de variables extraídas de la voz, con su descripción y su valor actual (clip). "
        "Para cada variable, haz lo siguiente:\n"
        "1. Explica en una sola frase y SIN REPETIR, qué mide esa variable (usa la descripción).\n"
        "2. Da una pequeña recomendación, comentario, o feedback positivo para el usuario sobre su voz, usando sólo el valor actual (clip), nunca repitas la misma frase para más de una variable. "
        "No uses tecnicismos ni digas 'no se detectó variación'. "
        "Habla directo al usuario, con lenguaje humano y cálido.\n\n"
        "Variables:\n"
        + detalle
    )

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"
    res = requests.post(url,
        params={"key": GEMINI_KEY},
        headers={"Content-Type":"application/json"},
        json={"contents":[{"parts":[{"text":prompt}]}]},
        timeout=10
    )
    text_ia = res.json().get("candidates",[{}])[0] \
        .get("content",{}).get("parts",[{}])[0] \
        .get("text","Error IA")

    lines = [l.strip() for l in text_ia.splitlines() if l.strip()]
    if len(lines) == 1 and ";" in lines[0]:
        lines = [seg.strip() for seg in lines[0].split(";") if seg.strip()]

    parsed = {}
    for ln in lines:
        ln = ln.lstrip("-*• ").strip()
        if ":" in ln:
            var, desc = ln.split(":",1)
            parsed[var.strip()] = desc.strip()

    final_interps = []
    for feat in MODEL_FEATURES:
        desc = parsed.get(feat)
        if not desc:
            desc = (
                f"{FEATURE_DESCRIPTIONS.get(feat,'Este indicador de voz es relevante.')} "
                "Recuerda mantener tu voz clara y relajada."
            )
        final_interps.append((feat, desc))

    df_ia = pd.DataFrame(final_interps, columns=["Variable","Interpretación"])
    st.dataframe(df_ia, use_container_width=True)
    
    # st.write("DEBUG JSON Gemini:", res.json())  # Muestra el JSON completo recibido


    # 4.3 Diagnóstico con tarjetas y paciente personalizado
    sano_p, park_p = proba[1], proba[0]
    paciente = st.session_state.get("paciente", "Paciente")

    if sano_p >= 0.7:
        estado = "saludable"
    elif park_p >= 0.7:
        estado = "riesgo"
    else:
        estado = "intermedio"


    cards = {
        "saludable": {
            "icon": "✅",
            "title": f"¡{paciente}, tu estado es Saludable!",
            "text": f"Sano {sano_p:.1%} · Parkinson {park_p:.1%}"
        },
        "intermedio": {
            "icon": "⚠️",
            "title": f"{paciente}, estado Intermedio",
            "text": f"Sano {sano_p:.1%} · Parkinson {park_p:.1%}"
        },
        "riesgo": {
            "icon": "❌",
            "title": f"{paciente}, Alto Riesgo",
            "text": f"Sano {sano_p:.1%} · Parkinson {park_p:.1%}"
        }
    }
    bg_colors = {
        "saludable": "#2ecc71",
        "intermedio": "#f1c40f",
        "riesgo": "#e74c3c"
    }
    inactive_bg = "#f0f0f0"
    active_text = "#ffffff"
    inactive_text = "#333333"

    st.subheader("🩺 Resultado y Recomendaciones")
    cols = st.columns(3)
    for idx, key in enumerate(("saludable","intermedio","riesgo")):
        card = cards[key]
        is_active = (key == estado)
        bg = bg_colors[key] if is_active else inactive_bg
        txt_color = active_text if is_active else inactive_text

        card_html = f"""
        <div style="
        background-color: {bg};
        color: {txt_color};
        border-radius: 8px;
        padding: 0.8rem;
        text-align: center;
        box-shadow: 0 3px 8px rgba(0,0,0,0.1);
        font-family: sans-serif;
        ">
        <div style="font-size: 2rem;">{card['icon']}</div>
        <h4 style="margin:0.2rem 0; font-size:1.1rem;">{card['title']}</h4>
        <small style="font-size:0.9rem;">{card['text']}</small>
        </div>
        """
        cols[idx].markdown(card_html, unsafe_allow_html=True)

    # Recomendación IA breve
    diag_prompt = (
        f"Paciente: {paciente}. Probabilidades: Sano {sano_p:.1%}, Parkinson {park_p:.1%}. "
        "Dame una recomendación breve y empática (máx 30 palabras)."
    )
    res = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent",
        params={"key": GEMINI_KEY},
        headers={"Content-Type":"application/json"},
        json={"contents":[{"parts":[{"text":diag_prompt}]}]},
        timeout=10
    )
    rec_ia = res.json().get("candidates",[{}])[0] \
                .get("content",{}).get("parts",[{}])[0] \
                .get("text","")
    st.markdown("#### Recomendación breve")
    st.markdown(
        f"""
        <div style='
            background: #e0f7fa;               /* Fondo celeste claro */
            border-left: 6px solid #00796b;    /* Borde verde azulado */
            border-radius: 8px;
            padding: 1rem 1.3rem;
            margin-bottom: 1rem;
            font-size: 1.15rem;
            color: #114155;                    /* Letra azul oscuro */
            font-weight: 500;
        '>
        💡 {rec_ia or 'No se pudo obtener la recomendación IA.'}
        </div>
        """,
        unsafe_allow_html=True
    )



# --- Genera recomendación extensa (IA) para el PDF ---
    prompt_ext = (
        f"Eres un médico empático experto en Parkinson. Explica al paciente {paciente} el resultado de su análisis de voz "
        f"(Sano: {sano_p:.1%}, Parkinson: {park_p:.1%}), qué significa para su salud, y da consejos útiles para la vida diaria y cuándo consultar con un especialista. Máx 170 palabras."
    )
    res_ext = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent",
        params={"key": GEMINI_KEY},
        headers={"Content-Type":"application/json"},
        json={"contents":[{"parts":[{"text":prompt_ext}]}]},
        timeout=15
    )
    recomendacion_extensa = res_ext.json().get("candidates",[{}])[0] \
                .get("content",{}).get("parts",[{}])[0] \
                .get("text","Consulta siempre a un especialista si tienes dudas sobre tu salud.")

    
    
    if estado == "saludable":
        diag_label = "Estado saludable"
    elif estado == "riesgo":
        diag_label = "Alta probabilidad de Parkinson"
    else:
        diag_label = "Estado intermedio"



    # --- BLOQUE PDF (DENTRO DEL IF) ---
    from fpdf import FPDF
    from datetime import datetime

    def sanitize(txt:str)->str:
        return txt.encode("latin-1","ignore").decode("latin-1")

    # --- BLOQUE PDF MEJORADO ---
    pdf = FPDF(format="A4")
    pdf.set_left_margin(15)
    pdf.set_right_margin(15)
    pdf.set_top_margin(12)
    pdf.add_page()
    pdf.set_auto_page_break(True, margin=15)

    def sanitize(txt: str) -> str:
        return txt.encode("latin-1", "ignore").decode("latin-1")

    # Encabezado y fecha, alineados
    pdf.set_font("Helvetica","B",16)
    pdf.cell(0, 12, "Reporte Personalizado de Fonética Vocal y Parkinson", ln=True, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Paciente: {paciente}", ln=True)
    pdf.cell(0, 8, f"Fecha de análisis: {datetime.now():%Y-%m-%d %H:%M:%S}", ln=True, align="R")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 8, sanitize("Hola, espero que tengas una excelente jornada. Este reporte es un resumen detallado del análisis de tu voz para apoyar el cuidado de tu salud."))
    pdf.ln(4)

    # Variables
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Variables Analizadas", ln=True)
    pdf.set_font("Helvetica", "B", 10)
    col_w = [60, 35, 35]
    pdf.cell(col_w[0], 7, "Variable", 1, 0, "C")
    pdf.cell(col_w[1], 7, "Bruto", 1, 0, "C")
    pdf.cell(col_w[2], 7, "Clip", 1, 1, "C")
    pdf.set_font("Helvetica", "", 9)
    for feat, raw_val, clip_val, *_ in rows:
        pdf.cell(col_w[0], 7, sanitize(str(feat)), 1)
        pdf.cell(col_w[1], 7, f"{raw_val:.3f}", 1)
        pdf.cell(col_w[2], 7, f"{clip_val:.3f}", 1)
        pdf.ln()
    pdf.ln(3)

    # ... después de imprimir la tabla de variables ...
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 7,
        "En la tabla anterior se muestran las variables extraídas de tu voz. "
        "La columna 'Bruto' representa los valores originales captados de tu grabación, "
        "mientras que 'Clip' corresponde a los valores ajustados al rango estándar de referencia. "
        "Estas mediciones ayudan a analizar características de tu voz que pueden relacionarse con salud vocal y detección temprana de Parkinson."
    )
    pdf.ln(2)


    # Interpretaciones IA
# Ajuste visual y de salto correcto para cada fila de la tabla IA
    from math import ceil

    pdf.add_page()  # <-- Esto fuerza que la tabla IA vaya a la siguiente hoja

    # Ahora imprime la tabla de interpretaciones IA con el bloque mejorado:
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Interpretación de cada variable (IA)", ln=True)
    pdf.set_font("Helvetica", "B", 10)
    col_w2 = [60, 110]
    pdf.cell(col_w2[0], 10, "Variable", 1, 0, "C")
    pdf.cell(col_w2[1], 10, "Interpretación", 1, 1, "C")
    pdf.set_font("Helvetica", "", 9)

    cell_height = 8

    for var, desc in final_interps:
        x = pdf.get_x()
        y = pdf.get_y()
        n_lines_desc = max(2, int(pdf.get_string_width(desc) / (col_w2[1] - 10)) + 1)
        row_h = n_lines_desc * cell_height

        pdf.multi_cell(col_w2[0], row_h, sanitize(var), border=1, align="L", ln=3)
        pdf.set_xy(x + col_w2[0], y)
        pdf.multi_cell(col_w2[1], cell_height, sanitize(desc), border=1, align="L")
        pdf.set_xy(x, y + row_h)

    pdf.ln(2)



    # Diagnóstico
    pdf.add_page() 
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Resultados del análisis", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(0, 80, 0) # Verde oscuro para destacar
    pdf.multi_cell(0, 7, sanitize(
        f"Diagnóstico: {diag_label}\n"
        f"Probabilidad Sano: {sano_p:.1%} | Probabilidad Parkinson: {park_p:.1%}\n"
        f"Frase IA: {rec_ia}"
    ))
    pdf.set_text_color(0,0,0)
    pdf.ln(2)

    # Recomendación extensa
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Recomendaciones personalizadas", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 7, sanitize(recomendacion_extensa))
    pdf.ln(4)

    pdf_bytes = bytes(pdf.output(dest="S"))
    st.download_button("📥 Descargar Informe detallado (PDF)",
                    data=pdf_bytes,
                    file_name=f"reporte_{paciente.replace(' ','_')}.pdf",
                    mime="application/pdf",
                    key="download_pdf")
