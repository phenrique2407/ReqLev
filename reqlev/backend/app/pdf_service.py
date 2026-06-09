"""ReqLev – PDF Export Service

Generates a project report PDF using ReportLab.

Structure
---------
1. Cover page  – project name, description, creation date, contributors list
2. Requirements section – table with all requirements
3. Activity log section – chronological list of activities
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable,
)

from . import models

# ── Brand colours ─────────────────────────────────────────────────────────────
ORANGE      = colors.HexColor("#F97316")
DARK_BG     = colors.HexColor("#0D0D0D")
CARD_BG     = colors.HexColor("#1F1F1F")
TEXT_MAIN   = colors.HexColor("#F0F0F0")
TEXT_MUTED  = colors.HexColor("#A0A0A0")
BORDER      = colors.HexColor("#2E2E2E")
GREEN       = colors.HexColor("#22C55E")
AMBER       = colors.HexColor("#F59E0B")

STATUS_COLOURS = {
    "todo":        (colors.HexColor("#374151"), colors.HexColor("#D1D5DB")),
    "in_progress": (AMBER,                      DARK_BG),
    "done":        (GREEN,                      DARK_BG),
}

STATUS_LABELS = {
    "todo":        "A fazer",
    "in_progress": "Em andamento",
    "done":        "Concluído",
}

TYPE_COLOURS = {
    "RF":  (ORANGE, DARK_BG),
    "RNF": (colors.HexColor("#3B82F6"), TEXT_MAIN),
}


# ── Page header/footer callbacks ──────────────────────────────────────────────

def _header_footer(canvas, doc):
    canvas.saveState()

    w, h = A4
    # Header line
    canvas.setStrokeColor(ORANGE)
    canvas.setLineWidth(1.5)
    canvas.line(2 * cm, h - 1.8 * cm, w - 2 * cm, h - 1.8 * cm)

    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(ORANGE)
    canvas.drawString(2 * cm, h - 1.5 * cm, "REQLEV")

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawRightString(w - 2 * cm, h - 1.5 * cm, doc.title)

    # Footer
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(2 * cm, 1.5 * cm, w - 2 * cm, 1.5 * cm)

    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawString(2 * cm, 1.1 * cm, f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    canvas.drawRightString(w - 2 * cm, 1.1 * cm, f"Página {canvas.getPageNumber()}")

    canvas.restoreState()


def _cover_page(canvas, doc):
    """First-page callback – full dark cover."""
    canvas.saveState()
    w, h = A4

    # Background
    canvas.setFillColor(DARK_BG)
    canvas.rect(0, 0, w, h, fill=1, stroke=0)

    # Orange accent bar (left side)
    canvas.setFillColor(ORANGE)
    canvas.rect(0, 0, 0.7 * cm, h, fill=1, stroke=0)

    # Brand
    canvas.setFont("Helvetica-Bold", 28)
    canvas.setFillColor(ORANGE)
    canvas.drawString(2 * cm, h - 4 * cm, "REQLEV")

    canvas.setFont("Helvetica", 11)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawString(2 * cm, h - 4.8 * cm, "Gerenciamento de Projetos & Requisitos")

    # Divider
    canvas.setStrokeColor(ORANGE)
    canvas.setLineWidth(1)
    canvas.line(2 * cm, h - 5.5 * cm, w - 2 * cm, h - 5.5 * cm)

    canvas.restoreState()


# ── Main export function ──────────────────────────────────────────────────────

def generate_project_pdf(
    project:      models.Project,
    requirements: List[models.Requirement],
    activities:   List[models.ActivityLog],
    contributors: List[dict],            # [{"username": ..., "role": ...}]
) -> bytes:
    """Build the PDF in memory and return raw bytes."""

    buf = io.BytesIO()
    w, h = A4

    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        title=project.name,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
    )

    # Two page templates: cover (no header/footer), body (with header/footer)
    cover_frame = Frame(0, 0, w, h, leftPadding=2 * cm, rightPadding=2 * cm,
                        topPadding=6 * cm, bottomPadding=2.5 * cm, id="cover")
    body_frame  = Frame(2 * cm, 2 * cm, w - 4 * cm, h - 4 * cm,
                        leftPadding=0, rightPadding=0,
                        topPadding=0.5 * cm, bottomPadding=0, id="body")

    doc.addPageTemplates([
        PageTemplate(id="Cover", frames=[cover_frame], onPage=_cover_page),
        PageTemplate(id="Body",  frames=[body_frame],  onPage=_header_footer),
    ])

    styles = getSampleStyleSheet()
    s      = styles["Normal"]

    def _style(**kw) -> ParagraphStyle:
        return ParagraphStyle("_", parent=s, **kw)

    title_style   = _style(fontSize=30, textColor=TEXT_MAIN,  fontName="Helvetica-Bold",
                           spaceAfter=6, leading=36)
    sub_style     = _style(fontSize=13, textColor=TEXT_MUTED, fontName="Helvetica",
                           spaceAfter=4)
    label_style   = _style(fontSize=9,  textColor=TEXT_MUTED, fontName="Helvetica",
                           spaceAfter=2)
    value_style   = _style(fontSize=11, textColor=TEXT_MAIN,  fontName="Helvetica",
                           spaceAfter=8)
    h2_style      = _style(fontSize=16, textColor=ORANGE,     fontName="Helvetica-Bold",
                           spaceBefore=14, spaceAfter=8)
    body_style    = _style(fontSize=9,  textColor=TEXT_MAIN,  fontName="Helvetica",
                           leading=14)
    muted_style   = _style(fontSize=8,  textColor=TEXT_MUTED, fontName="Helvetica")
    req_name_style = _style(fontSize=10, textColor=TEXT_MAIN, fontName="Helvetica-Bold",
                            leading=14)
    req_desc_style = _style(fontSize=9,  textColor=TEXT_MUTED, fontName="Helvetica",
                            leading=12)

    story = []

    # ── COVER ────────────────────────────────────────────────────────────────
    story.append(Paragraph(project.name, title_style))
    if project.description:
        story.append(Paragraph(project.description, sub_style))
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", color=BORDER, thickness=0.5))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("Data de Criação", label_style))
    created = project.created_at.strftime("%d/%m/%Y") if project.created_at else "—"
    story.append(Paragraph(created, value_style))

    story.append(Paragraph("Proprietário", label_style))
    story.append(Paragraph(project.owner.username if project.owner else "—", value_style))

    story.append(Paragraph("Contribuidores", label_style))
    for c in contributors:
        perm = "Editor" if c.get("permission") == "edit" else "Visualizador"
        story.append(Paragraph(f"• {c['username']} &lt;{c['email']}&gt; — {perm}", body_style))
    if not contributors:
        story.append(Paragraph("Nenhum colaborador adicional.", muted_style))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"Total de Requisitos: {len(requirements)}", value_style))

    story.append(PageBreak())

    # ── Switch to body template ───────────────────────────────────────────────
    from reportlab.platypus import NextPageTemplate
    story.append(NextPageTemplate("Body"))

    # ── REQUIREMENTS ─────────────────────────────────────────────────────────
    story.append(Paragraph("Requisitos", h2_style))
    story.append(HRFlowable(width="100%", color=ORANGE, thickness=1))
    story.append(Spacer(1, 0.4 * cm))

    if not requirements:
        story.append(Paragraph("Nenhum requisito cadastrado.", muted_style))
    else:
        for req in requirements:
            # Enum values may be Python enum objects or raw strings
            _status = req.status.value if hasattr(req.status, 'value') else str(req.status)
            _type   = req.type.value   if hasattr(req.type,   'value') else str(req.type)

            sc, tc  = STATUS_COLOURS.get(_status, (BORDER, TEXT_MAIN))
            rc, rtc = TYPE_COLOURS.get(_type,   (BORDER, TEXT_MAIN))
            st_label = STATUS_LABELS.get(_status, _status)

            # Badges row – use plain text; colour comes from ParagraphStyle.textColor
            badge_data = [[
                Paragraph(
                    _type,
                    _style(fontSize=9, fontName="Helvetica-Bold", textColor=rc)
                ),
                Paragraph(
                    st_label,
                    _style(fontSize=9, fontName="Helvetica-Bold", textColor=sc)
                ),
            ]]
            badge_table = Table(badge_data, colWidths=[2.5 * cm, 4 * cm])
            badge_table.setStyle(TableStyle([("ALIGN", (0,0), (-1,-1), "LEFT"),
                                              ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                                              ("LEFTPADDING", (0,0), (-1,-1), 0)]))

            req_block = [
                Paragraph(req.name, req_name_style),
                Spacer(1, 2),
                badge_table,
            ]
            if req.description:
                req_block += [Spacer(1, 4), Paragraph(req.description, req_desc_style)]

            # Container table (card look)
            tbl = Table([[req_block]], colWidths=[w - 4 * cm - 0.4 * cm])
            tbl.setStyle(TableStyle([
                ("BACKGROUND",   (0,0), (-1,-1), CARD_BG),
                ("BOX",          (0,0), (-1,-1), 0.5, BORDER),
                ("LEFTPADDING",  (0,0), (-1,-1), 8),
                ("RIGHTPADDING", (0,0), (-1,-1), 8),
                ("TOPPADDING",   (0,0), (-1,-1), 8),
                ("BOTTOMPADDING",(0,0), (-1,-1), 8),
                ("VALIGN",       (0,0), (-1,-1), "TOP"),
            ]))
            story.append(tbl)
            story.append(Spacer(1, 0.3 * cm))

    story.append(PageBreak())

    # ── ACTIVITY LOG ─────────────────────────────────────────────────────────
    story.append(Paragraph("Histórico de Atividades", h2_style))
    story.append(HRFlowable(width="100%", color=ORANGE, thickness=1))
    story.append(Spacer(1, 0.4 * cm))

    if not activities:
        story.append(Paragraph("Nenhuma atividade registrada.", muted_style))
    else:
        log_data = [["Data/Hora", "Usuário", "Ação", "Objeto"]]
        for act in activities:
            ts   = act.created_at.strftime("%d/%m/%Y %H:%M") if act.created_at else "—"
            user = act.user.username if act.user else "Sistema"
            log_data.append([ts, user, act.action, act.object_name or "—"])

        col_w = [(w - 4 * cm) * f for f in (0.22, 0.18, 0.35, 0.25)]
        log_table = Table(log_data, colWidths=col_w, repeatRows=1)
        log_table.setStyle(TableStyle([
            # Header
            ("BACKGROUND",    (0,0), (-1,0), ORANGE),
            ("TEXTCOLOR",     (0,0), (-1,0), DARK_BG),
            ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,0), 8),
            ("ALIGN",         (0,0), (-1,0), "LEFT"),
            ("BOTTOMPADDING", (0,0), (-1,0), 6),
            ("TOPPADDING",    (0,0), (-1,0), 6),
            # Body rows
            ("FONTNAME",      (0,1), (-1,-1), "Helvetica"),
            ("FONTSIZE",      (0,1), (-1,-1), 8),
            ("TEXTCOLOR",     (0,1), (-1,-1), TEXT_MAIN),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [CARD_BG, colors.HexColor("#191919")]),
            ("GRID",          (0,0), (-1,-1), 0.3, BORDER),
            ("LEFTPADDING",   (0,0), (-1,-1), 6),
            ("RIGHTPADDING",  (0,0), (-1,-1), 6),
            ("TOPPADDING",    (0,1), (-1,-1), 4),
            ("BOTTOMPADDING", (0,1), (-1,-1), 4),
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ]))
        story.append(log_table)

    doc.build(story)
    return buf.getvalue()
