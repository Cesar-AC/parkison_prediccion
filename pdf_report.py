"""Generación del PDF de reporte para Parkinson Detector (versión estilizada).

Se mantiene la misma firma pública de ``build_report_pdf`` para compatibilidad con ``app.py``.
Se mejora la presentación visual usando una paleta suave y estructura de informe médico:

- Encabezado centrado con título y fecha
- Caja de información del paciente
- Secciones con barras de color y espaciado uniforme
- Tablas con cabecera destacada y zebra striping sutil
- Resultados resumidos en una banda resaltada
- Pie de página con numeración
"""
from datetime import datetime
from fpdf import FPDF

# Paleta (azules / verdes suaves orientados a entorno médico)
PRIMARY_RGB = (34, 102, 153)      # Azul médico
ACCENT_RGB = (30, 140, 110)       # Verde salud
LIGHT_BG = (235, 244, 249)        # Fondo celeste claro
ZEBRA_BG = (245, 249, 251)
HEADER_TXT = (255, 255, 255)
GRAY_TXT = (70, 70, 70)


class MedicalPDF(FPDF):
    def header(self):  # pragma: no cover (dibujo)
        # Barra superior
        self.set_fill_color(*PRIMARY_RGB)
        self.rect(0, 0, 210, 18, "F")  # ancho A4
        self.set_y(4)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*HEADER_TXT)
        self.cell(0, 8, getattr(self, "_title", ""), align="C", ln=1)
        self.set_font("Helvetica", size=8)
        self.cell(0, 6, getattr(self, "_subtitle", ""), align="C")
        self.ln(2)
        # Reset para contenido
        self.set_text_color(0, 0, 0)
        self.set_y(22)

    def footer(self):  # pragma: no cover
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Página {self.page_no()}/{{nb}}", align="C")


def _sanitize(txt: str) -> str:
    return (txt or "").encode("latin-1", "ignore").decode("latin-1")


def _section_title(pdf: FPDF, text: str):
    pdf.set_fill_color(*PRIMARY_RGB)
    pdf.set_text_color(*HEADER_TXT)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, _sanitize(text), ln=1, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)


def _patient_box(pdf: FPDF, paciente: str, fecha: str, label_pac: str, label_fecha: str):
    pdf.set_fill_color(*LIGHT_BG)
    pdf.set_draw_color(*PRIMARY_RGB)
    pdf.set_line_width(0.3)
    x, y = pdf.get_x(), pdf.get_y()
    w = 0  # full width via cell(0,...)
    pdf.set_font("Helvetica", size=10)
    contenido = f"{label_pac} {paciente}\n{label_fecha} {fecha}"
    start_y = pdf.get_y()
    pdf.multi_cell(0, 6, _sanitize(contenido), border=1, fill=True)
    end_y = pdf.get_y()
    pdf.ln(2)
    pdf.set_y(end_y + 1)


