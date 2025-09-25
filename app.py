import streamlit as st
import pandas as pd
import requests
import io
import wave
from streamlit_mic_recorder import mic_recorder
from fpdf import FPDF  # still needed for type usage earlier
from datetime import datetime
from pdf_report import build_report_pdf
from gemini_client import (
    get_feature_interpretations,
    get_short_recommendation,
    get_long_recommendation,
    GeminiError,
)
from gemini_prompts import parse_feature_interpretations_response
from deep_translator import GoogleTranslator
import logging
import os
from styles.theme import inject_base_css
from ui_components.wizard import render_wizard
from funcion import predict_parkinson, MODEL_FEATURES, RANGE

# Descripciones simples de cada feature usadas para prompt IA
FEATURE_DESCRIPTIONS = {
    "spread1": "Medida logarítmica de la desviación relativa de la frecuencia fundamental (estabilidad tonal).",
    "MDVP:APQ": "Variación de amplitud (shimmer) promediada: refleja micro-variaciones de la intensidad de la voz.",
    "MDVP:Shimmer": "Shimmer local: porcentaje de variación ciclo a ciclo en la amplitud de la señal." ,
}

# Carpeta donde residen los reportes multilingües estáticos
PDF_DIR = "pdf"

st.set_page_config(page_title="🎤 Parkinson Detector", layout="wide")
inject_base_css()

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

active_index = step_status.index("active") if "active" in step_status else 0
done_until = max([i for i,s in enumerate(step_status) if s=="done"], default=-1)
render_wizard(steps, active_index=active_index, done_until=done_until)

# Selector de idioma
idioma_options = [
    ("Español", "es"),
    ("Inglés", "en"),
    ("Portugués", "pt"),
    ("Francés", "fr"),
    ("Chino mandarín", "zh-cn"),
]
_, idioma = st.selectbox(
    "🌐 Selecciona tu idioma de preferencia:",
    options=idioma_options,
    index=0,
)
st.session_state["idioma"] = idioma

# ── Toggle Tema Claro/Oscuro ─────────────────────────────────────────
if "theme" not in st.session_state:
    st.session_state["theme"] = "auto"  # auto | light | dark

col_theme, _ = st.columns([1,5])
with col_theme:
    current = st.session_state["theme"]
    label_toggle = {"auto":"🌗 Auto","light":"🌞 Claro","dark":"🌚 Oscuro"}
    next_map = {"auto":"light","light":"dark","dark":"auto"}
    if st.button(label_toggle[current], help="Cambiar tema (auto/claro/oscuro)"):
        st.session_state["theme"] = next_map[current]
        try:
            st.rerun()
        except Exception:
            pass

