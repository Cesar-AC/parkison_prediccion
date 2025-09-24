"""Generación del PDF de reporte para Parkinson Detector.

Separado desde app.py para mantener la vista más limpia.
La función principal: build_report_pdf(...) devuelve bytes del PDF.
"""
from fpdf import FPDF
from datetime import datetime


def build_report_pdf(
    traducir_func,
    paciente: str,
    rows,
    final_interps,
    diag_label: str,
    sano_p: float,
    park_p: float,
    recomendacion_extensa: str,
    idioma: str,
) -> bytes:
    """Construye y devuelve los bytes del PDF.

    Params:
        traducir_func: función de traducción (texto:str, dest:str)->str para no acoplar a Streamlit.
        paciente: nombre del paciente
        rows: iterable con (feature, raw, clip, min, max)
        final_interps: iterable con (feature, interpretación)
        diag_label: etiqueta de diagnóstico traducida
        sano_p, park_p: probabilidades
        recomendacion_extensa: texto extenso IA (ya traducido si aplica)
        idioma: código de idioma destino
    """
    def sanitize(txt: str) -> str:
        return (txt or "").encode("latin-1", "ignore").decode("latin-1")

    pdf = FPDF(format="A4")
    pdf.set_left_margin(15)
    pdf.set_right_margin(15)
    pdf.set_top_margin(12)
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()

    # Encabezado
    titulo_pdf = traducir_func("Reporte Personalizado de Fonética Vocal y Parkinson", idioma)
    label_pac = traducir_func("Paciente:", idioma)
    label_fecha = traducir_func("Fecha de análisis:", idioma)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, sanitize(titulo_pdf), ln=True, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, sanitize(f"{label_pac} {paciente}"), ln=True)
    pdf.cell(0, 8, sanitize(f"{label_fecha} {datetime.now():%Y-%m-%d %H:%M:%S}"), ln=True, align="R")
    pdf.ln(4)

    # Introducción
    intro = traducir_func(
        "Hola, espero que tengas una excelente jornada. "
        "Este reporte es un resumen detallado del análisis de tu voz "
        "para apoyar el cuidado de tu salud.",
        idioma,
    )
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 8, sanitize(intro))
    pdf.ln(4)

    # Tabla variables
    sec_vars = traducir_func("Variables Analizadas", idioma)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, sanitize(sec_vars), ln=True)

    col_w = [60, 35, 35]
    headers = [
        traducir_func("Variable", idioma),
        traducir_func("Bruto", idioma),
        traducir_func("Clip", idioma),
    ]
    pdf.set_font("Helvetica", "B", 10)
    for w, h in zip(col_w, headers):
        pdf.cell(w, 7, sanitize(h), 1, 0, "C")
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for feat, raw_val, clip_val, *_ in rows:
        pdf.cell(col_w[0], 7, sanitize(str(feat)), 1)
        pdf.cell(col_w[1], 7, f"{raw_val:.3f}", 1)
        pdf.cell(col_w[2], 7, f"{clip_val:.3f}", 1)
        pdf.ln()
    pdf.ln(3)

    # Explicación de la tabla
    explic = traducir_func(
        "En la tabla anterior se muestran las variables extraídas de tu voz. "
        "La columna 'Bruto' representa los valores originales captados de tu grabación, "
        "mientras que 'Clip' corresponde a los valores ajustados al rango estándar de referencia. "
        "Estas mediciones ayudan a analizar características de tu voz que pueden relacionarse "
        "con salud vocal y detección temprana de Parkinson.",
        idioma,
    )
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 7, sanitize(explic))
    pdf.ln(4)

    # Interpretaciones IA
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, sanitize(traducir_func("Interpretación de cada variable (IA)", idioma)), ln=True)
    pdf.set_font("Helvetica", "B", 10)

    w_feat, w_interp = 60, 110
    cell_h = 6
    pdf.cell(w_feat, 10, sanitize(traducir_func("Variable", idioma)), 1, 0, "C")
    pdf.cell(w_interp, 10, sanitize(traducir_func("Interpretación", idioma)), 1, 1, "C")
    pdf.set_font("Helvetica", "", 9)
    for feat, texto in final_interps:
        x0, y0 = pdf.get_x(), pdf.get_y()
        pdf.multi_cell(w_feat, cell_h, sanitize(str(feat)), border=1)
        y_feat_end = pdf.get_y()
        pdf.set_xy(x0 + w_feat, y0)
        pdf.multi_cell(w_interp, cell_h, sanitize(texto), border=1)
        y_interp_end = pdf.get_y()
        pdf.set_xy(x0, max(y_feat_end, y_interp_end))
    pdf.ln(4)

    # Resultados
    sec_res = traducir_func("Resultados del análisis", idioma)
    label_diag = traducir_func("Diagnóstico:", idioma)
    label_ps = traducir_func("Probabilidad Sano:", idioma)
    label_pp = traducir_func("Probabilidad Parkinson:", idioma)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, sanitize(sec_res), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(0, 80, 0)
    texto_res = (
        f"{label_diag} {diag_label}\n"
        f"{label_ps} {sano_p:.1%} | {label_pp} {park_p:.1%}"
    )
    pdf.multi_cell(0, 7, sanitize(texto_res))
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # Recomendaciones
    sec_rec = traducir_func("Recomendaciones personalizadas", idioma)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, sanitize(sec_rec), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 7, sanitize(recomendacion_extensa))
    pdf.ln(4)

    raw = pdf.output(dest="S")
    return raw.encode("latin-1") if isinstance(raw, str) else bytes(raw)