def _table_header(pdf: FPDF, headers, widths, center=False):
    total_w = sum(widths)
    start_x = pdf.get_x()
    if center:
        # Centrar en el ancho usable (ancho página - márgenes)
        usable = pdf.w - pdf.l_margin - pdf.r_margin
        offset = (usable - total_w) / 2
        pdf.set_x(pdf.l_margin + max(0, offset))
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(*PRIMARY_RGB)
    pdf.set_text_color(*HEADER_TXT)
    for h, w in zip(headers, widths):
        pdf.cell(w, 7, _sanitize(h), border=1, align="C", fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    if center:
        pdf.set_x(start_x)


def _table_row(pdf: FPDF, cells, widths, zebra=False, center=False):
    pdf.set_font("Helvetica", size=8)
    total_w = sum(widths)
    start_x = pdf.get_x()
    if center:
        usable = pdf.w - pdf.l_margin - pdf.r_margin
        offset = (usable - total_w) / 2
        pdf.set_x(pdf.l_margin + max(0, offset))
    if zebra:
        pdf.set_fill_color(*ZEBRA_BG)
    for c, w in zip(cells, widths):
        pdf.cell(w, 6, _sanitize(str(c)), border=1, align="C", fill=zebra)
    pdf.ln()
    if center:
        pdf.set_x(start_x)


def _interpretation_table(pdf: FPDF, headers, data, widths, center=True):
    # Cabecera centrada
    total_w = sum(widths)
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    offset = (usable - total_w) / 2 if center else 0
    start_x_global = pdf.get_x()
    if center:
        pdf.set_x(pdf.l_margin + max(0, offset))
    _table_header(pdf, headers, widths)
    pdf.set_font("Helvetica", size=8)
    col1_w, col2_w = widths
    line_h = 5
    zebra = False
    while data:
        feat, texto = data[0]
        zebra = not zebra
        # Calcular altura necesaria de interpretación antes de escribir para equilibrar celda de feature
        # Guardar posición
        x_start = pdf.get_x(); y_start = pdf.get_y()
        if center:
            pdf.set_x(pdf.l_margin + max(0, offset))
        if zebra:
            pdf.set_fill_color(*ZEBRA_BG)
        # Temporariamente escribir interpretación para medir
        # Escribimos feature con multi_cell y luego interpretación ajustando alturas
        # Feature
        pdf.multi_cell(col1_w, line_h, _sanitize(str(feat)), border=1, fill=zebra)
        y_feat_end = pdf.get_y()
        # Interpretación
        pdf.set_xy(x_start + col1_w, y_start)
        pdf.multi_cell(col2_w, line_h, _sanitize(texto), border=1, fill=zebra)
        y_interp_end = pdf.get_y()
        pdf.set_xy(x_start, max(y_feat_end, y_interp_end))
        data = data[1:]
    if center:
        pdf.set_x(start_x_global)


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

    La firma se conserva igual. ``rows``: iterable (feature, raw, clip, ...). ``final_interps``: (feature, texto).
    """

    pdf = MedicalPDF(format="A4")
    pdf.alias_nb_pages()
    pdf.set_left_margin(15)
    pdf.set_right_margin(15)
    pdf.set_top_margin(22)
    pdf.set_auto_page_break(True, margin=15)

    # Etiquetas traducidas
    titulo_pdf = traducir_func("Reporte Personalizado de Fonética Vocal y Parkinson", idioma)
    pdf._title = _sanitize(titulo_pdf[:90])  # atributos usados por header
    pdf._subtitle = _sanitize(traducir_func("Informe clínico de análisis vocal asistido por IA", idioma))
    label_pac = traducir_func("Paciente:", idioma)
    label_fecha = traducir_func("Fecha de análisis:", idioma)
    fecha_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    pdf.add_page()

    # Caja paciente
    _patient_box(pdf, paciente, fecha_str, label_pac, label_fecha)

    # Introducción
    intro = traducir_func(
        "Este informe presenta un análisis de parámetros acústicos de tu voz. "
        "La evaluación no constituye por sí sola un diagnóstico definitivo; "
        "considérala un apoyo complementario y consulta siempre a un profesional de salud.",
        idioma,
    )
    pdf.set_font("Helvetica", size=9)
    pdf.multi_cell(0, 5.5, _sanitize(intro))
    pdf.ln(3)

    # Sección Variables Analizadas
    _section_title(pdf, traducir_func("Variables Analizadas", idioma))
    headers = [
        traducir_func("Variable", idioma),
        traducir_func("Bruto", idioma),
        traducir_func("Clip", idioma),
    ]
    widths = [70, 35, 35]
    _table_header(pdf, headers, widths, center=True)
    zebra = False
    for feat, raw_val, clip_val, *_ in rows:
        zebra = not zebra
        _table_row(pdf, [feat, f"{raw_val:.3f}", f"{clip_val:.3f}"], widths, zebra=zebra, center=True)
    pdf.ln(2)

    explic = traducir_func(
        "La columna 'Bruto' muestra el valor directo calculado a partir de la señal; 'Clip' es la versión limitada "
        "al rango de referencia para reducir outliers y facilitar comparaciones estables.",
        idioma,
    )
    pdf.set_font("Helvetica", size=8)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(0, 4.3, _sanitize(explic))
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # Interpretaciones
    _section_title(pdf, traducir_func("Interpretación de cada variable (IA)", idioma))
    _interpretation_table(
        pdf,
        [traducir_func("Variable", idioma), traducir_func("Interpretación", idioma)],
        list(final_interps),  # usar copia
        [55, 115],
        center=True,
    )
    pdf.ln(4)

    # Resultados del análisis (banda)
    _section_title(pdf, traducir_func("Resultados del análisis", idioma))
    label_diag = traducir_func("Diagnóstico:", idioma)
    label_ps = traducir_func("Probabilidad Sano:", idioma)
    label_pp = traducir_func("Probabilidad Parkinson:", idioma)
    # Caja formal para diagnóstico (un solo bloque para evitar desalineación)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_draw_color(*ACCENT_RGB)
    pdf.set_fill_color(245, 249, 251)
    diag_text = (
        f"{label_diag} {diag_label}\n"
        f"{label_ps} {sano_p:.1%}   |   {label_pp} {park_p:.1%}"
    )
    pdf.multi_cell(0, 8, _sanitize(diag_text), border=1, fill=True)
    pdf.ln(1)
    # Barra de probabilidades (visual simple) - ancho fijo 100mm centrado
    bar_w = 100
    bar_h = 8
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    bar_x = pdf.l_margin + (usable - bar_w) / 2
    bar_y = pdf.get_y() + 1
    # Fondo gris claro
    pdf.set_fill_color(230, 230, 230)
    pdf.rect(bar_x, bar_y, bar_w, bar_h, 'F')
    # Segmento sano (verde) y parkinson (naranja)
    sanow = bar_w * max(0, min(1, sano_p))
    parkw = bar_w * max(0, min(1, park_p))
    pdf.set_fill_color(60, 170, 110)
    pdf.rect(bar_x, bar_y, sanow, bar_h, 'F')
    pdf.set_fill_color(220, 120, 60)
    pdf.rect(bar_x + sanow, bar_y, parkw, bar_h, 'F')
    # Contorno
    pdf.set_draw_color(150, 150, 150)
    pdf.rect(bar_x, bar_y, bar_w, bar_h)
    # Porcentajes encima (centrados en cada segmento si suficiente espacio)
    pdf.set_font('Helvetica', 'B', 7)
    pdf.set_text_color(255,255,255)
    if sanow > 12:  # espacio mínimo
        pdf.set_xy(bar_x, bar_y+1.2)
        pdf.cell(sanow, 5, f"{sano_p:.0%}", align='C')
    if parkw > 12:
        pdf.set_xy(bar_x + sanow, bar_y+1.2)
        pdf.cell(parkw, 5, f"{park_p:.0%}", align='C')
    pdf.set_text_color(0,0,0)
    pdf.set_y(bar_y + bar_h + 3)
    pdf.set_font('Helvetica', size=7)
    pdf.set_text_color(90,90,90)
    pdf.cell(0,4, _sanitize(traducir_func('Distribución visual de probabilidades', idioma)), ln=1, align='C')
    pdf.set_text_color(0,0,0)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    aclaracion = traducir_func(
        "Estos resultados reflejan patrones estadísticos obtenidos mediante modelos de aprendizaje automático aplicados a características acústicas. "
        "No reemplazan evaluaciones neurológicas, pruebas motoras ni otros estudios clínicos complementarios.",
        idioma,
    )
    pdf.set_font("Helvetica", size=8)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(0, 4.3, _sanitize(aclaracion))
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)
    # Bloque explicativo adicional del diagnóstico
    extra_diag = traducir_func(
        "Interpretación del estado: Un resultado 'saludable' indica que los patrones vocales analizados se encuentran dentro de parámetros esperados. "
        "Si la probabilidad de Parkinson es moderada o alta, se recomienda evaluación clínica presencial para correlacionar con signos motores, cognitivos y antecedentes médicos.",
        idioma,
    )
    pdf.set_font('Helvetica', size=8)
    pdf.multi_cell(0,4.1,_sanitize(extra_diag))
    pdf.ln(3)

    # Recomendaciones personalizadas
    _section_title(pdf, traducir_func("Recomendaciones personalizadas", idioma))
    pdf.set_font("Helvetica", size=9)
    # Normalizar texto muy largo: cortar en ~5000 chars para evitar PDF gigantes no deseados
    if len(recomendacion_extensa) > 5000:
        recomendacion_extensa = recomendacion_extensa[:5000] + "..."
    pdf.multi_cell(0, 5.2, _sanitize(recomendacion_extensa))
    # Texto educativo adicional
    educativo = traducir_func(
        "Consejo general: Mantener hábitos de sueño adecuados, hidratación y ejercicios de articulación vocal puede ayudar a conservar la claridad de la voz. "
        "Cambios persistentes o progresivos deben ser revisados por un especialista.",
        idioma,
    )
    pdf.ln(1)
    pdf.set_font('Helvetica', size=8)
    pdf.set_text_color(70,70,70)
    pdf.multi_cell(0,4.1,_sanitize(educativo))
    pdf.set_text_color(0,0,0)
    pdf.ln(2)

    disclaimer = traducir_func(
        "Aviso: Este documento no reemplaza una evaluación médica presencial. Consulte a un profesional ante cualquier duda o síntoma.",
        idioma,
    )
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(0, 4, _sanitize(disclaimer))

    raw = pdf.output(dest="S")
    return raw.encode("latin-1") if isinstance(raw, str) else bytes(raw)
