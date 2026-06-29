"""
Generador de comprobantes PDF para facturas AFIP/ARCA.

Punto de entrada: generar_comprobante_pdf(invoice, emisor)
Devuelve bytes del PDF — no escribe nada a disco, listo para servir por HTTP.

Layout: encabezado clásico AFIP (izq | recuadro letra | der), tabla de detalle,
totales, pie con QR oficial RG 4892 + CAE + "Comprobante Autorizado".

Dependencias: reportlab>=4.0, qrcode[pil]>=7.4
"""

from __future__ import annotations

import base64
import io
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import qrcode
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_TIPO_COD    = 11
_TIPO_NOMBRE = "FACTURA"
_TIPO_LETRA  = "C"

# ── Colores ───────────────────────────────────────────────────────────────────
_GRIS_OSCURO = colors.HexColor("#2c2c2c")
_GRIS_MEDIO  = colors.HexColor("#555555")
_GRIS_BORDE  = colors.HexColor("#999999")
_GRIS_HEADER = colors.HexColor("#f0f0f0")
_NEGRO       = colors.black


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG DE EMISOR
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class EmisorConfig:
    """Datos fiscales del emisor. Valores por defecto para la demo Bejas."""
    nombre:             str = "Bejas"
    domicilio:          str = "Fray Justo Santa María de Oro 2447, CABA"
    cuit:               int = 27287927490
    condicion_iva:      str = "Responsable Monotributo"
    iibb:               str = "Exento"
    inicio_actividades: str = "01/06/2026"


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _fmt_money(value: int | float) -> str:
    """Formatea un número como $8.500,00 (estilo Argentina)."""
    return f"${value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _get(invoice: Any, attr: str, default=None):
    """Accede a un atributo por nombre tanto en objetos como en dicts."""
    if isinstance(invoice, dict):
        return invoice.get(attr, default)
    return getattr(invoice, attr, default)


def _build_qr_image(
    emisor: EmisorConfig,
    invoice: Any,
    tipo_cod: int,
) -> io.BytesIO:
    """Construye el QR oficial AFIP según RG 4892 y devuelve PNG en buffer."""
    issued_at = _get(invoice, "issued_at")
    if isinstance(issued_at, datetime):
        fecha_iso = issued_at.date().isoformat()
    elif isinstance(issued_at, date):
        fecha_iso = issued_at.isoformat()
    else:
        fecha_iso = str(issued_at)[:10]

    cae_raw = _get(invoice, "cae")
    cae_int = int(cae_raw) if cae_raw else 0

    payload = {
        "ver":        1,
        "fecha":      fecha_iso,
        "cuit":       emisor.cuit,
        "ptoVta":     int(_get(invoice, "point_of_sale", 1)),
        "tipoCmp":    tipo_cod,
        "nroCmp":     int(_get(invoice, "voucher_number", 1)),
        "importe":    int(_get(invoice, "total", 0)),
        "moneda":     "PES",
        "ctz":        1,
        "tipoDocRec": 99,
        "nroDocRec":  0,
        "tipoCodAut": "E",
        "codAut":     cae_int,
    }
    json_str = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    b64      = base64.b64encode(json_str.encode("utf-8")).decode("ascii")
    url      = f"https://www.afip.gob.ar/fe/qr/?p={b64}"

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


def _ps(name: str, **kw) -> ParagraphStyle:
    defaults = dict(fontName="Helvetica", fontSize=9, leading=12, textColor=_GRIS_OSCURO)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)