# Inyectar clase para forzar tema si no es auto
forced = st.session_state["theme"]
if forced in ("light","dark"):
    # Añadimos un pequeño script para colocar clase en <html>
    st.markdown(f"""
    <script>
    const root = document.documentElement; root.classList.remove('theme-dark','theme-light');
    root.classList.add('theme-{forced}');
    </script>
    """, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def traducir(texto: str, dest: str) -> str:
    """Traduce texto al idioma destino usando deep-translator.

    Si el destino es español o el texto está vacío, retorna sin cambios.
    Ante error se devuelve el texto original para no romper el flujo UI.
    """
    if dest == "es" or not texto:
        return texto or ""
    texto_str = str(texto)
    try:
        return GoogleTranslator(source="auto", target=dest).translate(texto_str)
    except Exception:
        logging.exception("Error traduciendo texto")
        return texto_str




# ── 0 · Bienvenida y datos del paciente ─────────────────────────────
texto_bienvenida_panel = f"""
<div class='steps-panel'>
    <h1>👋 {traducir('¡Bienvenido(a) a Parkinson Detector!', st.session_state['idioma'])}</h1>
    <div class='steps-grid'>
        <div class='step-box' data-step='1'>
            <div class='step-icon'>📝</div>
            <div class='step-text'>{traducir('Ingresa tu nombre y apellido para personalizar el informe.', st.session_state['idioma'])}</div>
        </div>
        <div class='step-box' data-step='2'>
            <div class='step-icon'>🤫</div>
            <div class='step-text'>{traducir('Busca un lugar silencioso y evita ruidos bruscos al grabar.', st.session_state['idioma'])}</div>
        </div>
        <div class='step-box' data-step='3'>
            <div class='step-icon'>🎤</div>
            <div class='step-text'>{traducir('Mantén distancia constante del micrófono, tono natural y relajado.', st.session_state['idioma'])}</div>
        </div>
        <div class='step-box' data-step='4'>
            <div class='step-icon'>🗣️</div>
            <div class='step-text'>{traducir('Pronuncia una vocal clara ("A" o "E") sin cortes durante al menos 5 segundos.', st.session_state['idioma'])}</div>
        </div>
        <div class='step-box' data-step='5'>
            <div class='step-icon'>🧪</div>
            <div class='step-text'>{traducir('Analiza y revisa las variables, interpretaciones y recomendaciones.', st.session_state['idioma'])}</div>
        </div>
    </div>
</div>
"""
st.markdown(texto_bienvenida_panel, unsafe_allow_html=True)

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


## ── 1 · Grabación (panel mejorado con placeholder) ────────────
audio_state = st.session_state.get("audio")
audio_ok = False

start_label = traducir("▶️ Iniciar", idioma)
stop_label  = traducir("⏹️ Detener", idioma)
txt_grabando = traducir("Grabando", idioma)
txt_grabado = traducir("Grabado", idioma)
msg_inicial = traducir('Presiona Iniciar y sostén una vocal clara durante al menos 5 segundos.', idioma)
msg_grabando = traducir('Grabando… mantén la vocal constante…', idioma)
msg_fin = traducir('Listo. Puedes reproducir o analizar.', idioma)

if not audio_state:
    # Panel reducido solo con información / instrucciones
    st.markdown(f"""
    <div class='record-panel' id='record-panel'>
      <h3>🎤 {traducir('Grabación de voz', idioma)}</h3>
      <div class='short-hints'>
        <div class='hint'><i>🤫</i>{traducir('Ambiente silencioso', idioma)}</div>
        <div class='hint'><i>📏</i>{traducir('Mantén distancia constante', idioma)}</div>
        <div class='hint'><i>🗣️</i>{traducir('Pronuncia “A” o “E” clara', idioma)}</div>
        <div class='hint'><i>⏱️</i>{traducir('Duración > 5s', idioma)}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Componente de grabación simple (fuera del panel)
    rec = mic_recorder(start_label, stop_label, just_once=True, format="wav", key="mic_main")
    if not rec or not rec.get("bytes"):
        st.info(traducir("Pulsa ▶️ para grabar tu voz. Recuerda repetir una vocal, como 'A' o 'E'.", idioma))
        st.stop()
    try:
        audio_bytes = rec["bytes"]
        with io.BytesIO(audio_bytes) as wav_buffer:
            with wave.open(wav_buffer, "rb") as w:
                dur = w.getnframes() / w.getframerate()
        if dur < 4.5:
            st.error(traducir(f"El audio es muy corto ({dur:.1f} s). Por favor, graba al menos 5 segundos.", idioma))
            st.stop()
        else:
            audio_ok = True
    except Exception:
        st.error(traducir("No se pudo analizar la duración del audio. Intenta grabar de nuevo.", idioma))
        st.stop()
    st.session_state.audio = audio_bytes
    st.success(traducir("✅ ¡Audio guardado correctamente!", idioma))
else:
    # Panel estado grabado
    st.markdown(f"""
    <div class='record-panel recorded' id='record-panel'>
      <h3>🎤 {traducir('Grabación de voz', idioma)} <span class='badge-status success'>{txt_grabado}</span></h3>
      <div class='record-indicator compact'>
        <div class='mic-pulse stopped'></div>
        <div class='record-msg'>{traducir('Tu audio está listo para analizar.', idioma)}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    audio_ok = True
    # Botón Re-grabar
    if st.button(traducir("🔄 Re-grabar", idioma), key="re_record"):
        for k in ["audio","analyzed","proba","rows","final_interps","diag_label","recomendacion_extensa","sano_p","park_p","ready_for_pdf","pdf_bytes","ml_report_bytes"]:
            st.session_state.pop(k, None)
        st.rerun()

# ── 2 · Reproducir y salvar ────────────────────────────────────
if audio_ok:
    st.audio(st.session_state.audio, format="audio/wav")
    with open("recording.wav", "wb") as f:
        f.write(st.session_state.audio)

# ── 3 · ANALIZAR ───────────────────────────────────────────────
analyze_col = st.column_config if False else None  # placeholder para mantener formato
analyze_label = traducir("🔍 Analizar", idioma)
if st.button(analyze_label, key="analyze") and audio_ok:
    st.session_state["analyzed"] = True

# --- Sección de análisis (después de presionar Analizar) ---
if st.session_state.get("analyzed") and audio_ok:
    spinner_msg = traducir("Extrayendo variables…", idioma)
    with st.spinner(spinner_msg):
        raw, clip, scl, y, proba = predict_parkinson("recording.wav")
    st.session_state["proba"] = proba

    tab_vars, tab_interps, tab_diag, tab_descargas = st.tabs([
        traducir("Variables", idioma),
        traducir("Interpretaciones", idioma),
        traducir("Diagnóstico", idioma),
        traducir("Descargas", idioma)
    ])

    # 1) Variables
    with tab_vars:
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
        cols_hdr = [traducir(x, idioma) for x in ["Variable","Bruto","Clip","Min","Max"]]
        rows = [(f, raw[f], clip[f], *RANGE[f]) for f in MODEL_FEATURES]
        st.session_state["rows"] = rows
        df_vars = pd.DataFrame(rows, columns=cols_hdr)
        st.dataframe(df_vars, hide_index=True, use_container_width=True)

    # 2) Interpretaciones
    with tab_interps:
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
        detalles = []
        for feat in MODEL_FEATURES:
            desc = FEATURE_DESCRIPTIONS.get(feat, "")
            clip_val = clip[feat]
            detalles.append(f"{feat}: {desc} | Valor actual (clip): {clip_val:.3f}")
        detalle = "\n".join(detalles)
        try:
            text_ia = get_feature_interpretations(detalle)
        except GeminiError as e:
            text_ia = f"Error IA: {e}"
        if idioma != "es":
            text_ia = traducir(text_ia, idioma)
        parsed = parse_feature_interpretations_response(text_ia)
        final_interps = []
        for feat in MODEL_FEATURES:
            desc = parsed.get(feat)
            if not desc:
                desc = traducir("Este indicador de voz es relevante. Recuerda mantener tu voz clara y relajada.", idioma)
            final_interps.append((feat, desc))
        st.session_state["final_interps"] = final_interps
        df_ia = pd.DataFrame(final_interps, columns=[traducir("Variable", idioma), traducir("Interpretación", idioma)])
        st.dataframe(df_ia, use_container_width=True)

    # 3) Diagnóstico
    with tab_diag:
        sano_p, park_p = proba[1], proba[0]
        paciente = st.session_state.get("paciente", "Paciente")
        if sano_p >= 0.7:
            estado = "saludable"
        elif park_p >= 0.7:
            estado = "riesgo"
        else:
            estado = "intermedio"
        cards = {
            "saludable": {"icon": "✅", "title": f"¡{paciente}, tu estado es Saludable!", "text":  f"Sano {sano_p:.1%} · Parkinson {park_p:.1%}"},
            "intermedio": {"icon": "⚠️", "title": f"{paciente}, estado Intermedio", "text":  f"Sano {sano_p:.1%} · Parkinson {park_p:.1%}"},
            "riesgo": {"icon": "❌", "title": f"{paciente}, Alto Riesgo", "text":  f"Sano {sano_p:.1%} · Parkinson {park_p:.1%}"}
        }
        bg_colors = {"saludable": "#2ecc71","intermedio": "#f1c40f","riesgo": "#e74c3c"}
        inactive_bg, active_text, inactive_text = "#f0f0f0","#ffffff","#333333"
        st.subheader(traducir("🩺 Resultado y Recomendaciones", idioma))
        card_html_blocks = []
        for key in ("saludable","intermedio","riesgo"):
            card = cards[key]
            is_active = (key == estado)
            title = traducir(card["title"], idioma)
            text  = traducir(card["text"],  idioma)
            cls = "state-card active" if is_active else "state-card"
            card_html_blocks.append(
                f"<div class='{cls}'><span class='state-icon'>{card['icon']}</span><div><div class='state-title'>{title}</div><div class='state-sub'>{text}</div></div></div>"
            )
        st.markdown("<div class='state-cards'>" + "".join(card_html_blocks) + "</div>", unsafe_allow_html=True)
        st.markdown("<div class='prob-bars'>" +
            f"<div>{traducir('Probabilidad Sano', idioma)}: {sano_p:.1%}<div class='prob-bar animated'><span style='width:{sano_p*100:.1f}%;background:linear-gradient(90deg,#2ecc71,#27ae60)'></span></div></div>" +
            f"<div>{traducir('Probabilidad Parkinson', idioma)}: {park_p:.1%}<div class='prob-bar animated'><span style='width:{park_p*100:.1f}%;background:linear-gradient(90deg,#e74c3c,#c0392b)'></span></div></div>" +
            "</div>", unsafe_allow_html=True)
        try:
            rec_ia = get_short_recommendation(paciente, sano_p, park_p)
        except GeminiError as e:
            rec_ia = f"Error IA: {e}"
        if idioma != "es":
            rec_ia = traducir(rec_ia, idioma)
        st.markdown(traducir("#### Recomendación breve", idioma))
        fallback = traducir("No se pudo obtener la recomendación IA.", idioma)
        st.markdown(
            f"""<div style='background:#e0f7fa;border-left:6px solid #00796b;border-radius:8px;padding:1rem 1.3rem;margin-bottom:1rem;font-size:1.05rem;color:#114155;font-weight:500;'>💡 {rec_ia or fallback}</div>""",
            unsafe_allow_html=True
        )
        try:
            recomendacion_extensa = get_long_recommendation(paciente, sano_p, park_p)
        except GeminiError as e:
            recomendacion_extensa = f"Consulta siempre a un especialista. (Detalle: {e})"
        if idioma != "es":
            recomendacion_extensa = traducir(recomendacion_extensa, idioma)
        if estado == "saludable":
            diag_label = "Estado saludable"
        elif estado == "riesgo":
            diag_label = "Alta probabilidad de Parkinson"
        else:
            diag_label = "Estado intermedio"
        st.session_state["diag_label"] = traducir(diag_label, idioma)
        st.session_state["recomendacion_extensa"] = recomendacion_extensa
        st.session_state["sano_p"] = sano_p
        st.session_state["park_p"] = park_p
        st.session_state["ready_for_pdf"] = True

    # 4) Descargas (contenido gestionado más adelante)
    with tab_descargas:
        st.write(traducir("Usa los botones al final para descargar los reportes.", idioma))



    # ——— BLOQUE PDF CON TRADUCCIÓN ———


    # build_report_pdf ahora se importa desde pdf_report.py


if st.session_state.get("analyzed") and st.session_state.get("ready_for_pdf"):
    paciente = st.session_state.get("paciente", "Paciente")
    rows = st.session_state.get("rows", [])
    final_interps = st.session_state.get("final_interps", [])
    diag_label = st.session_state.get("diag_label", "")
    sano_p = st.session_state.get("sano_p")
    park_p = st.session_state.get("park_p")
    recomendacion_extensa = st.session_state.get("recomendacion_extensa", "")

    if None not in (sano_p, park_p) and rows and final_interps:
        if "pdf_bytes" not in st.session_state:
            st.session_state.pdf_bytes = build_report_pdf(
                traducir,
                paciente,
                rows,
                final_interps,
                diag_label,
                sano_p,
                park_p,
                recomendacion_extensa,
                idioma,
            )

        if "ml_report_bytes" not in st.session_state:
            try:
                with open("models/reporte_modelos.pdf", "rb") as f:
                    st.session_state.ml_report_bytes = f.read()
            except FileNotFoundError:
                st.session_state.ml_report_bytes = None

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                label=traducir("📥 Descargar Informe detallado (PDF)", idioma),
                data=st.session_state.pdf_bytes,
                file_name=f"reporte_{paciente.replace(' ','_')}.pdf",
                mime="application/pdf",
                key="download_detailed_report"
            )
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
    else:
        st.info(traducir("Realiza el análisis para generar los reportes.", idioma))