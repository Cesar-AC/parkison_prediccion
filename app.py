import streamlit as st
import pandas as pd
import requests
import io
import wave
from streamlit_mic_recorder import mic_recorder
from fpdf import FPDF
from datetime import datetime
from googletrans import Translator
translator = Translator()
import logging
import os
# backend
from funcion import predict_parkinson, MODEL_FEATURES, RANGE

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
PDF_DIR  = os.path.join(BASE_DIR, "pdf")



FEATURE_DESCRIPTIONS = {
    "spread1": "Dispersión de la frecuencia fundamental (cuanto más alto → más variación).",
    "MDVP:APQ": "Amplitud media de perturbación (fluctuaciones de volumen).",
    "MDVP:Shimmer": "Variabilidad ciclo a ciclo en la intensidad de la voz."
}

GEMINI_KEY = "AIzaSyAoReEdMLGBFiNG3oS089XrPc2OiW43-Fc"
#GEMINI_KEY = "AIzaSyBRup_GtM7g0Z-_VexcN8zvN-b12fER-0k"

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

# Justo después de pedir el nombre del paciente
display_name, idioma = st.selectbox(
    "🌐 Selecciona tu idioma de preferencia:",
    options=[
        ("Español", "es"),
        ("Inglés", "en"),
        ("Portugués", "pt"),
        ("Francés", "fr"),
        ("Chino mandarín", "zh-cn"),
    ],
    index=0,
)
st.session_state["idioma"] = idioma  # ahora idioma es un string: "es", "en", etc.


@st.cache_data(show_spinner=False)
def traducir(texto: str, dest: str) -> str:
    # Si está en español, o texto es None o vacío, devuelvo tal cual (o cadena vacía)
    if dest == "es" or not texto:
        return texto or ""
    try:
        # Aseguro que texto es str
        texto_str = str(texto)
        return translator.translate(texto_str, dest=dest).text
    except Exception:
        logging.exception("Error traduciendo texto")
        # En caso de fallo, devuelvo el texto original
        return texto_str




# ── 0 · Bienvenida y datos del paciente ─────────────────────────────
texto_bienvenida = """
# 👋 ¡Bienvenido(a) a Parkinson Detector!

Antes de comenzar:
- Ingresa tu **nombre y apellido**.
- Procura estar en un lugar **tranquilo**, sin mucho ruido de fondo.
- Cuando grabes tu voz, mantén una distancia adecuada del micrófono.
- Graba por **más de 5 segundos** diciendo una vocal clara (por ejemplo: “A” o “E”).
"""
# traducimos todo el bloque de una vez
st.markdown(traducir(texto_bienvenida, st.session_state["idioma"]), unsafe_allow_html=True)

# Input del paciente
label_paciente = traducir("👤 Nombre y Apellido", st.session_state["idioma"])
paciente = st.text_input(label_paciente, value=st.session_state.get("paciente", ""))
if paciente:
    st.session_state["paciente"] = paciente

# Validación de paciente
warning_msg = traducir("Por favor, ingresa tu nombre y apellido antes de continuar.", st.session_state["idioma"])
if not paciente:
    st.warning(warning_msg)
    st.stop()


# ── 1 · Grabar audio ────────────────────────────────────────────
audio_state = st.session_state.get("audio")
audio_ok = False

if not audio_state:
    # etiquetas del recorder traducidas
    start_label = traducir("▶️ Iniciar", idioma)
    stop_label  = traducir("⏹️ Detener", idioma)

    rec = mic_recorder(start_label, stop_label, just_once=True, format="wav")
    if not rec or not rec.get("bytes"):
        st.info(traducir(
            "Pulsa ▶️ para grabar tu voz. Recuerda repetir una vocal, como 'A' o 'E'.",
            idioma
        ))
        st.stop()

    # Chequea duración mínima (5 segundos)
    try:
        audio_bytes = rec["bytes"]
        with io.BytesIO(audio_bytes) as wav_buffer:
            with wave.open(wav_buffer, "rb") as w:
                dur = w.getnframes() / w.getframerate()
        if dur < 4.5:
            st.error(traducir(
                f"El audio es muy corto ({dur:.1f} s). Por favor, graba al menos 5 segundos.",
                idioma
            ))
            st.stop()
        else:
            audio_ok = True
    except Exception:
        st.error(traducir(
            "No se pudo analizar la duración del audio. Intenta grabar de nuevo.",
            idioma
        ))
        st.stop()

    st.session_state.audio = audio_bytes
    st.success(traducir("✅ ¡Audio guardado correctamente!", idioma))
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
    analyze_label = traducir("🔍 Analizar", idioma)
    if st.button(analyze_label, key="analyze") and audio_ok:
        st.session_state.analyzed = True