def _make_styles() -> dict[str, ParagraphStyle]:
    return {
        "bold":        _ps("bold",        fontName="Helvetica-Bold"),
        "normal":      _ps("normal"),
        "small":       _ps("small",       fontSize=7.5, textColor=_GRIS_MEDIO),
        "right":       _ps("right",       alignment=TA_RIGHT),
        "right_bold":  _ps("right_bold",  alignment=TA_RIGHT, fontName="Helvetica-Bold"),
        "center":      _ps("center",      alignment=TA_CENTER),
        "center_bold": _ps("center_bold", alignment=TA_CENTER, fontName="Helvetica-Bold"),
        "cae":         _ps("cae",         fontSize=8, textColor=_GRIS_MEDIO),
        "sec_label":   _ps("sec_label",   fontName="Helvetica-Bold", fontSize=7.5,
                            textColor=_GRIS_MEDIO, spaceBefore=4, spaceAfter=3),
    }


# ── Bloques de la página ──────────────────────────────────────────────────────

def _build_header(S, emisor: EmisorConfig, invoice: Any,
                  tipo_cod: int, tipo_nombre: str, tipo_letra: str) -> Table:
    issued_at = _get(invoice, "issued_at")
    if isinstance(issued_at, datetime):
        fecha_str = issued_at.strftime("%d/%m/%Y")
    else:
        fecha_str = str(issued_at)[:10]

    pv  = int(_get(invoice, "point_of_sale", 1))
    num = int(_get(invoice, "voucher_number", 1))

    izq = [
        Paragraph(f"<b>{emisor.nombre}</b>", S["bold"]),
        Paragraph(emisor.domicilio, S["small"]),
        Spacer(1, 3),
        Paragraph(f"<b>CUIT:</b> {emisor.cuit}", S["small"]),
        Paragraph(f"<b>Condición frente al IVA:</b> {emisor.condicion_iva}", S["small"]),
        Paragraph(f"<b>Ing. Brutos:</b> {emisor.iibb}", S["small"]),
        Paragraph(f"<b>Inicio de actividades:</b> {emisor.inicio_actividades}", S["small"]),
    ]

    centro = [
        Paragraph(tipo_letra, ParagraphStyle(
            "letra", fontName="Helvetica-Bold", fontSize=52, leading=54,
            alignment=TA_CENTER, textColor=_NEGRO,
        )),
        Paragraph(f"COD. {tipo_cod:02d}", ParagraphStyle(
            "cod", fontName="Helvetica", fontSize=8,
            alignment=TA_CENTER, textColor=_GRIS_MEDIO,
        )),
    ]

    der = [
        Paragraph(f"<b>{tipo_nombre} {tipo_letra}</b>", S["bold"]),
        Spacer(1, 4),
        Paragraph(f"<b>Punto de Venta:</b> {pv:04d}", S["small"]),
        Paragraph(f"<b>Comprobante N°:</b> {num:08d}", S["small"]),
        Spacer(1, 6),
        Paragraph(f"<b>Fecha de emisión:</b> {fecha_str}", S["small"]),
    ]

    t = Table([[izq, centro, der]], colWidths=[7.5*cm, 3.2*cm, 7.5*cm])
    t.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("ALIGN",        (1, 0), (1, 0),   "CENTER"),
        ("BOX",          (1, 0), (1, 0),   1.5, _NEGRO),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("LEFTPADDING",  (0, 0), (0, 0),   0),
        ("RIGHTPADDING", (-1,0), (-1, 0),  0),
        ("LINEAFTER",    (0, 0), (0, 0),   0.5, _GRIS_BORDE),
        ("LINEBEFORE",   (2, 0), (2, 0),   0.5, _GRIS_BORDE),
    ]))
    return t


def _build_receptor(S) -> Table:
    data = [
        [
            Paragraph("<b>Razón Social / Nombre:</b> Consumidor Final", S["normal"]),
            Paragraph("<b>Condición IVA:</b> Consumidor Final", S["normal"]),
        ],
        [
            Paragraph("<b>Domicilio:</b> —", S["small"]),
            Paragraph("<b>CUIT / DNI:</b> —", S["small"]),
        ],
    ]
    t = Table(data, colWidths=[9.5*cm, 8.7*cm])
    t.setStyle(TableStyle([
        ("BOX",          (0, 0), (-1, -1), 0.5, _GRIS_BORDE),
        ("INNERGRID",    (0, 0), (-1, -1), 0.25, _GRIS_BORDE),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("BACKGROUND",   (0, 0), (-1, 0),  _GRIS_HEADER),
    ]))
    return t


