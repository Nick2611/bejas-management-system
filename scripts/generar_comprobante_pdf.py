#!/usr/bin/env python3
"""
generar_comprobante_pdf.py
──────────────────────────
Genera un comprobante PDF de Factura C estilo AFIP/ARCA con QR oficial (RG 4892).
Usa reportlab (pure Python, sin dependencias nativas en Windows).

Dependencias: pip install reportlab "qrcode[pil]" pillow
Uso:          python scripts/generar_comprobante_pdf.py
"""

import base64
import io
import json
import sys
from pathlib import Path
from datetime import date

# ── UTF-8 en consola Windows ──────────────────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import qrcode
from PIL import Image as PILImage

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable, Image as RLImage,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ═══════════════════════════════════════════════════════════════════════════════
# DATOS DEL COMPROBANTE
# ═══════════════════════════════════════════════════════════════════════════════
EMISOR = {
    "nombre":      "Bejas",
    "domicilio":   "Fray Justo Santa María de Oro 2447, CABA",
    "iva":         "Responsable Monotributo",
    "cuit":        27287927490,
    "iibb":        "Exento",
    "inicio":      "01/06/2026",
}

COMPROBANTE = {
    "tipo_letra":  "C",
    "tipo_nombre": "FACTURA",
    "tipo_cod":    11,
    "pto_venta":   1,
    "numero":      1,
    "fecha":       "29/06/2026",
    "fecha_iso":   "2026-06-29",
}

RECEPTOR = {
    "nombre":  "Consumidor Final",
    "domicilio": "",
    "iva":     "Consumidor Final",
    "doc":     "",
}

ITEMS = [
    {"descripcion": "Consumición", "cantidad": 1, "precio": 1000.00, "subtotal": 1000.00},
]

TOTALES = {
    "subtotal": 1000.00,
    "total":    1000.00,
}

CAE = {
    "numero":  86260509443592,
    "vto":     "09/07/2026",
}

# ── Datos QR según RG 4892 ────────────────────────────────────────────────────
QR_PAYLOAD = {
    "ver":         1,
    "fecha":       COMPROBANTE["fecha_iso"],
    "cuit":        EMISOR["cuit"],
    "ptoVta":      COMPROBANTE["pto_venta"],
    "tipoCmp":     COMPROBANTE["tipo_cod"],
    "nroCmp":      COMPROBANTE["numero"],
    "importe":     int(TOTALES["total"]),
    "moneda":      "PES",
    "ctz":         1,
    "tipoDocRec":  99,
    "nroDocRec":   0,
    "tipoCodAut":  "E",
    "codAut":      CAE["numero"],
}

OUTPUT_DIR  = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / f"comprobante_FC_{COMPROBANTE['pto_venta']:04d}-{COMPROBANTE['numero']:08d}.pdf"

# ═══════════════════════════════════════════════════════════════════════════════
# COLORES
# ═══════════════════════════════════════════════════════════════════════════════
GRIS_OSCURO  = colors.HexColor("#2c2c2c")
GRIS_MEDIO   = colors.HexColor("#555555")
GRIS_BORDE   = colors.HexColor("#999999")
GRIS_HEADER  = colors.HexColor("#f0f0f0")
GRIS_FILA    = colors.HexColor("#fafafa")
NEGRO        = colors.black
BLANCO       = colors.white