# ── 4 · Tras Analizar ──────────────────────────────────────────
if st.session_state.get("analyzed"):
    spinner_msg = traducir("Extrayendo variables…", idioma)
    with st.spinner(spinner_msg):
        raw, clip, scl, y, proba = predict_parkinson("recording.wav")

    # 4.1 Tabla Variables con tooltip
    title_vars = traducir("📊 Variables (Bruto vs Clip)", idioma)
    tiptext   = traducir(
        "Se comparan los valores extraídos de tu voz (“Bruto”) "
        "con los valores ajustados al rango de entrenamiento (“Clip”).",
        idioma
    )
    st.markdown(
        f'<h3 style="display:inline;">{title_vars}</h3> '
        f'<span class="tooltip">❔'
        f'<span class="tiptext">{tiptext}</span>'
        f'</span>',
        unsafe_allow_html=True
    )

    # Construye las cabeceras traducidas de la tabla
    cols = [
        traducir("Variable", idioma),
        traducir("Bruto", idioma),
        traducir("Clip", idioma),
        traducir("Min", idioma),
        traducir("Max", idioma),
    ]
    rows = [(f, raw[f], clip[f], *RANGE[f]) for f in MODEL_FEATURES]
    df_vars = pd.DataFrame(rows, columns=cols)
    st.dataframe(df_vars, hide_index=True, use_container_width=True)
  # 4.2 · Header y tooltip traducidos
    title_ia = traducir("🔍 Interpretaciones de cada variable (IA)", idioma)
    tip_ia   = traducir(
        "Interpretaciones automáticas y personalizadas, fáciles de entender, generadas con IA.",
        idioma
    )
    st.markdown(
        f'<h3 style="display:inline;">{title_ia}</h3> '
        f'<span class="tooltip">❔'
        f'<span class="tiptext">{tip_ia}</span>'
        f'</span>',
        unsafe_allow_html=True
    )

    # --- Generación del prompt (SIEMPRE EN ESPAÑOL para calidad) ---
    detalles = []
    for feat in MODEL_FEATURES:
        desc = FEATURE_DESCRIPTIONS.get(feat, "")
        clip_val = clip[feat]                  # el valor «clip» de esa feature
        detalles.append(
            f"{feat}: {desc} | Valor actual (clip): {clip_val:.3f}"
        )
    detalle = "\n".join(detalles)

    prompt = (
        "Eres un experto en análisis de voz y Parkinson. "
        "A continuación verás una lista de variables extraídas de la voz, con su descripción y su valor actual (clip). "
        "Para cada variable, haz lo siguiente:\n"
        "1. Explica en una sola frase y SIN REPETIR, qué mide esa variable (usa la descripción).\n"
        "2. Da una pequeña recomendación, comentario o feedback positivo sobre tu voz, usando sólo el valor actual (clip). "
        "Habla directo al usuario, con lenguaje humano y cálido.\n\n"
        "Variables:\n" + detalle
    )

    # Llamada a Gemini
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"
    res = requests.post(
        url,
        params={"key": GEMINI_KEY},
        headers={"Content-Type":"application/json"},
        json={"contents":[{"parts":[{"text":prompt}]}]},
        timeout=10
    )
    text_ia = (
        res.json()
           .get("candidates",[{}])[0]
           .get("content",{})
           .get("parts",[{}])[0]
           .get("text","Error IA")
    )

    # 4.2.a · Traducir respuesta de Gemini si hace falta
    if idioma != "es":
        text_ia = traducir(text_ia, idioma)

    # Parseo de líneas
    lines = [l.strip() for l in text_ia.splitlines() if l.strip()]
    if len(lines) == 1 and ";" in lines[0]:
        lines = [seg.strip() for seg in lines[0].split(";") if seg.strip()]

    parsed = {}
    for ln in lines:
        ln = ln.lstrip("-*• ").strip()
        if ":" in ln:
            var, desc = ln.split(":",1)
            parsed[var.strip()] = desc.strip()

    # Construcción de final_interps (ya en el idioma seleccionado)
    final_interps = []
    for feat in MODEL_FEATURES:
        desc = parsed.get(feat)
        if not desc:
            fallback = traducir(
                "Este indicador de voz es relevante. Recuerda mantener tu voz clara y relajada.",
                idioma
            )
            desc = fallback
        final_interps.append((feat, desc))

    # 4.2.b · Tabla con cabeceras traducidas
    col_var    = traducir("Variable", idioma)
    col_interp = traducir("Interpretación", idioma)
    df_ia = pd.DataFrame(final_interps, columns=[col_var, col_interp])
    st.dataframe(df_ia, use_container_width=True)
    
    # st.write("DEBUG JSON Gemini:", res.json())  # Muestra el JSON completo recibido


    # ── 4.3 Diagnóstico con tarjetas y paciente personalizado ────────
    sano_p, park_p = proba[1], proba[0]
    paciente = st.session_state.get("paciente", "Paciente")

    # Determinar estado
    if sano_p >= 0.7:
        estado = "saludable"
    elif park_p >= 0.7:
        estado = "riesgo"
    else:
        estado = "intermedio"

    # Plantilla de cards (en español, luego traducimos)
    cards = {
        "saludable": {
            "icon": "✅",
            "title": f"¡{paciente}, tu estado es Saludable!",
            "text":  f"Sano {sano_p:.1%} · Parkinson {park_p:.1%}"
        },
        "intermedio": {
            "icon": "⚠️",
            "title": f"{paciente}, estado Intermedio",
            "text":  f"Sano {sano_p:.1%} · Parkinson {park_p:.1%}"
        },
        "riesgo": {
            "icon": "❌",
            "title": f"{paciente}, Alto Riesgo",
            "text":  f"Sano {sano_p:.1%} · Parkinson {park_p:.1%}"
        }
    }

    # Colores
    bg_colors = {"saludable": "#2ecc71","intermedio": "#f1c40f","riesgo": "#e74c3c"}
    inactive_bg, active_text, inactive_text = "#f0f0f0","#ffffff","#333333"

    # Subheader
    st.subheader(traducir("🩺 Resultado y Recomendaciones", idioma))

    cols = st.columns(3)
    for idx, key in enumerate(("saludable","intermedio","riesgo")):
        card = cards[key]
        is_active = (key == estado)
        bg = bg_colors[key] if is_active else inactive_bg
        txt_color = active_text if is_active else inactive_text

        # traducir título y texto
        title = traducir(card["title"], idioma)
        text  = traducir(card["text"],  idioma)

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
        <h4 style="margin:0.2rem 0; font-size:1.1rem;">{title}</h4>
        <small style="font-size:0.9rem;">{text}</small>
        </div>
        """
        cols[idx].markdown(card_html, unsafe_allow_html=True)

    # ── 4.4 Recomendación IA breve (¡fuera del for!) ───────────────────
    # Prompt en español
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
    rec_ia = (
        res.json()
        .get("candidates",[{}])[0]
        .get("content",{})
        .get("parts",[{}])[0]
        .get("text","")
    )

    # Traducir respuesta si es necesario
    if idioma != "es":
        rec_ia = traducir(rec_ia, idioma)

    # Títulos y fallback traducidos
    st.markdown(traducir("#### Recomendación breve", idioma))
    fallback = traducir("No se pudo obtener la recomendación IA.", idioma)

    st.markdown(
        f"""
        <div style='
            background: #e0f7fa;
            border-left: 6px solid #00796b;
            border-radius: 8px;
            padding: 1rem 1.3rem;
            margin-bottom: 1rem;
            font-size: 1.15rem;
            color: #114155;
            font-weight: 500;
        '>
        💡 {rec_ia or fallback}
        </div>
        """,
        unsafe_allow_html=True
    )


    # --- 4.5 Recomendación extensa (IA) para el PDF con traducción ---

    # 1) Prompt en español para Gemini
    prompt_ext = (
        f"Eres un médico empático experto en Parkinson. Explica al paciente {paciente} "
        f"el resultado de su análisis de voz (Sano: {sano_p:.1%}, Parkinson: {park_p:.1%}), "
        "qué significa para su salud, y da consejos útiles para la vida diaria y cuándo consultar "
        "con un especialista. Máx 170 palabras."
    )
    res_ext = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent",
        params={"key": GEMINI_KEY},
        headers={"Content-Type":"application/json"},
        json={"contents":[{"parts":[{"text":prompt_ext}]}]},
        timeout=15
    )
    recomendacion_extensa = (
        res_ext.json()
            .get("candidates",[{}])[0]
            .get("content",{})
            .get("parts",[{}])[0]
            .get("text", "Consulta siempre a un especialista si tienes dudas sobre tu salud.")
    )

    # 2) Traducir la recomendación si el idioma no es español
    if idioma != "es":
        recomendacion_extensa = traducir(recomendacion_extensa, idioma)

    # 3) Definir diag_label en español y luego traducir
    if estado == "saludable":
        diag_label = "Estado saludable"
    elif estado == "riesgo":
        diag_label = "Alta probabilidad de Parkinson"
    else:
        diag_label = "Estado intermedio"

    # traducimos diag_label
    diag_label = traducir(diag_label, idioma)



    # ——— BLOQUE PDF CON TRADUCCIÓN ———


    from fpdf import FPDF
    from datetime import datetime
    import streamlit as st

    @st.cache_data(show_spinner=False)
    def build_report_pdf(
        paciente: str,
        rows,
        final_interps,
        diag_label: str,
        sano_p: float,
        park_p: float,
        recomendacion_extensa: str,
        idioma: str
    ) -> bytes:
        """
        Construye y devuelve los bytes del PDF.
        Se cachea, de modo que la primera ejecución tarde,
        y las siguientes sean instantáneas.
        """
        def sanitize(txt: str) -> str:
            return txt.encode("latin-1", "ignore").decode("latin-1")

        pdf = FPDF(format="A4")
        pdf.set_left_margin(15); pdf.set_right_margin(15)
        pdf.set_top_margin(12); pdf.set_auto_page_break(True, margin=15)
        pdf.add_page()

        # — Encabezado —
        titulo_pdf = traducir("Reporte Personalizado de Fonética Vocal y Parkinson", idioma)
        label_pac  = traducir("Paciente:", idioma)
        label_fecha= traducir("Fecha de análisis:", idioma)

        pdf.set_font("Helvetica","B",16)
        pdf.cell(0, 12, sanitize(titulo_pdf), ln=True, align="C")
        pdf.set_font("Helvetica","",11)
        pdf.cell(0, 8, sanitize(f"{label_pac} {paciente}"), ln=True)
        pdf.cell(0, 8,
                sanitize(f"{label_fecha} {datetime.now():%Y-%m-%d %H:%M:%S}"),
                ln=True, align="R")
        pdf.ln(4)

        # — Introducción —
        intro = traducir(
            "Hola, espero que tengas una excelente jornada. "
            "Este reporte es un resumen detallado del análisis de tu voz "
            "para apoyar el cuidado de tu salud.",
            idioma
        )
        pdf.set_font("Helvetica","",11)
        pdf.multi_cell(0, 8, sanitize(intro))
        pdf.ln(4)

        # — Tabla de Variables —
        sec_vars = traducir("Variables Analizadas", idioma)
        pdf.set_font("Helvetica","B",13)
        pdf.cell(0, 8, sanitize(sec_vars), ln=True)

        col_w = [60, 35, 35]
        headers = [
            traducir("Variable", idioma),
            traducir("Bruto", idioma),
            traducir("Clip", idioma),
        ]
        pdf.set_font("Helvetica","B",10)
        for w, h in zip(col_w, headers):
            pdf.cell(w, 7, sanitize(h), 1, 0, "C")
        pdf.ln()
        pdf.set_font("Helvetica","",9)
        for feat, raw_val, clip_val, *_ in rows:
            pdf.cell(col_w[0],7,sanitize(str(feat)),1)
            pdf.cell(col_w[1],7,f"{raw_val:.3f}",1)
            pdf.cell(col_w[2],7,f"{clip_val:.3f}",1)
            pdf.ln()
        pdf.ln(3)

        # — Explicación de la Tabla —
        explic = traducir(
            "En la tabla anterior se muestran las variables extraídas de tu voz. "
            "La columna 'Bruto' representa los valores originales captados de tu grabación, "
            "mientras que 'Clip' corresponde a los valores ajustados al rango estándar de referencia. "
            "Estas mediciones ayudan a analizar características de tu voz que pueden relacionarse "
            "con salud vocal y detección temprana de Parkinson.",
            idioma
        )
        pdf.set_font("Helvetica","",10)
        pdf.multi_cell(0,7,sanitize(explic))
        pdf.ln(4)

        # — Interpretaciones IA —
        pdf.set_font("Helvetica","B",13)
        pdf.cell(0, 8, sanitize(traducir("Interpretación de cada variable (IA)", idioma)), ln=True)
        pdf.set_font("Helvetica","B",10)

        # Ancho de columnas
        w_feat, w_interp = 60, 110
        cell_h = 6  # altura de línea

        # Cabecera
        pdf.cell(w_feat, 10, sanitize(traducir("Variable", idioma)), 1, 0, "C")
        pdf.cell(w_interp, 10, sanitize(traducir("Interpretación", idioma)), 1, 1, "C")

        pdf.set_font("Helvetica","",9)

        for feat, texto in final_interps:
            # punto de partida de la fila
            x0, y0 = pdf.get_x(), pdf.get_y()

            # 1) Imprime la variable en la 1ª columna
            pdf.multi_cell(w_feat, cell_h, sanitize(feat), border=1)

            # Guarda hasta dónde llegó la 1ª columna
            y_feat_end = pdf.get_y()

            # 2) Imprime la interpretación en la 2ª columna,
            #    regresando al tope de la fila
            pdf.set_xy(x0 + w_feat, y0)
            pdf.multi_cell(w_interp, cell_h, sanitize(texto), border=1)

            # Guarda hasta dónde llegó la 2ª columna
            y_interp_end = pdf.get_y()

            # 3) Posiciona el cursor en la siguiente fila,
            #    al tope de la más alta de las dos columnas
            pdf.set_xy(x0, max(y_feat_end, y_interp_end))

        # un poco de espacio tras la tabla
        pdf.ln(4)


        # — Resultados y Recomendaciones —
        sec_res   = traducir("Resultados del análisis", idioma)
        label_diag= traducir("Diagnóstico:", idioma)
        label_ps  = traducir("Probabilidad Sano:", idioma)
        label_pp  = traducir("Probabilidad Parkinson:", idioma)

        pdf.set_font("Helvetica","B",13)
        pdf.cell(0,8,sanitize(sec_res), ln=True)
        pdf.set_font("Helvetica","",10)
        pdf.set_text_color(0,80,0)
        texto_res = (
            f"{label_diag} {diag_label}\n"
            f"{label_ps} {sano_p:.1%} | {label_pp} {park_p:.1%}"
        )
        pdf.multi_cell(0,7,sanitize(texto_res))
        pdf.set_text_color(0,0,0)
        pdf.ln(4)

        sec_rec = traducir("Recomendaciones personalizadas", idioma)
        pdf.set_font("Helvetica","B",13)
        pdf.cell(0,8,sanitize(sec_rec), ln=True)
        pdf.set_font("Helvetica","",10)
        pdf.multi_cell(0,7,sanitize(recomendacion_extensa))
        pdf.ln(4)

        # Output final
        raw = pdf.output(dest="S")
        return raw.encode("latin-1") if isinstance(raw, str) else bytes(raw)


if st.session_state.get("analyzed"):
    # … ya tienes rows, final_interps, diag_label, sano_p, park_p, recomendacion_extensa …

    # 1) Genera y cachea el PDF detallado solo la primera vez
    if "pdf_bytes" not in st.session_state:
        st.session_state.pdf_bytes = build_report_pdf(
            paciente,
            rows,
            final_interps,
            diag_label,
            sano_p,
            park_p,
            recomendacion_extensa,
            idioma
        )

    # 2) Opcional: cachea también el reporte ML pre-generado
    if "ml_report_bytes" not in st.session_state:
        try:
            with open("models/reporte_modelos.pdf", "rb") as f:
                st.session_state.ml_report_bytes = f.read()
        except FileNotFoundError:
            st.session_state.ml_report_bytes = None

    # 3) Dos columnas para los botones de descarga
    c1, c2 = st.columns(2)

    # Botón 1: Informe detallado (cacheado en session_state)
    with c1:
        st.download_button(
            label=traducir("📥 Descargar Informe detallado (PDF)", idioma),
            data=st.session_state.pdf_bytes,
            file_name=f"reporte_{paciente.replace(' ','_')}.pdf",
            mime="application/pdf",
            key="download_detailed_report"
        )

    # Botón 2: Reporte ML pre-generado por idioma
    with c2:
        lang_map = {
        "es":    ("espa_parkison.pdf", "Español"),
        "en":    ("ingl_parkison.pdf", "English"),
        "fr":    ("fran_parkison.pdf", "Français"),
        "pt":    ("port_parkison.pdf", "Português"),
        "zh-cn": ("chin_parkison.pdf", "中文"),
    }
    pdf_file, lang_name = lang_map.get(idioma, (None, None))

    if not pdf_file:
        st.error(traducir("Idioma no soportado para el reporte ML.", idioma))
    else:
        pdf_path = os.path.join(PDF_DIR, pdf_file)
        if not os.path.exists(pdf_path):
            st.error(traducir("No se encontró el reporte ML para este idioma.", idioma))
            
        else:
            with open(pdf_path, "rb") as f:
                ml_bytes = f.read()
            label = traducir(f"📥 Descargar Reporte ML ({lang_name})", idioma)
            st.download_button(
                label=label,
                data=ml_bytes,
                file_name=pdf_file,
                mime="application/pdf",
                key="download_ml_report"
            )