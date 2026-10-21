"""Generación del certificado en PDF con ReportLab."""

import io
from datetime import datetime

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

TINTA = HexColor("#16323a")
ACENTO = HexColor("#0f766e")
SUAVE = HexColor("#5b6b70")

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_larga(fecha: datetime) -> str:
    return f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"


def generar_pdf(
    nombre: str, curso: str, horas: int, empresa: str, codigo: str, emitido_en: datetime, url_verificacion: str
) -> bytes:
    salida = io.BytesIO()
    ancho, alto = landscape(A4)
    c = canvas.Canvas(salida, pagesize=(ancho, alto))
    c.setTitle(f"Certificado {codigo}")
    c.setAuthor("AulaNube · CapacitaPro S.A.S.")

    c.setStrokeColor(ACENTO)
    c.setLineWidth(3)
    c.rect(28, 28, ancho - 56, alto - 56)
    c.setLineWidth(0.8)
    c.rect(38, 38, ancho - 76, alto - 76)

    c.setFillColor(ACENTO)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(ancho / 2, alto - 90, "AULANUBE · CAPACITAPRO S.A.S.")

    c.setFillColor(TINTA)
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(ancho / 2, alto - 150, "Certificado de finalización")

    c.setFillColor(SUAVE)
    c.setFont("Helvetica", 14)
    c.drawCentredString(ancho / 2, alto - 200, "Se certifica que")

    c.setFillColor(TINTA)
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(ancho / 2, alto - 245, nombre)

    c.setFillColor(SUAVE)
    c.setFont("Helvetica", 14)
    c.drawCentredString(ancho / 2, alto - 285, f"colaborador(a) de {empresa}, completó el curso")

    c.setFillColor(TINTA)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(ancho / 2, alto - 322, curso)

    c.setFillColor(SUAVE)
    c.setFont("Helvetica", 13)
    c.drawCentredString(ancho / 2, alto - 352, f"con una intensidad de {horas} hora{'s' if horas != 1 else ''}, el {fecha_larga(emitido_en)}.")

    c.setFont("Helvetica", 10)
    c.drawString(70, 80, f"Código de verificación: {codigo}")
    c.drawString(70, 64, f"Verifique la autenticidad en {url_verificacion}")
    c.setStrokeColor(TINTA)
    c.line(ancho - 290, 100, ancho - 70, 100)
    c.drawCentredString(ancho - 180, 86, "Dirección académica · CapacitaPro")

    c.showPage()
    c.save()
    return salida.getvalue()