# ═══════════════════════════════════════════════════════════════════════════════
# QR
# ═══════════════════════════════════════════════════════════════════════════════
def build_qr_image() -> io.BytesIO:
    """Genera el QR oficial AFIP (RG 4892) y devuelve un buffer PNG."""
    json_str  = json.dumps(QR_PAYLOAD, separators=(",", ":"), ensure_ascii=False)
    b64_datos = base64.b64encode(json_str.encode("utf-8")).decode("ascii")
    url       = f"https://www.afip.gob.ar/fe/qr/?p={b64_datos}"

    print(f"   QR URL: {url[:80]}...")
    print(f"   JSON:   {json_str}")

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# ═══════════════════════════════════════════════════════════════════════════════
# ESTILOS DE PÁRRAFO
# ═══════════════════════════════════════════════════════════════════════════════
def make_styles():
    base = getSampleStyleSheet()

    def ps(name, **kw):
        defaults = dict(fontName="Helvetica", fontSize=9, leading=12,
                        textColor=GRIS_OSCURO)
        defaults.update(kw)
        return ParagraphStyle(name, **defaults)

    return {
        "titulo":     ps("titulo",    fontSize=16, fontName="Helvetica-Bold",
                         alignment=TA_CENTER, spaceAfter=2),
        "subtitulo":  ps("subtitulo", fontSize=8,  alignment=TA_CENTER, textColor=GRIS_MEDIO),
        "bold":       ps("bold",      fontName="Helvetica-Bold"),
        "normal":     ps("normal"),
        "small":      ps("small",     fontSize=7.5, textColor=GRIS_MEDIO),
        "right":      ps("right",     alignment=TA_RIGHT),
        "right_bold": ps("right_bold", alignment=TA_RIGHT, fontName="Helvetica-Bold"),
        "center":     ps("center",    alignment=TA_CENTER),
        "center_bold":ps("center_bold", alignment=TA_CENTER, fontName="Helvetica-Bold"),
        "cae":        ps("cae",       fontSize=8, textColor=GRIS_MEDIO),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ENCABEZADO — layout clásico AFIP: izq | C | der
# ═══════════════════════════════════════════════════════════════════════════════
def build_header(S) -> Table:
    # Columna izquierda — datos del emisor
    izq = [
        Paragraph(f"<b>{EMISOR['nombre']}</b>", S["bold"]),
        Paragraph(EMISOR["domicilio"], S["small"]),
        Spacer(1, 3),
        Paragraph(f"<b>CUIT:</b> {EMISOR['cuit']}", S["small"]),
        Paragraph(f"<b>Condición frente al IVA:</b> {EMISOR['iva']}", S["small"]),
        Paragraph(f"<b>Ing. Brutos:</b> {EMISOR['iibb']}", S["small"]),
        Paragraph(f"<b>Inicio de actividades:</b> {EMISOR['inicio']}", S["small"]),
    ]

    # Centro — recuadro con la letra del comprobante
    centro = [
        Paragraph("C", ParagraphStyle("letra", fontName="Helvetica-Bold",
                                       fontSize=52, leading=54,
                                       alignment=TA_CENTER, textColor=NEGRO)),
        Paragraph(f"COD. {COMPROBANTE['tipo_cod']:02d}",
                  ParagraphStyle("cod", fontName="Helvetica", fontSize=8,
                                 alignment=TA_CENTER, textColor=GRIS_MEDIO)),
    ]

    # Columna derecha — datos del comprobante
    pv_fmt  = f"{COMPROBANTE['pto_venta']:04d}"
    num_fmt = f"{COMPROBANTE['numero']:08d}"
    der = [
        Paragraph(f"<b>{COMPROBANTE['tipo_nombre']} {COMPROBANTE['tipo_letra']}</b>",
                  S["bold"]),
        Spacer(1, 4),
        Paragraph(f"<b>Punto de Venta:</b> {pv_fmt}", S["small"]),
        Paragraph(f"<b>Comprobante N°:</b> {num_fmt}", S["small"]),
        Spacer(1, 6),
        Paragraph(f"<b>Fecha de emisión:</b> {COMPROBANTE['fecha']}", S["small"]),
    ]

    data = [[izq, centro, der]]
    t = Table(data, colWidths=[7.5*cm, 3.2*cm, 7.5*cm])
    t.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("ALIGN",       (1, 0), (1, 0),  "CENTER"),
        ("BOX",         (1, 0), (1, 0),  1.5, NEGRO),
        ("TOPPADDING",  (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0,0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (0, 0),  0),
        ("RIGHTPADDING",(-1,0), (-1, 0), 0),
        ("LINEAFTER",   (0, 0), (0, 0),  0.5, GRIS_BORDE),
        ("LINEBEFORE",  (2, 0), (2, 0),  0.5, GRIS_BORDE),
    ]))
    return t


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN RECEPTOR
# ═══════════════════════════════════════════════════════════════════════════════
def build_receptor(S) -> Table:
    data = [
        [
            Paragraph(f"<b>Razón Social / Nombre:</b> {RECEPTOR['nombre']}", S["normal"]),
            Paragraph(f"<b>Condición IVA:</b> {RECEPTOR['iva']}", S["normal"]),
        ],
        [
            Paragraph(f"<b>Domicilio:</b> {RECEPTOR['domicilio'] or '—'}", S["small"]),
            Paragraph(f"<b>CUIT / DNI:</b> {RECEPTOR['doc'] or '—'}", S["small"]),
        ],
    ]
    t = Table(data, colWidths=[9.5*cm, 8.7*cm])
    t.setStyle(TableStyle([
        ("BOX",          (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("INNERGRID",    (0, 0), (-1, -1), 0.25, GRIS_BORDE),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("BACKGROUND",   (0, 0), (-1, 0),  GRIS_HEADER),
    ]))
    return t


# ═══════════════════════════════════════════════════════════════════════════════
# TABLA DE ITEMS
# ═══════════════════════════════════════════════════════════════════════════════
def build_items(S) -> Table:
    header = [
        Paragraph("<b>Cód.</b>",        S["center_bold"]),
        Paragraph("<b>Descripción</b>",  S["bold"]),
        Paragraph("<b>Cantidad</b>",     S["center_bold"]),
        Paragraph("<b>Precio Unit.</b>", S["right_bold"]),
        Paragraph("<b>Subtotal</b>",     S["right_bold"]),
    ]
    rows = [header]
    for i, item in enumerate(ITEMS):
        rows.append([
            Paragraph("—", S["center"]),
            Paragraph(item["descripcion"], S["normal"]),
            Paragraph(str(item["cantidad"]), S["center"]),
            Paragraph(f"${item['precio']:,.2f}", S["right"]),
            Paragraph(f"${item['subtotal']:,.2f}", S["right"]),
        ])

    t = Table(rows, colWidths=[1.5*cm, 9.2*cm, 2.0*cm, 2.8*cm, 2.7*cm])
    t.setStyle(TableStyle([
        ("BOX",          (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("INNERGRID",    (0, 0), (-1, -1), 0.25, GRIS_BORDE),
        ("BACKGROUND",   (0, 0), (-1, 0),  GRIS_HEADER),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


# ═══════════════════════════════════════════════════════════════════════════════
# TOTALES
# ═══════════════════════════════════════════════════════════════════════════════
def build_totales(S) -> Table:
    filas = [
        [Paragraph("<b>Subtotal</b>", S["right_bold"]),
         Paragraph(f"${TOTALES['subtotal']:,.2f}", S["right"])],
        [Paragraph("<b>Importe Total</b>", ParagraphStyle(
            "total_lbl", fontName="Helvetica-Bold", fontSize=10,
            alignment=TA_RIGHT, textColor=NEGRO)),
         Paragraph(f"<b>${TOTALES['total']:,.2f}</b>", ParagraphStyle(
            "total_val", fontName="Helvetica-Bold", fontSize=10,
            alignment=TA_RIGHT, textColor=NEGRO))],
    ]
    t = Table(filas, colWidths=[4.0*cm, 3.0*cm])
    t.setStyle(TableStyle([
        ("ALIGN",        (0, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LINEABOVE",    (0, -1), (-1, -1), 1.0, NEGRO),
        ("BOX",          (0, 0), (-1, -1), 0.5, GRIS_BORDE),
    ]))
    return t


# ═══════════════════════════════════════════════════════════════════════════════
# PIE — QR + CAE
# ═══════════════════════════════════════════════════════════════════════════════
def build_pie(S, qr_buf) -> Table:
    qr_img = RLImage(qr_buf, width=3.2*cm, height=3.2*cm)

    cae_block = [
        Paragraph("<b>Comprobante Autorizado</b>",
                  ParagraphStyle("auth", fontName="Helvetica-Bold", fontSize=9,
                                 textColor=NEGRO)),
        Spacer(1, 4),
        Paragraph(f"<b>CAE N°:</b> {CAE['numero']}", S["cae"]),
        Paragraph(f"<b>Fecha de Vto. CAE:</b> {CAE['vto']}", S["cae"]),
        Spacer(1, 8),
        Paragraph("Este comprobante fue generado en el entorno de<br/>homologación de AFIP/ARCA.",
                  ParagraphStyle("aviso", fontSize=7, textColor=GRIS_MEDIO, leading=9)),
    ]

    t = Table([[qr_img, cae_block]], colWidths=[3.8*cm, 14.4*cm])
    t.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0),   0),
        ("LEFTPADDING", (1, 0), (1, 0),   12),
        ("TOPPADDING",  (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0,0), (-1, -1), 6),
        ("BOX",         (0, 0), (-1, -1), 0.5, GRIS_BORDE),
    ]))
    return t


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    print("=" * 62)
    print("  GENERADOR DE COMPROBANTE PDF — FACTURA C")
    print("=" * 62)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("\n→  Generando QR oficial AFIP (RG 4892)…")
    qr_buf = build_qr_image()
    print("✓  QR generado")

    print("→  Construyendo PDF…")
    S = make_styles()

    doc = SimpleDocTemplate(
        str(OUTPUT_FILE),
        pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.5*cm,  bottomMargin=1.5*cm,
        title=f"Factura C {COMPROBANTE['pto_venta']:04d}-{COMPROBANTE['numero']:08d}",
        author="Bejas",
    )

    story = []

    # ── Título de página ──────────────────────────────────────────────────────
    story.append(Paragraph(
        f"{COMPROBANTE['tipo_nombre']} {COMPROBANTE['tipo_letra']}",
        ParagraphStyle("page_title", fontName="Helvetica-Bold", fontSize=13,
                       alignment=TA_CENTER, spaceAfter=4, textColor=GRIS_OSCURO)
    ))
    story.append(HRFlowable(width="100%", thickness=1.2, color=NEGRO, spaceAfter=6))

    # ── Encabezado ────────────────────────────────────────────────────────────
    story.append(build_header(S))
    story.append(Spacer(1, 0.35*cm))

    # ── Receptor ─────────────────────────────────────────────────────────────
    story.append(Paragraph("<b>DATOS DEL RECEPTOR</b>",
                            ParagraphStyle("sec", fontName="Helvetica-Bold",
                                           fontSize=7.5, textColor=GRIS_MEDIO,
                                           spaceBefore=4, spaceAfter=3)))
    story.append(build_receptor(S))
    story.append(Spacer(1, 0.35*cm))

    # ── Detalle ───────────────────────────────────────────────────────────────
    story.append(Paragraph("<b>DETALLE</b>",
                            ParagraphStyle("sec2", fontName="Helvetica-Bold",
                                           fontSize=7.5, textColor=GRIS_MEDIO,
                                           spaceBefore=4, spaceAfter=3)))
    story.append(build_items(S))
    story.append(Spacer(1, 0.25*cm))

    # ── Totales alineados a la derecha ────────────────────────────────────────
    outer = Table(
        [[Spacer(1, 1), build_totales(S)]],
        colWidths=[11.2*cm, 7.0*cm],
    )
    outer.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 0),
        ("TOPPADDING",  (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0,0), (-1, -1), 0),
    ]))
    story.append(outer)
    story.append(Spacer(1, 0.5*cm))

    # ── Pie con QR y CAE ──────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRIS_BORDE, spaceAfter=6))
    story.append(build_pie(S, qr_buf))

    doc.build(story)

    print(f"✓  PDF generado en:\n   {OUTPUT_FILE.resolve()}")
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        print("\n⛔  Error al generar el PDF:")
        traceback.print_exc()
        sys.exit(1)