def _build_items(S, total: int) -> Table:
    header = [
        Paragraph("<b>Cód.</b>",        S["center_bold"]),
        Paragraph("<b>Descripción</b>",  S["bold"]),
        Paragraph("<b>Cantidad</b>",     S["center_bold"]),
        Paragraph("<b>Precio Unit.</b>", S["right_bold"]),
        Paragraph("<b>Subtotal</b>",     S["right_bold"]),
    ]
    fila = [
        Paragraph("—", S["center"]),
        Paragraph("Consumición", S["normal"]),
        Paragraph("1", S["center"]),
        Paragraph(_fmt_money(total), S["right"]),
        Paragraph(_fmt_money(total), S["right"]),
    ]
    t = Table([header, fila], colWidths=[1.5*cm, 9.2*cm, 2.0*cm, 2.8*cm, 2.7*cm])
    t.setStyle(TableStyle([
        ("BOX",          (0, 0), (-1, -1), 0.5, _GRIS_BORDE),
        ("INNERGRID",    (0, 0), (-1, -1), 0.25, _GRIS_BORDE),
        ("BACKGROUND",   (0, 0), (-1, 0),  _GRIS_HEADER),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _build_totales(S, total: int) -> Table:
    filas = [
        [Paragraph("<b>Subtotal</b>", S["right_bold"]),
         Paragraph(_fmt_money(total), S["right"])],
        [Paragraph("<b>Importe Total</b>",
                   ParagraphStyle("tlbl", fontName="Helvetica-Bold",
                                  fontSize=10, alignment=TA_RIGHT, textColor=_NEGRO)),
         Paragraph(f"<b>{_fmt_money(total)}</b>",
                   ParagraphStyle("tval", fontName="Helvetica-Bold",
                                  fontSize=10, alignment=TA_RIGHT, textColor=_NEGRO))],
    ]
    t = Table(filas, colWidths=[4.0*cm, 3.0*cm])
    t.setStyle(TableStyle([
        ("ALIGN",        (0, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LINEABOVE",    (0, -1), (-1, -1), 1.0, _NEGRO),
        ("BOX",          (0, 0), (-1, -1), 0.5, _GRIS_BORDE),
    ]))
    return t


def _build_pie(S, qr_buf: io.BytesIO, cae: str, cae_exp: date | None) -> Table:
    exp_str = cae_exp.strftime("%d/%m/%Y") if cae_exp else "—"
    qr_img  = RLImage(qr_buf, width=3.2*cm, height=3.2*cm)

    cae_block = [
        Paragraph("<b>Comprobante Autorizado</b>",
                  ParagraphStyle("auth", fontName="Helvetica-Bold", fontSize=9,
                                 textColor=_NEGRO)),
        Spacer(1, 4),
        Paragraph(f"<b>CAE N°:</b> {cae}", S["cae"]),
        Paragraph(f"<b>Fecha de Vto. CAE:</b> {exp_str}", S["cae"]),
        Spacer(1, 8),
        Paragraph(
            "Este comprobante fue generado en el entorno de<br/>homologación de AFIP/ARCA.",
            ParagraphStyle("aviso", fontSize=7, textColor=_GRIS_MEDIO, leading=9),
        ),
    ]

    t = Table([[qr_img, cae_block]], colWidths=[3.8*cm, 14.4*cm])
    t.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (0, 0),   0),
        ("LEFTPADDING",  (1, 0), (1, 0),   12),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
        ("BOX",          (0, 0), (-1, -1), 0.5, _GRIS_BORDE),
    ]))
    return t


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def generar_comprobante_pdf(
    invoice: Any,
    emisor: EmisorConfig | None = None,
) -> bytes:
    """
    Genera el PDF de un comprobante fiscal argentino.

    Parámetros
    ----------
    invoice : InvoiceModel (SQLAlchemy) o dict con los mismos campos.
    emisor  : EmisorConfig con los datos del emisor.
               Si es None, usa los valores por defecto de Bejas.

    Retorna
    -------
    bytes — contenido completo del PDF, listo para servir por HTTP o escribir a disco.
    """
    if emisor is None:
        emisor = EmisorConfig()

    tipo_cod, tipo_nombre, tipo_letra = _TIPO_COD, _TIPO_NOMBRE, _TIPO_LETRA

    total      = int(_get(invoice, "total", 0))
    cae        = _get(invoice, "cae") or "—"
    cae_exp    = _get(invoice, "cae_expiration")

    S      = _make_styles()
    qr_buf = _build_qr_image(emisor, invoice, tipo_cod)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.5*cm,  bottomMargin=1.5*cm,
        title=f"{tipo_nombre} {tipo_letra} "
              f"{_get(invoice, 'point_of_sale', 1):04d}-"
              f"{_get(invoice, 'voucher_number', 1):08d}",
        author=emisor.nombre,
    )

    story = [
        Paragraph(
            f"{tipo_nombre} {tipo_letra}",
            ParagraphStyle("page_title", fontName="Helvetica-Bold", fontSize=13,
                           alignment=TA_CENTER, spaceAfter=4, textColor=_GRIS_OSCURO),
        ),
        HRFlowable(width="100%", thickness=1.2, color=_NEGRO, spaceAfter=6),
        _build_header(S, emisor, invoice, tipo_cod, tipo_nombre, tipo_letra),
        Spacer(1, 0.35*cm),
        Paragraph("<b>DATOS DEL RECEPTOR</b>", S["sec_label"]),
        _build_receptor(S),
        Spacer(1, 0.35*cm),
        Paragraph("<b>DETALLE</b>", S["sec_label"]),
        _build_items(S, total),
        Spacer(1, 0.25*cm),
        # Totales alineados a la derecha
        Table(
            [[Spacer(1, 1), _build_totales(S, total)]],
            colWidths=[11.2*cm, 7.0*cm],
            style=TableStyle([
                ("LEFTPADDING",  (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING",   (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
                ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ]),
        ),
        Spacer(1, 0.5*cm),
        HRFlowable(width="100%", thickness=0.5, color=_GRIS_BORDE, spaceAfter=6),
        _build_pie(S, qr_buf, cae, cae_exp),
    ]

    doc.build(story)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
# SNIPPET DE PRUEBA — monto dinámico 8500
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    from pathlib import Path
    from types import SimpleNamespace

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    # Simula un InvoiceModel con total=8500 (distinto al 1000 hardcodeado del script)
    invoice_demo = SimpleNamespace(
        voucher_type    = "C",
        point_of_sale   = 1,
        voucher_number  = 2,
        issued_at       = datetime(2026, 6, 29, 21, 0, 0),
        total           = 8500,          # ← monto dinámico de prueba
        cae             = "86260509443592",
        cae_expiration  = date(2026, 7, 9),
        status          = "INVOICE_AUTHORIZED",
    )

    emisor_demo = EmisorConfig()

    print(f"Generando PDF de prueba con total={invoice_demo.total}…")
    pdf_bytes = generar_comprobante_pdf(invoice_demo, emisor_demo)

    out_dir  = Path(__file__).parent.parent.parent / "scripts" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"prueba_dinamico_{invoice_demo.total}.pdf"
    out_path.write_bytes(pdf_bytes)

    print(f"✓  PDF generado: {out_path.resolve()}")
    print(f"   Tamaño: {len(pdf_bytes):,} bytes")
    print(f"   Total en el comprobante: {_fmt_money(invoice_demo.total)}")
    print("   (verificá que el monto visible en el PDF sea $8.500,00)")